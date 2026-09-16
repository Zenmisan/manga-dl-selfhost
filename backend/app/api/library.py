import logging
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Response, Depends, UploadFile, File, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.database import get_db
from app.models.download import DownloadRecord
from app.core.supabase_auth import get_current_user
from app.services.archive_converter import (
    read_cbz_pages,
    extract_cbz_image_bytes,
    convert_cbz_to_pdf_stream,
    convert_cbz_to_epub_stream,
)
from app.services.library_service import (
    ensure_local_file,
    list_library_items,
    fetch_library_stats,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/library", tags=["library"])
settings = get_settings()


class LibraryItem(BaseModel):
    title: str
    files: list[str]
    chapters_downloading: int = 0
    chapters_failed: int = 0
    cover_url: str | None = None
    subscribed: bool = False
    total_chapters: int = 0
    provider: str | None = None
    provider_manga_id: str | None = None
    type: str = 'manga'


class ProgressUpdate(BaseModel):
    page: int


async def _assert_admin(request: Request):
    """Pass through for all users to allow public library access."""
    pass


@router.get("", response_model=list[LibraryItem])
@router.get("/", response_model=list[LibraryItem], include_in_schema=False)
async def list_library(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch the library for the authenticated user."""
    items = await list_library_items(db, user_id)
    return [LibraryItem(**item) for item in items]


@router.get("/file/{manga_title}/{filename}")
async def download_file(manga_title: str, filename: str, request: Request):
    """Serve the raw CBZ file for downloading."""
    await _assert_admin(request)
    file_path = await ensure_local_file(manga_title, filename)
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.comicbook+zip"
    )


@router.get("/read/{manga_title}/{filename}")
async def get_cbz_manifest(manga_title: str, filename: str, request: Request, db: AsyncSession = Depends(get_db)):
    """List all image files inside a CBZ and return saved reading progress."""
    await _assert_admin(request)
    file_path = await ensure_local_file(manga_title, filename)

    try:
        images = await read_cbz_pages(file_path)

        result = await db.execute(
            select(DownloadRecord.last_page_read)
            .where(DownloadRecord.manga_title == manga_title)
            .where(DownloadRecord.chapter_title.like(f"%{filename.split(' Ch.')[-1].replace('.cbz', '')}%"))
            .limit(1)
        )
        last_page = result.scalar_one_or_none() or 0

        return {
            "title": manga_title,
            "filename": filename,
            "pages": images,
            "last_page": last_page,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read CBZ: {e}")


@router.get("/image/{manga_title}/{filename}/{image_name:path}")
async def get_cbz_image(
    manga_title: str,
    filename: str,
    image_name: str,
    request: Request,
    upscale: bool = Query(False),
):
    """Extract and serve a single image from a CBZ file, with optional upscaling."""
    await _assert_admin(request)
    file_path = await ensure_local_file(manga_title, filename)

    try:
        content, media_type = await extract_cbz_image_bytes(file_path, image_name, upscale=upscale)
        return Response(content=content, media_type=media_type)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting image: {e}")


@router.get("/pdf/{manga_title}/{filename}")
async def convert_to_pdf(manga_title: str, filename: str, request: Request):
    """Losslessly convert a CBZ to PDF on the fly and stream it."""
    await _assert_admin(request)
    file_path = await ensure_local_file(manga_title, filename)

    try:
        pdf_stream = await convert_cbz_to_pdf_stream(file_path)
        pdf_filename = filename.replace('.cbz', '.pdf')
        return StreamingResponse(
            pdf_stream,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{pdf_filename}"'}
        )
    except Exception as e:
        log.error("PDF conversion failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {e}")


@router.get("/epub/{manga_title}/{filename}")
async def convert_to_epub(manga_title: str, filename: str, request: Request):
    """Convert a CBZ archive to EPUB3 on the fly and stream it."""
    await _assert_admin(request)
    file_path = await ensure_local_file(manga_title, filename)

    try:
        epub_stream = await convert_cbz_to_epub_stream(manga_title, file_path)
        epub_filename = filename.replace(".cbz", ".epub")
        return StreamingResponse(
            epub_stream,
            media_type="application/epub+zip",
            headers={"Content-Disposition": f'attachment; filename="{epub_filename}"'},
        )
    except Exception as e:
        log.error("EPUB conversion failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {e}")


@router.post("/progress/{manga_title}/{filename}")
async def update_progress(manga_title: str, filename: str, req: ProgressUpdate, request: Request, db: AsyncSession = Depends(get_db)):
    """Update reading progress for a specific chapter."""
    await _assert_admin(request)
    result = await db.execute(
        select(DownloadRecord)
        .where(DownloadRecord.manga_title == manga_title)
        .where(DownloadRecord.chapter_title.like(f"%{filename.split(' Ch.')[-1].replace('.cbz', '')}%"))
        .limit(1)
    )
    record = result.scalar_one_or_none()
    if record:
        record.last_page_read = req.page
        await db.commit()
        return {"status": "ok", "page": req.page}
    return {"status": "not_found"}


@router.post("/pin/{manga_title}/{filename}")
async def toggle_pin(manga_title: str, filename: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Toggle the pinned status of a chapter to prevent auto-deletion."""
    await _assert_admin(request)
    result = await db.execute(
        select(DownloadRecord)
        .where(DownloadRecord.manga_title == manga_title)
        .where(DownloadRecord.chapter_title.like(f"%{filename.split(' Ch.')[-1].replace('.cbz', '')}%"))
        .limit(1)
    )
    record = result.scalar_one_or_none()
    if record:
        record.pinned = not record.pinned
        await db.commit()
        return {"status": "ok", "pinned": record.pinned}
    return {"status": "not_found"}


MAX_UPLOAD_BYTES = 300 * 1024 * 1024  # 300 MB hard cap


@router.post("/upload")
async def upload_manga(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Upload a local ZIP/CBZ file to the cloud library."""
    await _assert_admin(request)
    if file.size and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 300 MB upload limit.")
    ext = Path(file.filename).suffix.lower()
    if ext not in ('.zip', '.cbz'):
        raise HTTPException(status_code=400, detail=f"Invalid format: {ext}")

    temp_id = str(uuid.uuid4())
    temp_path = Path(settings.CACHE_PATH) / f"upload_{temp_id}_{file.filename}"
    temp_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size = temp_path.stat().st_size
        manga_title = file.filename.replace('.cbz', '').replace('.zip', '')
        if " Ch." in manga_title:
            manga_title = manga_title.split(" Ch.")[0].strip()

        remote_path = f"{manga_title}/{file.filename}"
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY:
            from app.core.storage import upload_file, check_and_evict
            await check_and_evict(db, file_size)
            await upload_file(temp_path, remote_path)
            output_path = remote_path
        else:
            dest_path = Path(settings.LIBRARY_PATH) / manga_title / file.filename
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(temp_path, dest_path)
            output_path = str(dest_path)

        record = DownloadRecord(
            id=temp_id,
            manga_id=f"upload:{manga_title.lower().replace(' ', '-')}",
            chapter_id=temp_id,
            provider="upload",
            manga_title=manga_title,
            chapter_title=file.filename.replace('.cbz', '').replace('.zip', ''),
            chapter_number=0.0,
            status="done",
            progress=100,
            file_size_bytes=file_size,
            output_path=output_path,
            completed_at=datetime.utcnow(),
        )
        db.add(record)
        await db.commit()
        return {"status": "ok", "manga": manga_title}
    except Exception as e:
        log.exception("Upload failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path.exists(): temp_path.unlink()


@router.get("/stats")
async def get_library_stats(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """Aggregate reading statistics scoped to the authenticated user."""
    return await fetch_library_stats(db, user_id)
