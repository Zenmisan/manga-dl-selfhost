import logging
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import defer

from app.config import get_settings
from app.models.download import DownloadRecord
from app.models.manga import MangaRecord
from app.services.archive_converter import natural_sort_key

log = logging.getLogger(__name__)
settings = get_settings()


def _safe_join(base: Path, *parts: str) -> Path:
    """Join path parts and reject traversal attempts that escape base."""
    result = base
    for part in parts:
        result = result / part
    resolved = result.resolve()
    base_resolved = base.resolve()
    if not str(resolved).startswith(str(base_resolved) + "/") and resolved != base_resolved:
        raise HTTPException(status_code=400, detail="Invalid file path.")
    return result


async def ensure_local_file(manga_title: str, filename: str) -> Path:
    """Ensure the target CBZ file exists locally. Fetch from Supabase cache if needed."""
    lib_base = Path(settings.LIBRARY_PATH)
    cache_base = Path(settings.CACHE_PATH) / "library_cache"

    local_path = _safe_join(lib_base, manga_title, filename)
    if local_path.exists():
        return local_path

    cache_path = _safe_join(cache_base, manga_title, filename)
    if cache_path.exists():
        return cache_path

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY:
        from app.core.storage import download_file_to_cache
        remote_path = f"{manga_title}/{filename}"
        try:
            log.info("Downloading %s from Supabase to local cache...", remote_path)
            await download_file_to_cache(remote_path, cache_path)
            return cache_path
        except Exception as e:
            log.error("Failed to fetch from Supabase: %s", e)
            raise HTTPException(status_code=404, detail="File not found in cloud storage")

    raise HTTPException(status_code=404, detail="File not found locally and cloud storage is not configured")


async def list_library_items(db: AsyncSession, user_id: str) -> list[dict]:
    """Fetch library items belonging to user_id — downloads + subscriptions."""
    result = await db.execute(
        select(DownloadRecord)
        .where(DownloadRecord.user_id == user_id)
        .order_by(DownloadRecord.created_at.desc())
    )
    records = result.scalars().all()

    grouped: dict[str, dict] = {}
    for r in records:
        title = r.manga_title
        if title not in grouped:
            prov_manga_id = r.manga_id.split(":", 1)[1] if ":" in r.manga_id else r.manga_id
            grouped[title] = {
                "files": set(),
                "downloading": 0,
                "failed": 0,
                "cover_url": None,
                "subscribed": False,
                "provider": r.provider,
                "provider_manga_id": prov_manga_id,
            }

        if r.status == "done" and r.output_path:
            grouped[title]["files"].add(Path(r.output_path).name)
        elif r.status in ("queued", "downloading", "packaging"):
            grouped[title]["downloading"] += 1
        elif r.status == "failed":
            grouped[title]["failed"] += 1

    # Include subscribed manga even if no chapters downloaded yet
    # Defer chapters_json (can be MB-sized) — count keys via SQL instead
    sub_result = await db.execute(
        select(MangaRecord)
        .options(defer(MangaRecord.chapters_json))
        .where(MangaRecord.subscribed == True, MangaRecord.user_id == user_id)
    )
    for r in sub_result.scalars().all():
        chapter_count = 0
        if r.title not in grouped:
            grouped[r.title] = {
                "files": set(), "downloading": 0, "failed": 0,
                "cover_url": r.cover_url, "subscribed": True,
                "total_chapters": chapter_count,
                "provider": r.provider, "provider_manga_id": r.provider_manga_id,
            }
        else:
            grouped[r.title]["cover_url"] = r.cover_url
            grouped[r.title]["subscribed"] = True
            grouped[r.title]["total_chapters"] = chapter_count
            grouped[r.title]["provider"] = r.provider
            grouped[r.title]["provider_manga_id"] = r.provider_manga_id

    _novel_providers = {"royalroad", "scribblehub", "lightnovelworld", "wuxiaworld"}

    items = [
        {
            "title": title,
            "files": sorted(list(data["files"]), key=natural_sort_key),
            "chapters_downloading": data["downloading"],
            "chapters_failed": data["failed"],
            "cover_url": data.get("cover_url"),
            "subscribed": data.get("subscribed", False),
            "total_chapters": data.get("total_chapters", 0),
            "provider": data.get("provider"),
            "provider_manga_id": data.get("provider_manga_id"),
            "type": "novel" if data.get("provider") in _novel_providers else "manga",
        }
        for title, data in grouped.items()
        if data.get("subscribed") or len(data["files"]) > 0
    ]
    return sorted(items, key=lambda x: x["title"])


