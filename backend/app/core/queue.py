"""
Async download queue with WebSocket broadcast for real-time progress.
"""
import asyncio
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Awaitable

from sqlalchemy import update, select
from app.config import get_settings
from app.core.downloader import download_chapter_to_cbz

log = logging.getLogger(__name__)
settings = get_settings()

# Active WebSocket connections waiting for progress events
_ws_listeners: set[Callable[[dict], Awaitable[None]]] = set()

# download_id → task info
_active: dict[str, dict] = {}


def register_ws_listener(callback: Callable[[dict], Awaitable[None]]):
    _ws_listeners.add(callback)


def unregister_ws_listener(callback: Callable[[dict], Awaitable[None]]):
    _ws_listeners.discard(callback)


async def _broadcast(event: dict):
    dead = set()
    for cb in _ws_listeners:
        try:
            await cb(event)
        except Exception:
            dead.add(cb)
    for cb in dead:
        _ws_listeners.discard(cb)


async def _update_db_record(db_factory, download_id: str, **fields):
    try:
        from app.models.download import DownloadRecord
        async with db_factory() as db:
            await db.execute(
                update(DownloadRecord)
                .where(DownloadRecord.id == download_id)
                .values(**fields)
            )
            await db.commit()
    except Exception as exc:
        log.error("Failed to update DownloadRecord %s: %s", download_id, exc)


class DownloadQueue:
    def __init__(self, max_concurrent: int = 3):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running = False
        self._paused = False

    async def start(self):
        self._running = True
        asyncio.create_task(self._worker())

    async def stop(self):
        self._running = False

    def pause(self):
        self._paused = True
        log.info("Download queue paused")

    def resume(self):
        self._paused = False
        log.info("Download queue resumed")

    @property
    def is_paused(self) -> bool:
        return self._paused

    async def enqueue(
        self,
        *,
        db_session_factory,
        provider_id: str,
        manga_id: str,
        manga_title: str,
        chapter_id: str,
        chapter_title: str,
        chapter_number: float,
        page_urls: list[str],
        user_id: str = "local-api-key-user",
    ) -> str:
        download_id = str(uuid.uuid4())
        now = datetime.utcnow()
        _active[download_id] = {
            "id": download_id,
            "provider": provider_id,
            "manga_id": manga_id,
            "manga_title": manga_title,
            "chapter_id": chapter_id,
            "chapter_title": chapter_title,
            "chapter_number": chapter_number,
            "status": "queued",
            "progress": 0,
            "total_pages": len(page_urls),
            "downloaded_pages": 0,
            "error": None,
            "created_at": now.isoformat(),
        }

        # Persist immediately so library shows "queued" state right away
        try:
            from app.models.download import DownloadRecord
            async with db_session_factory() as db:
                record = DownloadRecord(
                    id=download_id,
                    manga_id=f"{provider_id}:{manga_id}",
                    chapter_id=chapter_id,
                    provider=provider_id,
                    manga_title=manga_title,
                    chapter_title=chapter_title,
                    chapter_number=chapter_number,
                    status="queued",
                    progress=0,
                    total_pages=len(page_urls),
                    downloaded_pages=0,
                    created_at=now,
                    user_id=user_id,
                )
                db.add(record)
                await db.commit()
        except Exception as exc:
            log.error("Failed to persist initial DownloadRecord: %s", exc)

        await _broadcast({"type": "queued", "download": _active[download_id]})

        await self._queue.put({
            "download_id": download_id,
            "db_session_factory": db_session_factory,
            "provider_id": provider_id,
            "manga_id": manga_id,
            "manga_title": manga_title,
            "chapter_id": chapter_id,
            "chapter_title": chapter_title,
            "chapter_number": chapter_number,
            "page_urls": page_urls,
        })

        return download_id

    async def _worker(self):
        log.info("Download worker started")
        while self._running:
            if self._paused:
                await asyncio.sleep(0.5)
                continue
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            await self._semaphore.acquire()
            asyncio.create_task(self._run_job_wrapper(job))

    async def _run_job_wrapper(self, job: dict):
        try:
            await self._run_job(job)
        finally:
            self._semaphore.release()

    async def _run_job(self, job: dict):
        download_id = job["download_id"]
        info = _active[download_id]
        db_factory = job["db_session_factory"]
        log.info("Starting download job %s (%s)", download_id, job["manga_title"])

        async def on_progress(downloaded: int, total: int):
            info["downloaded_pages"] = downloaded
            info["total_pages"] = total
            info["progress"] = int((downloaded / total) * 100) if total else 0
            info["status"] = "downloading"
            await _broadcast({"type": "progress", "download": dict(info)})

        info["status"] = "downloading"
        await _broadcast({"type": "started", "download": dict(info)})
        await _update_db_record(db_factory, download_id, status="downloading")

        try:
            cbz_path, file_size = await download_chapter_to_cbz(
                provider_id=job["provider_id"],
                manga_title=job["manga_title"],
                chapter_title=job["chapter_title"],
                chapter_number=job["chapter_number"],
                page_urls=job["page_urls"],
                library_path=Path(settings.LIBRARY_PATH),
                cache_path=Path(settings.CACHE_PATH),
                on_progress=on_progress,
            )

            output_path_str = str(cbz_path)

            # --- Supabase Cloud Storage Integration ---
            if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY:
                from app.core.storage import check_and_evict, upload_file
                remote_path = f"{cbz_path.parent.name}/{cbz_path.name}"

                info["status"] = "packaging"
                await _broadcast({"type": "progress", "download": dict(info)})
                await _update_db_record(db_factory, download_id, status="packaging")

                async with db_factory() as db:
                    await check_and_evict(db, file_size, user_id=job.get("user_id", "local-api-key-user"))

                try:
                    await upload_file(cbz_path, remote_path)
                    output_path_str = remote_path
                    log.info("Uploaded %s to Supabase", remote_path)
                    cbz_path.unlink(missing_ok=True)
                except Exception as e:
                    log.error("Failed to upload %s to Supabase: %s", remote_path, e)

            info["status"] = "done"
            info["progress"] = 100
            info["output_path"] = output_path_str

            await _update_db_record(
                db_factory, download_id,
                status="done",
                progress=100,
                total_pages=info["total_pages"],
                downloaded_pages=info["total_pages"],
                output_path=output_path_str,
                file_size_bytes=file_size,
                completed_at=datetime.utcnow(),
            )
            log.info("Download job %s finished", download_id)

        except Exception as exc:
            log.exception("Download failed for %s", download_id)
            info["status"] = "failed"
            info["error"] = str(exc)
            await _update_db_record(db_factory, download_id, status="failed", error=str(exc))

        await _broadcast({"type": "completed", "download": dict(info)})
        _active.pop(download_id, None)

    def list_active(self) -> list[dict]:
        return list(_active.values())

    def get(self, download_id: str) -> dict | None:
        return _active.get(download_id)

    async def cancel(self, download_id: str, db_factory) -> bool:
        """Cancel a queued download. Returns True if found and cancelled."""
        info = _active.get(download_id)
        if not info:
            return False
        info["status"] = "failed"
        info["error"] = "Cancelled by user"
        await _broadcast({"type": "completed", "download": dict(info)})
        _active.pop(download_id, None)
        await _update_db_record(db_factory, download_id, status="failed", error="Cancelled by user")
        return True


# Singleton queue instance
download_queue = DownloadQueue(max_concurrent=settings.MAX_CONCURRENT_DOWNLOADS)
