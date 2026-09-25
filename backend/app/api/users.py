"""
Device session management and user reading progress / profile API.
"""
import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.device import UserDevice
from app.models.reading_progress import ReadingProgress
from app.models.profiles import UserProfile
from app.core.supabase_auth import get_current_user, get_current_user_email, get_optional_user
from app.services.device_service import register_user_device, forfeit_user_device
from app.services.user_service import (
    upsert_user_reading_progress,
    fetch_user_reading_history,
    clear_user_history,
    fetch_user_reading_stats,
    fetch_public_user_profile,
    search_public_profiles,
    fetch_readers_leaderboard,
)
from app.services.email_service import send_email, welcome_email

log = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


class DeviceRegisterRequest(BaseModel):
    device_name: str = "Unknown Device"


class ForfeitDeviceRequest(BaseModel):
    forfeit_device_id: str
    new_device_name: str = "Unknown Device"


class ReadingProgressUpsert(BaseModel):
    provider: str
    manga_id: str
    chapter_id: str
    last_page: int
    manga_title: str | None = None
    chapter_title: str | None = None


class ProfileSetup(BaseModel):
    username: str


@router.post("/device/register")
async def register_device(
    body: DeviceRegisterRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register this device for the current user. Enforces 3-device limit."""
    return await register_user_device(body.device_name, request, user_id, db)


@router.post("/device/forfeit")
async def forfeit_device(
    body: ForfeitDeviceRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Forfeit an existing device so a new one can be registered."""
    return await forfeit_user_device(
        body.forfeit_device_id, body.new_device_name, request, user_id, db
    )


@router.put("/reading-progress")
async def upsert_reading_progress(
    body: ReadingProgressUpsert,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await upsert_user_reading_progress(
        user_id, body.provider, body.manga_id, body.chapter_id, body.last_page, body.manga_title, body.chapter_title, db
    )


@router.get("/history")
async def get_reading_history(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, le=500),
):
    try:
        return await fetch_user_reading_history(user_id, limit, db)
    except Exception as exc:
        log.warning("History fetch failed for user %s: %s", user_id, exc)
        return []


@router.delete("/history")
async def clear_reading_history(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await clear_user_history(user_id, None, None, db)


@router.delete("/history/{provider}/{manga_id:path}")
async def clear_manga_history(
    provider: str,
    manga_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await clear_user_history(user_id, provider, manga_id, db)


@router.get("/reading-progress/{provider}/{manga_id:path}")
async def get_reading_progress(
    provider: str,
    manga_id: str,
    chapter_id: str = Query(...),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == user_id,
            ReadingProgress.provider == provider,
            ReadingProgress.manga_id == manga_id,
            ReadingProgress.chapter_id == chapter_id,
        )
    )
    record = result.scalar_one_or_none()
    return {"last_page": record.last_page if record else 1}


@router.get("/devices")
async def list_devices(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all devices for the current user."""
    result = await db.execute(select(UserDevice).where(UserDevice.user_id == user_id))
    devices = result.scalars().all()
    return [
        {
            "id": d.id,
            "name": d.device_name,
            "last_active": d.last_active.isoformat() if d.last_active else None,
            "locked_until": d.locked_until.isoformat() if d.locked_until else None,
        }
        for d in devices
    ]


@router.post("/profile/setup")
async def setup_profile(
    body: ProfileSetup,
    request: Request,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """One-time username setup. Username cannot be changed after setting."""
    import re
    username = body.username.strip().lower()
    if not re.match(r'^[a-z0-9_]{3,24}$', username):
        raise HTTPException(status_code=422, detail="Username must be 3–24 characters: letters, numbers, underscores only.")

    # Check if username is already taken (query only user_id to avoid querying unmigrated columns)
    try:
        taken = (await db.execute(select(UserProfile.user_id).where(UserProfile.username == username))).scalar_one_or_none()
        if taken and taken != user_id:
            raise HTTPException(status_code=409, detail="Username already taken.")

        # Check if current user already set up a profile
        existing = (await db.execute(select(UserProfile.user_id).where(UserProfile.user_id == user_id))).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Profile already set up. Username cannot be changed.")
    except HTTPException:
        raise
    except Exception as exc:
        log.warning("Pre-check failed in setup_profile (%s), attempting raw query", exc)
        await db.rollback()
        # Fallback to direct raw query in case schema cache is stale
        res = (await db.execute(text("SELECT user_id FROM profiles WHERE username = :un"), {"un": username})).scalar_one_or_none()
        if res and res != user_id:
            raise HTTPException(status_code=409, detail="Username already taken.")
        res_existing = (await db.execute(text("SELECT user_id FROM profiles WHERE user_id = :u"), {"u": user_id})).scalar_one_or_none()
        if res_existing:
            raise HTTPException(status_code=409, detail="Profile already set up. Username cannot be changed.")

    try:
        profile = UserProfile(user_id=user_id, username=username)
        db.add(profile)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        log.warning("Profile setup standard insert failed (%s), running safe column migration and retry", exc)
        try:
            # Auto-migrate missing columns in database if not yet applied
            await db.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS display_name VARCHAR"))
            await db.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS liked_comments JSON DEFAULT '[]'"))
            await db.commit()
            profile = UserProfile(user_id=user_id, username=username)
            db.add(profile)
            await db.commit()
        except Exception as exc2:
            await db.rollback()
            log.warning("Auto-migration fallback failed (%s), performing direct raw insert", exc2)
            await db.execute(
                text("INSERT INTO profiles (user_id, username, created_at) VALUES (:u, :un, NOW())"),
                {"u": user_id, "un": username}
            )
            await db.commit()

    user_email = await get_current_user_email(request)
    if user_email:
        subject, html = welcome_email(username)
        asyncio.create_task(send_email(user_email, subject, html))

    return {"username": username}


@router.get("/me")
async def get_my_profile(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return current user's profile."""
    try:
        username = (await db.execute(select(UserProfile.username).where(UserProfile.user_id == user_id))).scalar_one_or_none()
    except Exception as exc:
        log.warning("get_my_profile query failed (%s)", exc)
        try:
            username = (await db.execute(text("SELECT username FROM profiles WHERE user_id = :u"), {"u": user_id})).scalar_one_or_none()
        except Exception:
            username = None

    return {
        "user_id": user_id,
        "username": username,
        "profile_set": username is not None,
    }


@router.get("/me/stats")
async def get_my_reading_stats(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate reading statistics based on ReadingProgress."""
    return await fetch_user_reading_stats(user_id, db)


@router.get("/profile/{user_id}")
async def get_public_profile(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Return publicly shareable reading stats and metadata for a user."""
    actual_id = user_id
    if user_id.lower() == "me":
        auth_user_id = await get_optional_user(request)
        if auth_user_id and auth_user_id != "local-api-key-user":
            actual_id = auth_user_id
        else:
            raise HTTPException(status_code=401, detail="Authentication required to view /profile/me")

    return await fetch_public_user_profile(actual_id, db)


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    pinned_badges: list[str] | None = None


@router.get("/leaderboard")
async def get_readers_leaderboard(
    period: str = Query("all_time", regex="^(weekly|monthly|yearly|all_time)$"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Return global reader leaderboard for weekly, monthly, yearly, or all-time."""
    return await fetch_readers_leaderboard(period, limit, db)


@router.get("/search")
async def search_users(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Search user profiles by username or display name."""
    return await search_public_profiles(q, limit, db)


@router.put("/profile")
async def update_my_profile(
    body: ProfileUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update display name, bio, avatar, and pinned badges."""
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Set up username first.")

    if body.display_name is not None:
        profile.display_name = body.display_name.strip() or None
    if body.bio is not None:
        profile.bio = body.bio.strip() or None
    if body.avatar_url is not None:
        profile.avatar_url = body.avatar_url.strip() or None
    if body.pinned_badges is not None:
        profile.pinned_badges = [str(b) for b in body.pinned_badges[:4]]

    await db.commit()
    return {
        "user_id": profile.user_id,
        "username": profile.username,
        "display_name": profile.display_name,
        "bio": profile.bio,
        "avatar_url": profile.avatar_url,
        "pinned_badges": getattr(profile, "pinned_badges", []) or [],
    }


@router.get("/me/profile-slug")
async def get_or_create_profile_slug(
    user_id: str = Depends(get_current_user),
):
    """Return the shareable profile URL for the current user."""
    return {"url": f"/profile/{user_id}"}