async def fetch_library_stats(db: AsyncSession, user_id: str = "local-api-key-user") -> dict:
    """Aggregate reading statistics and download activity history for one user."""
    def _base():
        return DownloadRecord.status == "done", DownloadRecord.user_id == user_id

    total_chapters = (await db.execute(
        select(func.count(DownloadRecord.id)).where(*_base())
    )).scalar() or 0

    total_manga = (await db.execute(
        select(func.count(distinct(DownloadRecord.manga_title))).where(*_base())
    )).scalar() or 0

    total_pages = (await db.execute(
        select(func.sum(DownloadRecord.total_pages)).where(*_base())
    )).scalar() or 0

    storage_bytes = (await db.execute(
        select(func.sum(DownloadRecord.file_size_bytes)).where(*_base())
    )).scalar() or 0

    # Downloads per day — last 30 days
    cutoff_30 = datetime.utcnow() - timedelta(days=30)
    daily_rows = (await db.execute(
        select(
            func.date(DownloadRecord.completed_at).label("day"),
            func.count(DownloadRecord.id).label("count"),
        )
        .where(*_base())
        .where(DownloadRecord.completed_at >= cutoff_30)
        .group_by(func.date(DownloadRecord.completed_at))
        .order_by(func.date(DownloadRecord.completed_at))
    )).all()
    daily_downloads = [{"day": str(r.day), "count": r.count} for r in daily_rows]

    # Downloads per day — last 365 days (for heatmap)
    cutoff_365 = datetime.utcnow() - timedelta(days=365)
    yearly_rows = (await db.execute(
        select(
            func.date(DownloadRecord.completed_at).label("day"),
            func.count(DownloadRecord.id).label("count"),
        )
        .where(*_base())
        .where(DownloadRecord.completed_at >= cutoff_365)
        .group_by(func.date(DownloadRecord.completed_at))
        .order_by(func.date(DownloadRecord.completed_at))
    )).all()
    yearly_downloads = [{"day": str(r.day), "count": r.count} for r in yearly_rows]

    # Provider breakdown
    provider_rows = (await db.execute(
        select(DownloadRecord.provider, func.count(DownloadRecord.id).label("count"))
        .where(*_base())
        .group_by(DownloadRecord.provider)
        .order_by(func.count(DownloadRecord.id).desc())
    )).all()
    provider_breakdown = [{"provider": r.provider, "count": r.count} for r in provider_rows]

    # Reading streak
    active_days = {r.day for r in daily_rows}
    streak = 0
    check = datetime.utcnow().date()
    while check in active_days:
        streak += 1
        check = check - timedelta(days=1)

    from app.config import get_settings as _gs2
    _s2 = _gs2()
    storage_limit_bytes = _s2.MAX_STORAGE_PER_USER_MB * 1024 * 1024

    return {
        "total_chapters": total_chapters,
        "total_manga": total_manga,
        "total_pages": total_pages,
        "storage_bytes": storage_bytes,
        "storage_limit_bytes": storage_limit_bytes,
        "daily_downloads": daily_downloads,
        "yearly_downloads": yearly_downloads,
        "provider_breakdown": provider_breakdown,
        "streak_days": streak,
    }
