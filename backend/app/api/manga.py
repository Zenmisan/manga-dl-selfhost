import logging
import asyncio
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.supabase_auth import get_current_user, get_current_user_email, require_jwt_user
from app.config import get_settings
from app.services.proxy_service import (
    proxy_html_content,
    proxy_json_content,
    proxy_image_response,
)
from app.services.manga_service import (
    fetch_manga_updates,
    fetch_subscription_status,
    list_subscriptions,
    toggle_manga_subscription,
    migrate_manga_provider,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/manga", tags=["manga"])


async def _assert_admin(request: Request):
    """Allow if valid API key present, or if JWT email matches admin."""
    settings = get_settings()
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if settings.API_KEY and api_key == settings.API_KEY:
        return
    email = await get_current_user_email(request)
    if email != "zenmisan@gmail.com":
        raise HTTPException(status_code=403, detail="Library access is restricted to administrator.")


class SubscribeMeta(BaseModel):
    title: str = ""
    cover_url: str | None = None
    description: str | None = None
    status: str | None = None
    genres: list[str] = []
    authors: list[str] = []
    url: str = ""


class MigrationRequest(BaseModel):
    old_provider: str
    old_manga_id: str
    new_provider: str
    new_manga_id: str
    new_title: str | None = None
    new_cover_url: str | None = None


@router.api_route("/proxy/html", methods=["GET", "POST"])
async def proxy_html(request: Request, url: str = Query(...)):
    """Proxy HTML for extension Web Workers that can't bypass CORS."""
    body = None
    content_type = None
    if request.method == "POST":
        body = await request.body()
        content_type = request.headers.get("content-type")
    return await proxy_html_content(url, method=request.method, body=body, content_type=content_type)


@router.get("/proxy/json")
async def proxy_json(url: str = Query(...)):
    """Proxy a JSON API for JS extensions — bypasses CORS restrictions on third-party APIs."""
    return await proxy_json_content(url)


@router.get("/image-proxy")
async def proxy_image(url: str = Query(...)):
    """Proxy a remote manga page/cover image to avoid CORS and hotlink restrictions."""
    return await proxy_image_response(url)


@router.get("/descramble-proxy")
async def descramble_proxy(
    url: str = Query(...),
    seed: str | None = Query(default=None),
    algo: str | None = Query(default=None),
    enc_seed: str | None = Query(default=None, alias="encSeed"),
    enc_len: str | None = Query(default=None, alias="encLen"),
    enc_algo: str | None = Query(default=None, alias="encAlgo"),
):
    """Fetch a Comix.to scrambled image, apply XOR + grid descrambling, return clean JPEG."""
    from app.services.comixto_descrambler import descramble_image_response
    return await descramble_image_response(
        url=url,
        scramble_seed=int(seed) if seed else None,
        scramble_algo=algo,
        enc_seed=int(enc_seed) if enc_seed else None,
        enc_len=int(enc_len) if enc_len else None,
        enc_algo=enc_algo,
    )


@router.get("/updates")
async def get_manga_updates(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_jwt_user),
):
    """Return latest chapters from the authenticated user's subscribed manga."""
    return await fetch_manga_updates(db, user_id)


@router.post("/sync")
async def trigger_sync(request: Request):
    """Manually trigger one sync cycle for all subscribed manga."""
    await _assert_admin(request)
    from app.core.tasks import _sync_once
    asyncio.create_task(_sync_once())
    return {"status": "sync started"}


@router.get("/subscriptions")
async def get_all_subscriptions(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_jwt_user),
):
    """List subscribed manga for the authenticated user."""
    return await list_subscriptions(db, user_id)


@router.post("/subscriptions")
async def add_subscription(
    request: Request,
    meta: SubscribeMeta = SubscribeMeta(),
    user_id: str = Depends(require_jwt_user),
    db: AsyncSession = Depends(get_db),
):
    """Subscribe to a manga. Scoped to the authenticated user."""
    body = await request.json()
    provider_id = body.get("provider_id", "")
    manga_id = body.get("manga_id", "")
    if not provider_id or not manga_id:
        raise HTTPException(status_code=422, detail="provider_id and manga_id required")
    full_meta = {**meta.model_dump(), **body}
    status = await toggle_manga_subscription(provider_id, manga_id, full_meta, db, user_id=user_id)
    return {"subscribed": status}


@router.delete("/subscriptions/{provider_id}/{manga_id:path}")
async def remove_subscription(
    provider_id: str,
    manga_id: str,
    user_id: str = Depends(require_jwt_user),
    db: AsyncSession = Depends(get_db),
):
    """Unsubscribe from a manga. Scoped to the authenticated user."""
    status = await toggle_manga_subscription(provider_id, manga_id, {}, db, user_id=user_id)
    return {"subscribed": status}


@router.get("/subscription/{provider_id}/{manga_id:path}")
async def get_subscription_status(
    provider_id: str,
    manga_id: str,
    user_id: str = Depends(require_jwt_user),
    db: AsyncSession = Depends(get_db),
):
    """Get subscription status for this user."""
    record_id = f"{provider_id}:{manga_id}:{user_id}"
    from sqlalchemy import select
    from app.models.manga import MangaRecord
    result = await db.execute(select(MangaRecord).where(MangaRecord.id == record_id))
    record = result.scalar_one_or_none()
    return {"subscribed": bool(record and record.subscribed)}


@router.post("/subscribe/{provider_id}/{manga_id:path}")
async def toggle_subscribe(
    provider_id: str,
    manga_id: str,
    meta: SubscribeMeta = SubscribeMeta(),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle subscription for a manga. Scoped to the authenticated user."""
    status = await toggle_manga_subscription(provider_id, manga_id, meta.model_dump(), db, user_id=user_id)
    return {"subscribed": status}


@router.post("/migrate")
async def migrate_manga_source(req: MigrationRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Migrate manga from one source to another, preserving downloads and subscription."""
    await _assert_admin(request)
    new_id = await migrate_manga_provider(
        req.old_provider, req.old_manga_id, req.new_provider, req.new_manga_id, req.new_title, req.new_cover_url, db
    )
    return {"status": "migrated", "new_id": new_id}
