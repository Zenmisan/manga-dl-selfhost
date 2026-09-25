from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import get_settings
import logging
import socket

log = logging.getLogger(__name__)

settings = get_settings()

# Render Free Tier doesn't support IPv6, but Supabase resolves to it by default.
# The Transaction Pooler URL (port 6543) should resolve to IPv4 automatically.
# We use the 'psycopg' (v3) driver as it has superior support for PgBouncer.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    # Import all models to ensure Base.metadata is fully populated
    import app.models.manga
    import app.models.download
    import app.models.reading_progress
    import app.models.profiles
    import app.models.comment
    import app.models.manga_override
    import app.models.support
    import app.models.device

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _migrate_add_columns()


async def _migrate_add_columns():
    """Non-destructive column additions for existing databases."""
    is_sqlite = "sqlite" in settings.DATABASE_URL

    columns = [
        ("manga", "user_id", "VARCHAR"),
        ("manga", "chapters_json", "JSON DEFAULT '{}'"),
        ("manga", "last_synced", "TIMESTAMP"),
        ("manga", "subscribed", "BOOLEAN DEFAULT FALSE"),
        ("reading_progress", "manga_title", "VARCHAR"),
        ("reading_progress", "chapter_title", "VARCHAR"),
        ("reading_progress", "last_page", "INTEGER DEFAULT 1"),
        ("reading_progress", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("downloads", "user_id", "VARCHAR"),
        ("downloads", "file_size_bytes", "INTEGER DEFAULT 0"),
        ("downloads", "pinned", "BOOLEAN DEFAULT FALSE"),
        ("downloads", "last_page_read", "INTEGER DEFAULT 0"),
        ("profiles", "display_name", "VARCHAR"),
        ("profiles", "bio", "VARCHAR"),
        ("profiles", "avatar_url", "VARCHAR"),
        ("profiles", "pinned_badges", "JSON DEFAULT '[]'"),
        ("profiles", "liked_comments", "JSON DEFAULT '[]'"),
        ("comments", "display_name", "VARCHAR"),
        ("comments", "likes", "INTEGER DEFAULT 0"),
        ("comments", "updated_at", "TIMESTAMP"),
    ]

    for table, col, typedef in columns:
        try:
            async with engine.begin() as conn:
                if is_sqlite:
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}"))
                else:
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {typedef}"))
        except Exception as exc:
            # Column may already exist or table may not yet exist; safe to continue
            log.debug("Column migration skipped for %s.%s: %s", table, col, exc)

    log.info("DB column migration complete")

