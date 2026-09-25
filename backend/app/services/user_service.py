import logging
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, distinct, or_, and_

from app.models.reading_progress import ReadingProgress
from app.models.manga_override import MangaOverride
from app.models.profiles import UserProfile

log = logging.getLogger(__name__)


async def upsert_user_reading_progress(
    user_id: str,
    provider: str,
    manga_id: str,
    chapter_id: str,
    last_page: int,
    manga_title: str | None,
    chapter_title: str | None,
    db: AsyncSession,
) -> dict:
    """Save or update reading progress for a user."""
    result = await db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == user_id,
            ReadingProgress.provider == provider,
            ReadingProgress.manga_id == manga_id,
            ReadingProgress.chapter_id == chapter_id,
        )
    )
    record = result.scalar_one_or_none()
    if record:
        record.last_page = last_page
        record.updated_at = datetime.utcnow()
        if manga_title:
            record.manga_title = manga_title
        if chapter_title:
            record.chapter_title = chapter_title
    else:
        record = ReadingProgress(
            user_id=user_id,
            provider=provider,
            manga_id=manga_id,
            chapter_id=chapter_id,
            last_page=last_page,
            manga_title=manga_title,
            chapter_title=chapter_title,
        )
        db.add(record)
    await db.commit()
    return {"status": "ok", "last_page": last_page}


