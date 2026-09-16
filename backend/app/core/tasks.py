import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.orm import defer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.manga import MangaRecord
from app.models.download import DownloadRecord
from app.providers import get_provider
from app.core.queue import download_queue

log = logging.getLogger(__name__)

async def _sync_manga(db: AsyncSession, manga: MangaRecord):
    provider = get_provider(manga.provider)
    if not provider:
        log.debug(f"Provider {manga.provider} sync handled via client extension.")
        return

    try:
        detail = await provider.get_manga(manga.provider_manga_id)
    except Exception as exc:
        log.error(f"Failed to fetch manga {manga.provider_manga_id}: {exc}")
        return

    # Get already downloaded chapters
    stmt = select(DownloadRecord.chapter_id).where(
        DownloadRecord.manga_id == manga.id,
        DownloadRecord.status == "done"
    )
    result = await db.execute(stmt)
    downloaded_chapter_ids = set(result.scalars().all())

    # Enqueue new chapters
    for chapter in detail.chapters:
        if chapter.id not in downloaded_chapter_ids:
            try:
                pages = await provider.get_pages(chapter.id)
                if pages:
                    log.info(f"Auto-queueing {manga.title} - {chapter.title}")
                    await download_queue.enqueue(
                        db_session_factory=AsyncSessionLocal,
                        provider_id=manga.provider,
                        manga_id=manga.provider_manga_id,
                        manga_title=detail.title,
                        chapter_id=chapter.id,
                        chapter_title=chapter.title,
                        chapter_number=chapter.number,
                        page_urls=pages,
                    )
            except Exception as exc:
                log.error(f"Failed fetching pages for {chapter.id}: {exc}")

async def _sync_once():
    """Run one sync cycle immediately (for manual triggers)."""
    log.info("Running manual sync...")
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(MangaRecord).options(defer(MangaRecord.chapters_json)).where(MangaRecord.subscribed == True)
            result = await db.execute(stmt)
            mangas = result.scalars().all()
            for manga in mangas:
                await _sync_manga(db, manga)
                await asyncio.sleep(2)
    except Exception as exc:
        log.error(f"Manual sync failed: {exc}")


async def sync_subscribed_manga():
    """Background task to sync subscribed manga every 6 hours."""
    while True:
        log.info("Running subscribed manga sync...")
        try:
            async with AsyncSessionLocal() as db:
                stmt = select(MangaRecord).options(defer(MangaRecord.chapters_json)).where(MangaRecord.subscribed == True)
                result = await db.execute(stmt)
                mangas = result.scalars().all()

                for manga in mangas:
                    await _sync_manga(db, manga)
                    await asyncio.sleep(2)  # politeness delay
        except Exception as exc:
            log.error(f"Sync task failed: {exc}")
        
        await asyncio.sleep(6 * 3600)  # 6 hours

_sync_task = None

def start_sync_task():
    global _sync_task
    if _sync_task is None:
        _sync_task = asyncio.create_task(sync_subscribed_manga())

def stop_sync_task():
    global _sync_task
    if _sync_task:
        _sync_task.cancel()
        _sync_task = None
