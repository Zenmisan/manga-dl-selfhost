import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import defer
from fastapi import HTTPException

from app.models.manga import MangaRecord

log = logging.getLogger(__name__)


async def list_subscriptions(db: AsyncSession, user_id: str) -> list[dict]:
    """Return subscribed manga records for a specific user."""
    result = await db.execute(
        select(MangaRecord)
        .options(defer(MangaRecord.chapters_json))
        .where(MangaRecord.subscribed == True, MangaRecord.user_id == user_id)
    )
    records = result.scalars().all()
    return [{"provider_id": r.provider, "manga_id": r.provider_manga_id, "title": r.title, "cover_url": r.cover_url} for r in records]


async def fetch_manga_updates(db: AsyncSession, user_id: str | None = None) -> list[dict]:
    """Fetch latest chapters from subscribed manga for a specific user."""
    query = select(MangaRecord).where(MangaRecord.subscribed == True)
    if user_id:
        query = query.where(MangaRecord.user_id == user_id)
    result = await db.execute(query)
    manga_list = result.scalars().all()

    updates = []
    for manga in manga_list:
        chapters_json = manga.chapters_json or {}
        if not isinstance(chapters_json, dict):
            continue
        chapter_list = list(chapters_json.values())
        chapter_list.sort(key=lambda c: c.get("number", 0) if isinstance(c, dict) else 0, reverse=True)
        for ch in chapter_list[:10]:
            if not isinstance(ch, dict):
                continue
            updates.append({
                "manga_title": manga.title,
                "manga_id": manga.provider_manga_id,
                "provider": manga.provider,
                "cover_url": manga.cover_url,
                "chapter_id": ch.get("id", ""),
                "chapter_title": ch.get("title", ""),
                "chapter_number": ch.get("number", 0),
                "published_at": ch.get("published_at", ""),
            })

    updates.sort(
        key=lambda u: (u.get("published_at") or ""),
        reverse=True,
    )
    return updates[:200]


async def fetch_subscription_status(provider_id: str, manga_id: str, email: str | None, db: AsyncSession) -> bool:
    """Check subscription status for a manga."""
    if email != "zenmisan@gmail.com":
        return False

    record_id = f"{provider_id}:{manga_id}"
    result = await db.execute(select(MangaRecord).where(MangaRecord.id == record_id))
    record = result.scalar_one_or_none()
    return record.subscribed if record else False


async def toggle_manga_subscription(
    provider_id: str,
    manga_id: str,
    meta: dict,
    db: AsyncSession,
    user_id: str = "local-api-key-user",
) -> bool:
    """Toggle subscription for a manga per-user, creating a record if needed."""
    record_id = f"{provider_id}:{manga_id}:{user_id}"
    result = await db.execute(select(MangaRecord).where(MangaRecord.id == record_id))
    record = result.scalar_one_or_none()

    if not record:
        title = meta.get("title", "")
        if not title:
            raise HTTPException(
                status_code=422,
                detail="Manga not found in library and no metadata provided. Supply title and other fields to create a new record."
            )
        record = MangaRecord(
            id=record_id,
            provider=provider_id,
            provider_manga_id=manga_id,
            title=title,
            cover_url=meta.get("cover_url"),
            description=meta.get("description"),
            status=meta.get("status"),
            genres=meta.get("genres", []),
            authors=meta.get("authors", []),
            url=meta.get("url", ""),
            subscribed=True,
            user_id=user_id,
        )
        db.add(record)
        await db.commit()
        return True

    record.subscribed = not record.subscribed
    await db.commit()
    return record.subscribed


async def migrate_manga_provider(
    old_provider: str,
    old_manga_id: str,
    new_provider: str,
    new_manga_id: str,
    new_title: str | None,
    new_cover_url: str | None,
    db: AsyncSession,
) -> str:
    """Migrate a manga record from one provider source to another."""
    old_id = f"{old_provider}:{old_manga_id}"
    result = await db.execute(select(MangaRecord).where(MangaRecord.id == old_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Manga not found in library")

    new_id = f"{new_provider}:{new_manga_id}"

    record.id = new_id
    record.provider = new_provider
    record.provider_manga_id = new_manga_id
    if new_title:
        record.title = new_title
    if new_cover_url:
        record.cover_url = new_cover_url

    await db.commit()
    return new_id