async def fetch_user_reading_history(user_id: str, limit: int, db: AsyncSession) -> list[dict]:
    """Fetch reading history records for a user."""
    result = await db.execute(
        select(ReadingProgress)
        .where(ReadingProgress.user_id == user_id)
        .order_by(ReadingProgress.updated_at.desc())
        .limit(limit)
    )
    records = result.scalars().all()
    return [
        {
            "provider": r.provider,
            "manga_id": r.manga_id,
            "chapter_id": r.chapter_id,
            "manga_title": r.manga_title or r.manga_id,
            "chapter_title": r.chapter_title or r.chapter_id,
            "last_page": r.last_page,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in records
    ]


async def clear_user_history(user_id: str, provider: str | None, manga_id: str | None, db: AsyncSession) -> dict:
    """Clear reading history for all manga or a specific series."""
    query = delete(ReadingProgress).where(ReadingProgress.user_id == user_id)
    if provider and manga_id:
        query = query.where(
            ReadingProgress.provider == provider,
            ReadingProgress.manga_id == manga_id,
        )
    await db.execute(query)
    await db.commit()
    return {"cleared": True}


async def fetch_user_reading_stats(user_id: str, db: AsyncSession) -> dict:
    """Aggregate user-specific reading statistics."""
    total_chapters = (await db.execute(
        select(func.count(ReadingProgress.chapter_id)).where(ReadingProgress.user_id == user_id)
    )).scalar() or 0

    total_manga = (await db.execute(
        select(func.count(distinct(ReadingProgress.manga_id))).where(ReadingProgress.user_id == user_id)
    )).scalar() or 0

    total_pages = (await db.execute(
        select(func.sum(ReadingProgress.last_page)).where(ReadingProgress.user_id == user_id)
    )).scalar() or 0

    cutoff_30 = datetime.utcnow() - timedelta(days=30)
    daily_rows = (await db.execute(
        select(
            func.date(ReadingProgress.updated_at).label("day"),
            func.count(ReadingProgress.chapter_id).label("count"),
        )
        .where(ReadingProgress.user_id == user_id)
        .where(ReadingProgress.updated_at >= cutoff_30)
        .group_by(func.date(ReadingProgress.updated_at))
        .order_by(func.date(ReadingProgress.updated_at))
    )).all()
    daily_reads = [{"day": str(r.day), "count": r.count} for r in daily_rows]

    cutoff_365 = datetime.utcnow() - timedelta(days=365)
    yearly_rows = (await db.execute(
        select(
            func.date(ReadingProgress.updated_at).label("day"),
            func.count(ReadingProgress.chapter_id).label("count"),
        )
        .where(ReadingProgress.user_id == user_id)
        .where(ReadingProgress.updated_at >= cutoff_365)
        .group_by(func.date(ReadingProgress.updated_at))
        .order_by(func.date(ReadingProgress.updated_at))
    )).all()
    yearly_reads = [{"day": str(r.day), "count": r.count} for r in yearly_rows]

    provider_rows = (await db.execute(
        select(ReadingProgress.provider, func.count(ReadingProgress.chapter_id).label("count"))
        .where(ReadingProgress.user_id == user_id)
        .group_by(ReadingProgress.provider)
        .order_by(func.count(ReadingProgress.chapter_id).desc())
    )).all()
    provider_breakdown = [{"provider": r.provider, "count": r.count} for r in provider_rows]

    active_days = {str(r.day) for r in yearly_rows}
    streak = 0
    check = datetime.utcnow().date()
    while str(check) in active_days:
        streak += 1
        check = check - timedelta(days=1)

    return {
        "total_chapters": total_chapters,
        "total_manga": total_manga,
        "total_pages": total_pages,
        "storage_bytes": 0,
        "daily_reads": daily_reads,
        "yearly_reads": yearly_reads,
        "daily_downloads": daily_reads,
        "yearly_downloads": yearly_reads,
        "provider_breakdown": provider_breakdown,
        "streak_days": streak,
    }


async def fetch_public_user_profile(identifier: str, db: AsyncSession) -> dict:
    """Fetch publicly shareable profile data by user_id or username."""
    clean_id = identifier.lstrip("@").strip()
    if not clean_id:
        raise HTTPException(status_code=404, detail="Reader profile not found.")

    profile = None
    try:
        res = await db.execute(select(UserProfile).where(UserProfile.user_id == clean_id))
        profile = res.scalar_one_or_none()
        if not profile:
            res = await db.execute(select(UserProfile).where(func.lower(UserProfile.username) == clean_id.lower()))
            profile = res.scalar_one_or_none()
    except Exception as exc:
        log.warning("UserProfile lookup failed (%s)", exc)

    if profile:
        target_user_id = profile.user_id
        username = profile.username
        display_name = profile.display_name or profile.username
        bio = getattr(profile, "bio", None) or ""
        avatar_url = getattr(profile, "avatar_url", None) or ""
    else:
        target_user_id = clean_id
        username = clean_id if len(clean_id) <= 30 and "-" not in clean_id else None
        display_name = username or f"Reader #{clean_id[:8].upper()}"
        bio = ""
        avatar_url = ""

    user_cond = or_(
        ReadingProgress.user_id == target_user_id,
        ReadingProgress.user_id == clean_id,
    ) if target_user_id != clean_id else (ReadingProgress.user_id == target_user_id)

    chapters_read = await db.scalar(
        select(func.count()).select_from(ReadingProgress).where(user_cond)
    ) or 0

    manga_result = await db.execute(
        select(ReadingProgress.manga_id, ReadingProgress.provider, ReadingProgress.manga_title)
        .where(user_cond)
        .distinct()
    )
    manga_rows = manga_result.all()
    manga_count = len(manga_rows)

    if profile is None and chapters_read == 0 and manga_count == 0 and clean_id != "local-api-key-user":
        raise HTTPException(status_code=404, detail="Reader profile not found.")

    recent_result = await db.execute(
        select(ReadingProgress)
        .where(user_cond)
        .order_by(ReadingProgress.updated_at.desc())
        .limit(10)
    )
    recent = recent_result.scalars().all()

    streak_result = await db.execute(
        select(func.date(ReadingProgress.updated_at))
        .where(user_cond)
        .distinct()
        .order_by(func.date(ReadingProgress.updated_at).desc())
    )
    streak_days_raw = [row[0] for row in streak_result.all()]
    streak = 0
    if streak_days_raw:
        today = datetime.utcnow().date()
        prev = today
        for d in streak_days_raw:
            day = d if isinstance(d, type(today)) else datetime.fromisoformat(str(d)).date()
            if (prev - day).days <= 1:
                streak += 1
                prev = day
            else:
                break

    return {
        "user_id": target_user_id,
        "username": username,
        "display_name": display_name,
        "bio": bio,
        "avatar_url": avatar_url,
        "pinned_badges": getattr(profile, "pinned_badges", []) or [],
        "chapters_read": chapters_read,
        "manga_count": manga_count,
        "streak_days": streak,
        "recent_activity": [
            {
                "manga_id": r.manga_id,
                "manga_title": r.manga_title or r.manga_id,
                "chapter_id": r.chapter_id,
                "chapter_title": r.chapter_title or r.chapter_id,
                "provider": r.provider,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in recent
        ],
    }


async def search_public_profiles(query: str, limit: int, db: AsyncSession) -> list[dict]:
    """Search user profiles by username or display name."""
    clean_q = query.strip().lower()
    if not clean_q:
        return []

    pattern = f"%{clean_q}%"
    try:
        stmt = (
            select(UserProfile)
            .where(
                or_(
                    func.lower(UserProfile.username).like(pattern),
                    func.lower(UserProfile.display_name).like(pattern),
                )
            )
            .limit(limit)
        )
        res = await db.execute(stmt)
        profiles = res.scalars().all()
    except Exception as exc:
        log.warning("search_public_profiles error: %s", exc)
        profiles = []

    results = []
    for p in profiles:
        read_count = await db.scalar(
            select(func.count()).select_from(ReadingProgress).where(
                or_(ReadingProgress.user_id == p.user_id, ReadingProgress.user_id == p.username)
            )
        ) or 0
        manga_cnt = await db.scalar(
            select(func.count(distinct(ReadingProgress.manga_id))).where(
                or_(ReadingProgress.user_id == p.user_id, ReadingProgress.user_id == p.username)
            )
        ) or 0
        results.append({
            "user_id": p.user_id,
            "username": p.username,
            "display_name": p.display_name or p.username,
            "bio": getattr(p, "bio", "") or "",
            "avatar_url": getattr(p, "avatar_url", "") or "",
            "chapters_read": read_count,
            "manga_count": manga_cnt,
        })
    return results


def compute_hunter_rank(score: int, rank: int) -> dict:
    """Determine Hunter Rank and tier based on score and rank standing."""
    if rank == 1 and score > 0:
        return {"rank_code": "MONARCH", "rank_name": "Shadow Monarch", "tier": "mythic"}
    elif score >= 15000:
        return {"rank_code": "S", "rank_name": "S-Rank Hunter", "tier": "diamond"}
    elif score >= 8000:
        return {"rank_code": "A", "rank_name": "A-Rank Hunter", "tier": "platinum"}
    elif score >= 4000:
        return {"rank_code": "B", "rank_name": "B-Rank Hunter", "tier": "gold"}
    elif score >= 1500:
        return {"rank_code": "C", "rank_name": "C-Rank Hunter", "tier": "silver"}
    elif score >= 500:
        return {"rank_code": "D", "rank_name": "D-Rank Hunter", "tier": "bronze"}
    else:
        return {"rank_code": "E", "rank_name": "E-Rank Novice", "tier": "bronze"}


async def fetch_readers_leaderboard(
    period: str = "all_time",
    limit: int = 50,
    db: AsyncSession = None,
) -> list[dict]:
    """
    Fetch global reader leaderboard ranked by Reader Score (EXP):
    Score = (chapters_read * 10) + (streak_days * 50) + (manga_count * 25).
    Periods supported: 'all_time', 'yearly', 'monthly', 'weekly'.
    """
    now = datetime.utcnow()
    time_filter = None
    if period == "weekly":
        time_filter = now - timedelta(days=7)
    elif period == "monthly":
        time_filter = now - timedelta(days=30)
    elif period == "yearly":
        time_filter = now - timedelta(days=365)

    try:
        profiles_res = await db.execute(select(UserProfile))
        profiles = profiles_res.scalars().all()
    except Exception as exc:
        log.warning("fetch_readers_leaderboard profile fetch error: %s", exc)
        profiles = []

    user_map: dict[str, dict] = {}
    for p in profiles:
        user_map[p.user_id] = {
            "user_id": p.user_id,
            "username": p.username,
            "display_name": p.display_name or p.username,
            "bio": getattr(p, "bio", "") or "",
            "avatar_url": getattr(p, "avatar_url", "") or "",
            "pinned_badges": getattr(p, "pinned_badges", []) or [],
        }

    try:
        progress_users_res = await db.execute(select(distinct(ReadingProgress.user_id)))
        for row in progress_users_res.all():
            uid = row[0]
            if uid and uid not in user_map:
                matched = any(p.username and p.username.lower() == uid.lower() for p in profiles)
                if not matched:
                    user_map[uid] = {
                        "user_id": uid,
                        "username": uid if len(uid) <= 24 and "-" not in uid else None,
                        "display_name": f"Reader #{uid[:8].upper()}",
                        "bio": "",
                        "avatar_url": "",
                        "pinned_badges": [],
                    }
    except Exception as exc:
        log.warning("fetch_readers_leaderboard progress query error: %s", exc)

    leaderboard = []
    for uid, udata in user_map.items():
        user_cond = or_(
            ReadingProgress.user_id == uid,
            ReadingProgress.user_id == (udata.get("username") or uid),
        )
        cond = and_(user_cond, ReadingProgress.updated_at >= time_filter) if time_filter else user_cond

        chapters_count = await db.scalar(
            select(func.count()).select_from(ReadingProgress).where(cond)
        ) or 0

        manga_cnt = await db.scalar(
            select(func.count(distinct(ReadingProgress.manga_id))).where(cond)
        ) or 0

        streak_result = await db.execute(
            select(func.date(ReadingProgress.updated_at))
            .where(cond)
            .distinct()
            .order_by(func.date(ReadingProgress.updated_at).desc())
        )
        streak_days_raw = [row[0] for row in streak_result.all()]
        streak = 0
        if streak_days_raw:
            today = now.date()
            prev = today
            for d in streak_days_raw:
                day = d if isinstance(d, type(today)) else datetime.fromisoformat(str(d)).date()
                if (prev - day).days <= 1:
                    streak += 1
                    prev = day
                else:
                    break

        score = (chapters_count * 10) + (streak * 50) + (manga_cnt * 25)

        leaderboard.append({
            "user_id": udata["user_id"],
            "username": udata["username"],
            "display_name": udata["display_name"],
            "bio": udata["bio"],
            "avatar_url": udata["avatar_url"],
            "pinned_badges": udata["pinned_badges"],
            "chapters_read": chapters_count,
            "manga_count": manga_cnt,
            "streak_days": streak,
            "score": score,
        })

    leaderboard.sort(
        key=lambda x: (x["score"], x["chapters_read"], x["streak_days"], x["manga_count"]),
        reverse=True,
    )

    result = []
    for idx, entry in enumerate(leaderboard[:limit], start=1):
        entry["rank"] = idx
        entry["hunter_rank"] = compute_hunter_rank(entry["score"], idx)
        result.append(entry)

    return result
