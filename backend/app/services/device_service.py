import hashlib
import uuid
import logging
from datetime import datetime, timedelta
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.device import UserDevice

log = logging.getLogger(__name__)
MAX_DEVICES = 3


def compute_device_fingerprint(request: Request, user_id: str) -> str:
    """Compute sha256 device fingerprint based on user-agent and IP."""
    ua = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else "unknown"
    raw = f"{user_id}:{ua}:{ip}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def register_user_device(
    device_name: str,
    request: Request,
    user_id: str,
    db: AsyncSession,
) -> dict:
    """Register user device enforcing max 3 active devices limit."""
    fingerprint = compute_device_fingerprint(request, user_id)

    result = await db.execute(
        select(UserDevice).where(
            UserDevice.user_id == user_id,
            UserDevice.device_fingerprint == fingerprint,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        if existing.locked_until and existing.locked_until > datetime.utcnow():
            remaining = (existing.locked_until - datetime.utcnow()).days + 1
            raise HTTPException(
                status_code=403,
                detail=f"This device is locked for {remaining} more day(s). It was forfeited to allow login on another device.",
            )
        existing.last_active = datetime.utcnow()
        existing.locked_until = None
        await db.commit()
        return {"status": "ok", "device_id": existing.id, "existing": True}

    active_result = await db.execute(
        select(UserDevice).where(UserDevice.user_id == user_id)
    )
    all_devices = active_result.scalars().all()
    active_devices = [d for d in all_devices if not d.locked_until or d.locked_until <= datetime.utcnow()]

    if len(active_devices) >= MAX_DEVICES:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "device_limit_reached",
                "message": f"Maximum {MAX_DEVICES} devices allowed. Choose one to forfeit.",
                "devices": [
                    {
                        "id": d.id,
                        "name": d.device_name,
                        "last_active": d.last_active.isoformat() if d.last_active else None,
                    }
                    for d in active_devices
                ],
            },
        )

    device = UserDevice(
        id=str(uuid.uuid4()),
        user_id=user_id,
        device_fingerprint=fingerprint,
        device_name=device_name,
    )
    db.add(device)
    await db.commit()
    return {"status": "ok", "device_id": device.id, "existing": False}


async def forfeit_user_device(
    forfeit_device_id: str,
    new_device_name: str,
    request: Request,
    user_id: str,
    db: AsyncSession,
) -> dict:
    """Forfeit an active device and register the current device."""
    result = await db.execute(
        select(UserDevice).where(
            UserDevice.id == forfeit_device_id,
            UserDevice.user_id == user_id,
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Device not found.")

    target.locked_until = datetime.utcnow() + timedelta(days=30)

    fingerprint = compute_device_fingerprint(request, user_id)
    device = UserDevice(
        id=str(uuid.uuid4()),
        user_id=user_id,
        device_fingerprint=fingerprint,
        device_name=new_device_name,
    )
    db.add(device)
    await db.commit()
    return {"status": "ok", "device_id": device.id, "forfeited_until": target.locked_until.isoformat()}
