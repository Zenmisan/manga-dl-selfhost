from sqlalchemy import String, Text, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.database import Base


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String, primary_key=True)          # uuid
    user_id: Mapped[str] = mapped_column(String, index=True)
    username: Mapped[str] = mapped_column(String)                       # denormalized
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # Target — chapter_id=None means manga-level comment
    provider: Mapped[str] = mapped_column(String)
    manga_id: Mapped[str] = mapped_column(String)
    chapter_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # Threading — parent_id=None means top-level
    parent_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    body: Mapped[str] = mapped_column(Text)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_comments_target", "provider", "manga_id", "chapter_id"),
    )
