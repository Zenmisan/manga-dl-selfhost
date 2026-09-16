import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.support import SupportTicket
from app.config import get_settings
from app.services.email_service import send_email, support_ticket_email

log = logging.getLogger(__name__)
router = APIRouter(prefix="/support", tags=["support"])


class TicketCreate(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    category: str = Field(default="general", max_length=50)
    message: str = Field(..., max_length=4000)
    user_id: str | None = Field(default=None, max_length=100)


@router.post("/ticket")
async def submit_ticket(body: TicketCreate, db: AsyncSession = Depends(get_db)):
    """Submit a support ticket. No auth required."""
    msg = body.message.strip()
    if not msg:
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    ticket = SupportTicket(
        name=body.name.strip() if body.name else None,
        email=body.email.strip() if body.email else None,
        category=body.category.strip() if body.category else "general",
        message=msg,
        user_id=body.user_id,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    settings = get_settings()
    if settings.RESEND_API_KEY:
        subject, html = support_ticket_email(
            ticket.id,
            ticket.name or "Anonymous",
            ticket.email,
            ticket.category,
            ticket.message,
        )
        asyncio.create_task(send_email(settings.SUPPORT_EMAIL, subject, html))

    return {"id": ticket.id, "status": "received"}
