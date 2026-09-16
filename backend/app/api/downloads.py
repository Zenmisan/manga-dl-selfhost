from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import json
import logging

from app.providers import get_provider
from app.core.queue import download_queue, register_ws_listener, unregister_ws_listener
from app.database import get_db, AsyncSessionLocal
from app.models.download import DownloadRecord
from app.core.supabase_auth import get_current_user
from app.config import get_settings

settings = get_settings()

log = logging.getLogger(__name__)
router = APIRouter(prefix="/downloads", tags=["downloads"])


class DownloadRequest(BaseModel):
    provider_id: str
    manga_id: str
    chapter_id: str
    manga_title: str | None = None
    chapter_title: str | None = None
    chapter_number: float | None = None
    pages: list[str] | None = None


@router.post("/queue")
async def queue_download(
    req: DownloadRequest,
    user_id: str = Depends(get_current_user),
):
    """Queue a chapter for download, tagged to the authenticated user."""
    pages: list[str] = req.pages or []
    manga_title: str = req.manga_title or req.manga_id
    chapter_title: str = req.chapter_title or f"Chapter {req.chapter_number or 1}"
    chapter_number: float = req.chapter_number if req.chapter_number is not None else 1.0

    provider = get_provider(req.provider_id)
    if provider:
        try:
            manga = await provider.get_manga(req.manga_id)
            chapter = next((c for c in manga.chapters if c.id == req.chapter_id), None)
            if chapter:
                manga_title = manga.title
                chapter_title = chapter.title
                chapter_number = chapter.number
                pages = await provider.get_pages(req.chapter_id)
        except Exception as exc:
            log.warning("Failed to fetch Python provider info for %s: %s", req.provider_id, exc)

    if not pages:
        raise HTTPException(status_code=422, detail="No pages found — chapter may be paywalled or unavailable")

    download_id = await download_queue.enqueue(
        db_session_factory=AsyncSessionLocal,
        provider_id=req.provider_id,
        manga_id=req.manga_id,
        manga_title=manga_title,
        chapter_id=req.chapter_id,
        chapter_title=chapter_title,
        chapter_number=chapter_number,
        page_urls=pages,
        user_id=user_id,
    )

    return {"download_id": download_id, "total_pages": len(pages)}


@router.post("/pause")
async def pause_downloads(user_id: str = Depends(get_current_user)):
    download_queue.pause()
    return {"paused": True}


@router.post("/resume")
async def resume_downloads(user_id: str = Depends(get_current_user)):
    download_queue.resume()
    return {"paused": False}


@router.get("/queue-status")
async def queue_status(user_id: str = Depends(get_current_user)):
    return {"paused": download_queue.is_paused}


@router.post("/cancel/{download_id}")
async def cancel_download(download_id: str, user_id: str = Depends(get_current_user)):
    cancelled = await download_queue.cancel(download_id, AsyncSessionLocal)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Download not found in active queue")
    return {"cancelled": True}


@router.post("/retry/{download_id}")
async def retry_download(
    download_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = (await db.execute(
        select(DownloadRecord).where(DownloadRecord.id == download_id, DownloadRecord.user_id == user_id)
    )).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Download record not found")

    provider = get_provider(record.provider)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{record.provider}' not found")

    try:
        pages = await provider.get_pages(record.chapter_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch pages: {exc}")

    if not pages:
        raise HTTPException(status_code=422, detail="No pages found")

    new_id = await download_queue.enqueue(
        db_session_factory=AsyncSessionLocal,
        provider_id=record.provider,
        manga_id=record.manga_id,
        manga_title=record.manga_title,
        chapter_id=record.chapter_id,
        chapter_title=record.chapter_title,
        chapter_number=record.chapter_number,
        page_urls=pages,
        user_id=user_id,
    )
    return {"download_id": new_id, "total_pages": len(pages)}


@router.delete("/history")
async def clear_history(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(DownloadRecord).where(
            DownloadRecord.user_id == user_id,
            DownloadRecord.status.in_(["done", "failed"]),
        )
    )
    await db.commit()
    return {"cleared": True}


@router.get("/active")
async def list_active_downloads(user_id: str = Depends(get_current_user)):
    return download_queue.list_active()


@router.get("/history")
async def download_history(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DownloadRecord)
        .where(DownloadRecord.user_id == user_id)
        .order_by(DownloadRecord.created_at.desc())
        .limit(100)
    )
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "manga_title": r.manga_title,
            "chapter_title": r.chapter_title,
            "chapter_number": r.chapter_number,
            "provider": r.provider,
            "status": r.status,
            "output_path": r.output_path,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in records
    ]


@router.websocket("/ws")
async def download_ws(websocket: WebSocket):
    """
    WebSocket endpoint for real-time download progress.
    Broadcasts events: {type: "queued"|"started"|"progress"|"completed", download: {...}}
    """
    api_key = websocket.query_params.get("api_key", "")
    token = websocket.query_params.get("token", "")

    await websocket.accept()

    # Validate: API key OR Bearer token must be present
    api_key_ok = settings.API_KEY is None or (api_key and api_key == settings.API_KEY)
    token_ok = bool(token)  # existence check — full JWT verify below
    if not api_key_ok and not token_ok:
        await websocket.close(code=4401, reason="Unauthorized")
        return

    if token_ok and not api_key_ok:
        # Verify Supabase JWT from query param
        from starlette.requests import Request as _Req
        from starlette.datastructures import Headers as _Hdrs
        import urllib.parse
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
        }
        fake_req = _Req(scope)
        try:
            from app.core.supabase_auth import get_current_user
            await get_current_user(fake_req)
        except Exception:
            await websocket.close(code=4401, reason="Invalid token")
            return

    async def send_event(event: dict):
        await websocket.send_json(event)

    register_ws_listener(send_event)
    await websocket.send_json({"type": "state", "downloads": download_queue.list_active()})

    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        unregister_ws_listener(send_event)
