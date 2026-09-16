from sqlalchemy import String, Text, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.database import Base


class MangaRecord(Base):
    __tablename__ = "manga"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # "{provider}:{manga_id}"
    provider: Mapped[str] = mapped_column(String, index=True)
    provider_manga_id: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    cover_url: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    genres: Mapped[list] = mapped_column(JSON, default=list)
    authors: Mapped[list] = mapped_column(JSON, default=list)
    url: Mapped[str] = mapped_column(String)
    subscribed: Mapped[bool] = mapped_column(default=False)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    chapters_json: Mapped[dict] = mapped_column(JSON, default=dict)  # {chapter_id: ChapterResult dict}
    last_synced: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
