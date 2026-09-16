"""
Backup API:
  POST /backup/import/tachibk       — parse .tachibk → JSON
  GET  /backup/export/manual        — export user data as manga-dl JSON backup
  POST /backup/import/manual        — import manga-dl JSON backup
"""
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tachibk import decode_tachibk
from app.core.supabase_auth import get_current_user
from app.database import get_db
from app.models.reading_progress import ReadingProgress

router = APIRouter(prefix="/backup", tags=["backup"])

BACKUP_VERSION = "1.0"


# ── Tachiyomi .tachibk import ─────────────────────────────────────────────────

MAX_TACHIBK_BYTES = 50 * 1024 * 1024  # 50 MB — Tachiyomi backups are rarely > 5 MB


@router.post("/import/tachibk")
async def import_tachibk(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    """
    Accept a .tachibk file, decode it from gzip+protobuf, return JSON.
    The frontend uses this to restore library, history, bookmarks, etc.
    """
    if file.size and file.size > MAX_TACHIBK_BYTES:
        raise HTTPException(413, "File exceeds 50 MB limit.")
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(400, "Empty file")
    if len(raw) > MAX_TACHIBK_BYTES:
        raise HTTPException(413, "File exceeds 50 MB limit.")
    try:
        parsed = decode_tachibk(raw)
    except Exception as e:
        raise HTTPException(422, f"Failed to decode backup: {e}")
    return parsed


# ── manga-dl manual backup export ─────────────────────────────────────────────

@router.get("/export/manual")
async def export_manual_backup(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export all server-side reading history for the user.
    The frontend appends client-side data (localStorage) before download.
    """
    result = await db.execute(
        select(ReadingProgress).where(ReadingProgress.user_id == user_id)
    )
    records = result.scalars().all()

    history = [
        {
            "provider": r.provider,
            "manga_id": r.manga_id,
            "chapter_id": r.chapter_id,
            "last_page": r.last_page,
            "manga_title": r.manga_title,
            "chapter_title": r.chapter_title,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in records
    ]

    return {
        "version": BACKUP_VERSION,
        "app": "manga-dl",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "cloud_history": history,
    }


# ── manga-dl manual backup import ─────────────────────────────────────────────

@router.post("/import/manual")
async def import_manual_backup(
    payload: dict[str, Any],
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Restore cloud reading history from a manga-dl JSON backup.
    Client-side data (library, bookmarks, read tracking, notes, etc.)
    is restored directly by the frontend from the same JSON file.
    """
    if payload.get("app") != "manga-dl":
        raise HTTPException(400, "Not a manga-dl backup file")

    restored = 0
    for entry in payload.get("cloud_history", []):
        try:
            result = await db.execute(
                select(ReadingProgress).where(
                    ReadingProgress.user_id == user_id,
                    ReadingProgress.provider == entry["provider"],
                    ReadingProgress.manga_id == entry["manga_id"],
                    ReadingProgress.chapter_id == entry["chapter_id"],
                )
            )
            record = result.scalar_one_or_none()
            if record is None:
                db.add(ReadingProgress(
                    user_id=user_id,
                    provider=entry["provider"],
                    manga_id=entry["manga_id"],
                    chapter_id=entry["chapter_id"],
                    last_page=entry.get("last_page", 1),
                    manga_title=entry.get("manga_title", ""),
                    chapter_title=entry.get("chapter_title", ""),
                ))
                restored += 1
            else:
                if entry.get("last_page", 1) > record.last_page:
                    record.last_page = entry["last_page"]
        except Exception:
            continue

    await db.commit()
    return {"restored": restored, "message": f"Restored {restored} history entries"}
