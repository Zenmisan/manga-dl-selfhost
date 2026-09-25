"""
Backup API:
  POST /backup/import/tachibk       — parse .tachibk / .json → structured library + DB
  GET  /backup/export/manual        — export user data as manga-dl JSON backup
  POST /backup/import/manual        — import manga-dl JSON backup
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tachibk import (
    decode_tachibk,
    parse_tachiyomi_backup,
    resolve_provider,
    clean_manga_id,
    clean_chapter_id,
    TRACKER_SYNC_ID_MAP,
)
from app.core.supabase_auth import get_current_user
from app.database import get_db
from app.models.reading_progress import ReadingProgress
from app.models.manga import MangaRecord

log = logging.getLogger(__name__)
router = APIRouter(prefix="/backup", tags=["backup"])

BACKUP_VERSION = "1.0"


# ── Tachiyomi .tachibk / .json import ─────────────────────────────────────────

MAX_TACHIBK_BYTES = 50 * 1024 * 1024  # 50 MB — Tachiyomi backups are rarely > 5 MB


@router.post("/import/tachibk")
async def import_tachibk(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Accept a .tachibk or .json Tachiyomi / Mihon backup file.
    Parse library, categories, read chapters, bookmarks, and tracker links.
    If user is authenticated, persist subscriptions and reading progress to DB.
    Returns structured data for the frontend to merge into local storage.
    """
    if file.size and file.size > MAX_TACHIBK_BYTES:
        raise HTTPException(413, "File exceeds 50 MB limit.")
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(400, "Empty file")
    if len(raw) > MAX_TACHIBK_BYTES:
        raise HTTPException(413, "File exceeds 50 MB limit.")

    user_id: str | None = None
    try:
        user_id = await get_current_user(request)
    except Exception:
        user_id = None

    try:
        parsed = parse_tachiyomi_backup(raw, file.filename or "")
    except Exception as e:
        raise HTTPException(422, f"Failed to decode backup: {e}")

    manga_list = parsed.get("manga", [])
    cat_list = parsed.get("categories", [])

    raw_categories: list[str] = []
    for c in cat_list:
        name = c.get("name") if isinstance(c, dict) else str(c)
        if name and name.strip():
            raw_categories.append(name.strip())

    for m in manga_list:
        for cat_name in m.get("category_names", []):
            if cat_name and cat_name.strip():
                raw_categories.append(cat_name.strip())

    all_categories = list(dict.fromkeys(raw_categories))

    manga_categories: dict[str, list[str]] = {}
    read_tracking: dict[str, list[str]] = {}
    bookmarks: dict[str, list[str]] = {}
    tracker_links: dict[str, dict[str, Any]] = {}
    local_sub_meta: dict[str, dict[str, Any]] = {}

    for m in manga_list:
        raw_title = m.get("title") or ""
        title = raw_title.strip()
        if not title:
            continue

        source_name = m.get("source_name", "")
        url = m.get("url", "")
        provider = resolve_provider(source_name, url)
        manga_id = clean_manga_id(url, provider)
        composite_key = f"{provider}:{manga_id}"

        cover_url = m.get("thumbnail_url")
        desc = m.get("description")
        author = m.get("author")
        artist = m.get("artist")
        authors = [a.strip() for a in [author, artist] if a and a.strip()]

        cats = [c.strip() for c in m.get("category_names", []) if c and c.strip()]
        if cats:
            manga_categories[title.lower().strip()] = cats

        ch_list = m.get("chapters", [])
        read_ids: list[str] = []
        bm_ids: list[str] = []
        read_chapters_detail: list[dict[str, Any]] = []

        for ch in ch_list:
            ch_url = ch.get("url", "")
            ch_num = ch.get("chapter_number", 0.0)
            ch_id = clean_chapter_id(ch_url, ch_num)
            if ch.get("read"):
                read_ids.append(ch_id)
                read_chapters_detail.append({
                    "chapter_id": ch_id,
                    "last_page": ch.get("last_page_read", 1) or 1,
                    "chapter_title": ch.get("name") or f"Chapter {ch_num}",
                })
            if ch.get("bookmark"):
                bm_ids.append(ch_id)

        if read_ids:
            read_tracking[composite_key] = read_ids
        if bm_ids:
            bookmarks[composite_key] = bm_ids

        manga_trackers: dict[str, Any] = {}
        for tr in m.get("tracking", []):
            sync_id = tr.get("sync_id", 0)
            tracker_name = TRACKER_SYNC_ID_MAP.get(sync_id)
            media_id = tr.get("media_id", 0)
            if tracker_name and media_id:
                manga_trackers[tracker_name] = {
                    "id": media_id,
                    "title": tr.get("title") or title,
                    "score": float(tr.get("score", 0.0)),
                    "status": str(tr.get("status", 0)),
                    "progress": int(tr.get("last_chapter_read", 0.0)),
                }
        if manga_trackers:
            tracker_links[composite_key] = manga_trackers

        local_sub_meta[composite_key] = {
            "title": title,
            "cover_url": cover_url,
            "provider": provider,
            "mangaId": manga_id,
        }

        if user_id:
            try:
                db_record_id = f"{provider}:{manga_id}:{user_id}"
                res = await db.execute(select(MangaRecord).where(MangaRecord.id == db_record_id))
                rec = res.scalar_one_or_none()
                if rec is None:
                    new_rec = MangaRecord(
                        id=db_record_id,
                        provider=provider,
                        provider_manga_id=manga_id,
                        title=title,
                        cover_url=cover_url,
                        description=desc,
                        authors=authors,
                        url=url,
                        subscribed=True,
                        user_id=user_id,
                    )
                    db.add(new_rec)
                else:
                    rec.subscribed = True
                    if cover_url and not rec.cover_url:
                        rec.cover_url = cover_url
                    if title and not rec.title:
                        rec.title = title

                if read_chapters_detail:
                    rp_res = await db.execute(
                        select(ReadingProgress.chapter_id).where(
                            ReadingProgress.user_id == user_id,
                            ReadingProgress.provider == provider,
                            ReadingProgress.manga_id == manga_id,
                        )
                    )
                    existing_ch_ids = set(rp_res.scalars().all())
                    for ch_info in read_chapters_detail:
                        if ch_info["chapter_id"] not in existing_ch_ids:
                            db.add(ReadingProgress(
                                user_id=user_id,
                                provider=provider,
                                manga_id=manga_id,
                                chapter_id=ch_info["chapter_id"],
                                last_page=ch_info["last_page"],
                                manga_title=title,
                                chapter_title=ch_info["chapter_title"],
                            ))
                            existing_ch_ids.add(ch_info["chapter_id"])
            except Exception as e:
                log.warning("Failed to save manga %s to DB: %s", title, e)

    if user_id:
        try:
            await db.commit()
        except Exception as e:
            log.error("Failed to commit Tachiyomi import to DB: %s", e)
            await db.rollback()

    total_read = sum(len(c) for c in read_tracking.values())
    total_bm = sum(len(b) for b in bookmarks.values())

    return {
        "success": True,
        "imported_manga_count": len(local_sub_meta),
        "imported_categories_count": len(all_categories),
        "imported_chapters_count": total_read,
        "imported_bookmarks_count": total_bm,
        "categories": all_categories,
        "manga_categories": manga_categories,
        "read_tracking": read_tracking,
        "bookmarks": bookmarks,
        "tracker_links": tracker_links,
        "local_sub_meta": local_sub_meta,
        "local_subs": list(local_sub_meta.keys()),
        "manga": manga_list,
        "raw_categories": cat_list,
    }


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
