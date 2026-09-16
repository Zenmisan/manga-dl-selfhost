from sqlalchemy import String, Integer, Float, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.database import Base


class DownloadRecord(Base):
    __tablename__ = "downloads"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # uuid
    manga_id: Mapped[str] = mapped_column(String, index=True)   # "{provider}:{manga_id}"
    chapter_id: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String)
    manga_title: Mapped[str] = mapped_column(String)
    chapter_title: Mapped[str] = mapped_column(String)
    chapter_number: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="queued")
    # queued | downloading | packaging | done | failed
    progress: Mapped[int] = mapped_column(Integer, default=0)   # 0-100
    total_pages: Mapped[int] = mapped_column(Integer, default=0)
    downloaded_pages: Mapped[int] = mapped_column(Integer, default=0)
    output_path: Mapped[str | None] = mapped_column(String, nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    last_page_read: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
