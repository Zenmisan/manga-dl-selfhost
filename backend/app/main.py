from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
import asyncio

from app.config import get_settings
from app.database import init_db
from app.core.queue import download_queue
from app.core.tasks import start_sync_task, stop_sync_task
from app.core.discovery_cache import start_discovery_refresh, stop_discovery_refresh
from app.api import manga, downloads, settings as settings_router, library, sources, auth, users, backup, support
from app.api import discovery as discovery_router_module
from app.providers import list_providers
from app.core.security import verify_api_key

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await download_queue.start()

    # Run provider validation at startup (non-blocking)
    async def validate_all():
        for p in list_providers():
            try:
                report = await p.validate()
                log.info("Provider %s health: %s", p.id, report.status.value)
            except Exception as exc:
                log.warning("Provider %s validation error: %s", p.id, exc)

    asyncio.create_task(validate_all())
    start_sync_task()
    start_discovery_refresh()

    # Ensure Supabase storage bucket exists (no-op if credentials not set)
    from app.core.storage import ensure_bucket_exists
    asyncio.create_task(ensure_bucket_exists())

    yield

    # Shutdown
    stop_discovery_refresh()
    stop_sync_task()
    await download_queue.stop()
    for p in list_providers():
        try:
            await p.close()
        except Exception as exc:
            log.warning("[Shutdown] Provider %s close error: %s", getattr(p, "id", p), exc)


app = FastAPI(
    title="manga-dl",
    description="A self-hostable manga downloader with support for multiple sources",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "manga-dl API is running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "manga-dl"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_deps = [Depends(verify_api_key)]
app.include_router(manga.router, prefix="/api", dependencies=api_deps)
app.include_router(downloads.router, prefix="/api", dependencies=api_deps)
app.include_router(settings_router.router, prefix="/api", dependencies=api_deps)
app.include_router(library.router, prefix="/api", dependencies=api_deps)
app.include_router(sources.router, prefix="/api", dependencies=api_deps)
app.include_router(auth.router, prefix="/api", dependencies=api_deps)
app.include_router(users.router, prefix="/api")  # Uses Supabase JWT auth, not API key
app.include_router(backup.router, prefix="/api")
app.include_router(support.router, prefix="/api")  # No auth — public contact form
app.include_router(discovery_router_module.router, prefix="/api", dependencies=api_deps)

# Serve built frontend in production
_frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"

@app.get("/sitemap.xml", include_in_schema=False)
async def get_sitemap():
    sitemap_path = _frontend_dist / "sitemap.xml"
    if sitemap_path.exists():
        return FileResponse(sitemap_path, media_type="application/xml")
    raise HTTPException(status_code=404, detail="sitemap.xml not found")

@app.get("/robots.txt", include_in_schema=False)
async def get_robots():
    robots_path = _frontend_dist / "robots.txt"
    if robots_path.exists():
        return FileResponse(robots_path, media_type="text/plain")
    raise HTTPException(status_code=404, detail="robots.txt not found")

if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
