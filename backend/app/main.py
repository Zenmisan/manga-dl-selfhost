from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
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
from app.api import manga, downloads, settings as settings_router, library, sources, auth, users, backup, support, comments as comments_router
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
    # Backend download queue temporarily disabled to conserve Render container memory.
    # Downloads are now processed client-side in the browser.
    # await download_queue.start()

    # Run provider validation at startup (non-blocking)
    async def validate_all():
        for p in list_providers():
            try:
                report = await p.validate()
                log.info("Provider %s health: %s", p.id, report.status.value)
            except Exception as exc:
                log.warning("Provider %s validation error: %s", p.id, exc)

    asyncio.create_task(validate_all())
    # start_sync_task()  # Temporarily disabled to prevent background downloads
    start_discovery_refresh()

    # Ensure Supabase storage bucket exists (no-op if credentials not set)
    from app.core.storage import ensure_bucket_exists
    asyncio.create_task(ensure_bucket_exists())

    # Pre-warm comixto token server (non-blocking — takes ~10s)
    from app.services.comixto_token import ensure_server as _ensure_token_server
    asyncio.create_task(_ensure_token_server())

    yield

    # Shutdown
    from app.services.comixto_token import stop_server as _stop_token_server
    _stop_token_server()
    stop_discovery_refresh()
    # stop_sync_task()
    # await download_queue.stop()
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

_cors_origin_regex = (
    r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|"
    r"capacitor://localhost|"
    r"tauri://localhost|"
    r"https?://tauri\.localhost|"
    r"https://[a-zA-Z0-9-]+\.(web\.app|firebaseapp\.com))$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.CORS_ORIGINS,
    allow_origin_regex=_cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def _global_exc_handler(request: Request, exc: Exception) -> JSONResponse:
    """Ensure CORS headers are present even on unhandled 500 errors."""
    import re
    origin = request.headers.get("origin", "")
    headers: dict[str, str] = {}
    if origin and (origin in _settings.CORS_ORIGINS or re.match(_cors_origin_regex, origin)):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"}, headers=headers)

api_deps = [Depends(verify_api_key)]
app.include_router(manga.router, prefix="/api", dependencies=api_deps)
app.include_router(downloads.router, prefix="/api", dependencies=api_deps)
app.include_router(settings_router.router, prefix="/api", dependencies=api_deps)
app.include_router(library.router, prefix="/api", dependencies=api_deps)
app.include_router(sources.router, prefix="/api", dependencies=api_deps)
# Public token sync endpoint (no auth — localhost-only, called by userscript)
from app.api.sources import public_router as sources_public_router
app.include_router(sources_public_router, prefix="/api")
app.include_router(auth.router, prefix="/api", dependencies=api_deps)
app.include_router(users.router, prefix="/api")  # Uses Supabase JWT auth, not API key
app.include_router(backup.router, prefix="/api")
app.include_router(support.router, prefix="/api")  # No auth — public contact form
app.include_router(comments_router.router, prefix="/api")  # Supabase JWT auth for write ops
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
