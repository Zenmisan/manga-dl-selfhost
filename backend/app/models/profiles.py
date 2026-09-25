from sqlalchemy import String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.database import Base


class UserProfile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    bio: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    pinned_badges: Mapped[list] = mapped_column(JSON, default=list)  # list of badge ids
    liked_comments: Mapped[list] = mapped_column(JSON, default=list)  # list of comment ids
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
