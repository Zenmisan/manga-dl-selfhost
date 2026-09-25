import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.supabase_auth import get_current_user
from app.models.comment import Comment
from app.models.profiles import UserProfile

log = logging.getLogger(__name__)
router = APIRouter(prefix="/comments", tags=["comments"])


class PostComment(BaseModel):
    provider: str
    manga_id: str
    chapter_id: str | None = None
    parent_id: str | None = None
    body: str

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Comment body cannot be empty")
        if len(v) > 2000:
            raise ValueError("Comment must be 2000 characters or fewer")
        return v


class UpdateDisplayName(BaseModel):
    display_name: str

    @field_validator("display_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) > 50:
            raise ValueError("Display name must be 50 characters or fewer")
        return v


def _serialize(c: Comment, liked_ids: set[str]) -> dict:
    return {
        "id": c.id,
        "user_id": c.user_id,
        "username": c.username,
        "display_name": c.display_name or c.username,
        "provider": c.provider,
        "manga_id": c.manga_id,
        "chapter_id": c.chapter_id,
        "parent_id": c.parent_id,
        "body": c.body,
        "likes": c.likes,
        "liked": c.id in liked_ids,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


async def _get_liked_ids(user_id: str | None, db: AsyncSession) -> set[str]:
    if not user_id:
        return set()
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one_or_none()
    return set(profile.liked_comments or []) if profile else set()


@router.get("")
async def list_comments(
    provider: str = Query(...),
    manga_id: str = Query(...),
    chapter_id: str | None = Query(default=None),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List top-level comments for a manga or chapter. Replies are nested inside each comment."""
    q = (
        select(Comment)
        .where(
            Comment.provider == provider,
            Comment.manga_id == manga_id,
            Comment.chapter_id == chapter_id,
            Comment.parent_id == None,  # noqa: E711
        )
        .order_by(Comment.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    top_level = (await db.execute(q)).scalars().all()

    total = (await db.execute(
        select(func.count()).select_from(Comment).where(
            Comment.provider == provider,
            Comment.manga_id == manga_id,
            Comment.chapter_id == chapter_id,
            Comment.parent_id == None,  # noqa: E711
        )
    )).scalar_one()

    # Fetch replies for these comments
    parent_ids = [c.id for c in top_level]
    replies_map: dict[str, list[Comment]] = {pid: [] for pid in parent_ids}
    if parent_ids:
        reply_rows = (await db.execute(
            select(Comment).where(Comment.parent_id.in_(parent_ids)).order_by(Comment.created_at.asc())
        )).scalars().all()
        for r in reply_rows:
            if r.parent_id in replies_map:
                replies_map[r.parent_id].append(r)

    liked_ids: set[str] = set()

    result = []
    for c in top_level:
        d = _serialize(c, liked_ids)
        d["replies"] = [_serialize(r, liked_ids) for r in replies_map.get(c.id, [])]
        result.append(d)

    return {"comments": result, "total": total, "offset": offset, "limit": limit}


@router.get("/mine")
async def get_my_comments(
    limit: int = Query(default=10, le=50),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List recent comments posted by the current user."""
    q = (
        select(Comment)
        .where(Comment.user_id == user_id)
        .order_by(Comment.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(q)).scalars().all()
    liked_ids = await _get_liked_ids(user_id, db)
    return [_serialize(c, liked_ids) for c in rows]


@router.post("", status_code=201)
async def post_comment(
    body: PostComment,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Post a new comment or reply. Requires authentication."""
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=403, detail="Set a username before commenting.")

    if body.parent_id:
        parent = (await db.execute(select(Comment).where(Comment.id == body.parent_id))).scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent comment not found.")
        if parent.parent_id:
            raise HTTPException(status_code=400, detail="Cannot reply to a reply.")

    comment = Comment(
        id=str(uuid.uuid4()),
        user_id=user_id,
        username=profile.username,
        display_name=profile.display_name,
        provider=body.provider,
        manga_id=body.manga_id,
        chapter_id=body.chapter_id,
        parent_id=body.parent_id,
        body=body.body,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return _serialize(comment, set())


@router.post("/{comment_id}/like")
async def toggle_like(
    comment_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle like on a comment."""
    comment = (await db.execute(select(Comment).where(Comment.id == comment_id))).scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found.")

    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one_or_none()
    liked: list = list(profile.liked_comments or []) if profile else []

    if comment_id in liked:
        liked.remove(comment_id)
        comment.likes = max(0, comment.likes - 1)
        liked_now = False
    else:
        liked.append(comment_id)
        comment.likes += 1
        liked_now = True

    if profile:
        profile.liked_comments = liked
    await db.commit()
    return {"liked": liked_now, "likes": comment.likes}


@router.delete("/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete own comment."""
    comment = (await db.execute(select(Comment).where(Comment.id == comment_id))).scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found.")
    if comment.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your comment.")
    await db.delete(comment)
    await db.commit()


@router.get("/display-name")
async def get_display_name(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's display name."""
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one_or_none()
    return {"display_name": profile.display_name if profile else None, "username": profile.username if profile else None}


@router.patch("/display-name")
async def update_display_name(
    body: UpdateDisplayName,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update display name (can change freely, unlike username)."""
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
    profile.display_name = body.display_name
    await db.commit()
    return {"display_name": profile.display_name, "username": profile.username}
