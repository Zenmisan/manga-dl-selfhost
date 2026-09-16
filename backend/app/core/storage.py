import logging
from pathlib import Path
from typing import Optional
from supabase import create_client, Client
from app.config import get_settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.download import DownloadRecord

log = logging.getLogger(__name__)
settings = get_settings()

_supabase_client: Optional[Client] = None

def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        url = settings.SUPABASE_URL
        key = settings.SUPABASE_SERVICE_KEY
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set to use cloud storage")
        _supabase_client = create_client(url, key)
    return _supabase_client

async def ensure_bucket_exists():
    """Ensure the target bucket exists on Supabase."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        log.warning("Supabase credentials not configured. Skipping bucket check.")
        return

    client = get_supabase_client()
    try:
        buckets = client.storage.list_buckets()
        bucket_names = [b.name for b in buckets]
        if settings.SUPABASE_BUCKET not in bucket_names:
            log.info(f"Creating bucket: {settings.SUPABASE_BUCKET}")
            # Create a public bucket so frontend can theoretically stream directly if needed
            client.storage.create_bucket(settings.SUPABASE_BUCKET, options={"public": True})
    except Exception as e:
        log.warning(f"Supabase storage bucket check skipped (connection unavailable): {e}")

async def upload_file(local_path: Path, remote_path: str) -> str:
    """Upload a file to Supabase storage and return its public URL."""
    client = get_supabase_client()
    with open(local_path, "rb") as f:
        # Overwrite if exists
        client.storage.from_(settings.SUPABASE_BUCKET).upload(
            file=f,
            path=remote_path,
            file_options={"cache-control": "3600", "upsert": "true"}
        )
    return client.storage.from_(settings.SUPABASE_BUCKET).get_public_url(remote_path)

async def check_and_evict(db: AsyncSession, new_file_size_bytes: int, user_id: str = "local-api-key-user"):
    """Evict oldest unpinned chapters for this user if their 200 MB quota would be exceeded."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return

    per_user_max = settings.MAX_STORAGE_PER_USER_MB * 1024 * 1024

    # Current usage for this user only
    result = await db.execute(
        select(func.sum(DownloadRecord.file_size_bytes))
        .where(DownloadRecord.status == "done")
        .where(DownloadRecord.output_path.isnot(None))
        .where(DownloadRecord.user_id == user_id)
    )
    current_size = result.scalar() or 0

    if current_size + new_file_size_bytes <= per_user_max:
        return

    log.info("User %s at %.1f MB — evicting oldest chapters to make room", user_id, current_size / 1024 / 1024)
    client = get_supabase_client()

    # Oldest unpinned chapters for this user
    result = await db.execute(
        select(DownloadRecord)
        .where(DownloadRecord.status == "done")
        .where(DownloadRecord.pinned == False)
        .where(DownloadRecord.user_id == user_id)
        .order_by(DownloadRecord.completed_at.asc())
    )
    records_to_evict = result.scalars().all()

    freed = 0
    for record in records_to_evict:
        if current_size - freed + new_file_size_bytes <= per_user_max:
            break
        if record.output_path:
            try:
                client.storage.from_(settings.SUPABASE_BUCKET).remove([record.output_path])
                freed += record.file_size_bytes
                record.status = "evicted"
                record.output_path = None
                log.info("Evicted: %s — %s (%.1f MB freed)", record.manga_title, record.chapter_title, freed / 1024 / 1024)
            except Exception as e:
                log.error("Failed to delete %s from Supabase: %s", record.output_path, e)

    await db.commit()

async def get_storage_used_bytes() -> int:
    """Query Supabase Storage directly for actual bucket usage in bytes."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return 0
    try:
        client = get_supabase_client()
        total = 0
        # List top-level folders (manga titles), then files inside each
        root_items = client.storage.from_(settings.SUPABASE_BUCKET).list("", {"limit": 1000})
        for item in root_items:
            if item.get("id") is None:
                # It's a folder — list its contents
                folder = item["name"]
                children = client.storage.from_(settings.SUPABASE_BUCKET).list(folder, {"limit": 1000})
                for child in children:
                    size = (child.get("metadata") or {}).get("size") or 0
                    total += size
            else:
                size = (item.get("metadata") or {}).get("size") or 0
                total += size
        return total
    except Exception as e:
        log.warning("Could not fetch Supabase bucket size: %s", e)
        return 0


async def download_file_to_cache(remote_path: str, local_cache_path: Path):
    """Download a file from Supabase to local ephemeral storage (for reading)."""
    if local_cache_path.exists():
        return  # Already cached

    local_cache_path.parent.mkdir(parents=True, exist_ok=True)
    client = get_supabase_client()
    
    with open(local_cache_path, "wb") as f:
        res = client.storage.from_(settings.SUPABASE_BUCKET).download(remote_path)
        f.write(res)
