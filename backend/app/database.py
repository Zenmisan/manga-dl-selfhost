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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _migrate_add_columns()


async def _migrate_add_columns():
    """Non-destructive column additions for existing databases."""
    is_sqlite = "sqlite" in settings.DATABASE_URL

    async def _safe_add(conn, table: str, col: str, typedef: str):
        try:
            if is_sqlite:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}"))
            else:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {typedef}"))
        except Exception:
            pass  # column already exists

    async with engine.begin() as conn:
        await _safe_add(conn, "manga", "user_id", "VARCHAR")
        await _safe_add(conn, "downloads", "user_id", "VARCHAR")
    log.info("DB column migration complete")
