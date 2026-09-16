"""
Device session management and user reading progress / profile API.
"""
import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.device import UserDevice
from app.models.reading_progress import ReadingProgress
from app.models.profiles import UserProfile
from app.core.supabase_auth import get_current_user, get_current_user_email
from app.services.device_service import register_user_device, forfeit_user_device
from app.services.user_service import (
    upsert_user_reading_progress,
    fetch_user_reading_history,
    clear_user_history,
    fetch_user_reading_stats,
    fetch_public_user_profile,
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
    return await fetch_user_reading_history(user_id, limit, db)


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

    existing = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Profile already set up. Username cannot be changed.")

    taken = (await db.execute(select(UserProfile).where(UserProfile.username == username))).scalar_one_or_none()
    if taken:
        raise HTTPException(status_code=409, detail="Username already taken.")

    profile = UserProfile(user_id=user_id, username=username)
    db.add(profile)
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
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one_or_none()
    return {
        "user_id": user_id,
        "username": profile.username if profile else None,
        "profile_set": profile is not None,
    }


@router.get("/me/stats")
async def get_my_reading_stats(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate reading statistics based on ReadingProgress."""
    return await fetch_user_reading_stats(user_id, db)


@router.get("/profile/{user_id}")
async def get_public_profile(user_id: str, db: AsyncSession = Depends(get_db)):
    """Return publicly shareable reading stats for a user."""
    return await fetch_public_user_profile(user_id, db)


@router.get("/me/profile-slug")
async def get_or_create_profile_slug(
    user_id: str = Depends(get_current_user),
):
    """Return the shareable profile URL for the current user."""
    return {"url": f"/profile/{user_id}"}
