import re
import time
import hashlib
import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from curl_cffi import requests
from app.providers import get_provider
from app.providers.komga import KomgaProvider
from app.providers.suwayomi import SuwayomiProvider
from app.services.js_extensions import (
    BUILT_IN_EXTENSIONS,
    KEIYOUSHI_INDEX,
    get_extension_code_by_pkg,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/sources", tags=["sources"])
public_router = APIRouter(prefix="/sources", tags=["sources"])

_market_cache: list[dict] | None = None
_market_cache_time: float = 0
MARKET_CACHE_TTL = 86400  # 24 hours


@router.get("/builtins")
async def list_builtins():
    """Return metadata for all built-in extensions."""
    data = [
        {
            "id": ext_id,
            "name": meta["name"],
            "lang": meta["lang"],
            "version": meta["version"],
            "icon": meta["icon"],
            "nsfw": meta["nsfw"],
            "builtin": True,
            "skip_proxy": meta["skip_proxy"],
            "type": meta.get("type", "manga"),
        }
        for ext_id, meta in BUILT_IN_EXTENSIONS.items()
    ]
    return JSONResponse(content=data, headers={"Cache-Control": "public, max-age=86400, stale-while-revalidate=86400"})


@router.get("/market")
async def list_market_sources():
    """Return built-in extensions + Keiyoushi community extensions."""
    global _market_cache, _market_cache_time
    now = time.time()
    if _market_cache is not None and (now - _market_cache_time < MARKET_CACHE_TTL):
        return JSONResponse(
            content=_market_cache,
            headers={"Cache-Control": "public, max-age=86400, stale-while-revalidate=86400"},
        )

    sources = [
        {
            "id": ext_id,
            "name": meta["name"],
            "version": meta["version"],
            "lang": meta["lang"],
            "icon": meta["icon"],
            "nsfw": meta["nsfw"],
            "builtin": True,
            "skip_proxy": meta["skip_proxy"],
            "type": meta.get("type", "manga"),
        }
        for ext_id, meta in BUILT_IN_EXTENSIONS.items()
        if meta.get("type") != "novel"
    ]

    try:
        response = requests.get(KEIYOUSHI_INDEX, impersonate="chrome110", timeout=5)
        if response.status_code == 200:
            data = response.json()
            _SENTINEL_NAMES = {"outdated app", "update to mihon", "update mihon", "app outdated"}
            builtin_ids = set(BUILT_IN_EXTENSIONS.keys())
            for ext in data:
                pkg = ext.get("pkg", "")
                simple_id = pkg.split(".")[-1]
                if simple_id in builtin_ids:
                    continue
                display_name = re.sub(r'^Tachiyomi:?\s*', '', ext.get("name", "")).strip()
                if any(display_name.lower() == s or display_name.lower().startswith(s) for s in _SENTINEL_NAMES):
                    continue
                sources.append({
                    "id": pkg,
                    "name": display_name,
                    "version": ext.get("version"),
                    "lang": ext.get("lang"),
                    "icon": f"https://raw.githubusercontent.com/keiyoushi/extensions/repo/icon/{pkg}.png",
                    "nsfw": ext.get("nsfw", 0) == 1,
                    "builtin": False,
                    "skip_proxy": False,
                })
    except Exception as e:
        log.warning("Keiyoushi market fetch failed (non-fatal): %s", e)

    _market_cache = sources
    _market_cache_time = now
    return JSONResponse(
        content=sources,
        headers={"Cache-Control": "public, max-age=86400, stale-while-revalidate=86400"},
    )


@router.get("/code/{pkg_id}")
async def get_extension_code(pkg_id: str, request: Request):
    """Return built-in JS extension code, or proxy from Keiyoushi for community extensions."""
    res = get_extension_code_by_pkg(pkg_id)
    if res:
        etag = '"' + hashlib.md5(res["code"].encode()).hexdigest()[:12] + '"'
        if request.headers.get("if-none-match") == etag:
            from fastapi.responses import Response
            return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "public, max-age=86400"})
        return JSONResponse(content=res, headers={"Cache-Control": "public, max-age=86400", "ETag": etag})
    raise HTTPException(status_code=404, detail="Extension code not found")


class KomgaConfig(BaseModel):
    base_url: str
    username: str = ""
    password: str = ""


class SuwayomiConfig(BaseModel):
    base_url: str


@router.post("/configure/komga")
async def configure_komga(config: KomgaConfig):
    provider = get_provider("komga")
    if not isinstance(provider, KomgaProvider):
        raise HTTPException(500, "Komga provider not registered")
    provider.configure(config.base_url, config.username, config.password)
    return {"status": "ok", "base_url": config.base_url}


@router.post("/configure/suwayomi")
async def configure_suwayomi(config: SuwayomiConfig):
    provider = get_provider("suwayomi")
    if not isinstance(provider, SuwayomiProvider):
        raise HTTPException(500, "Suwayomi provider not registered")
    provider.configure(config.base_url)
    return {"status": "ok", "base_url": config.base_url}


class ComixtoToken(BaseModel):
    token: str


class ComixtoCache(BaseModel):
    url: str
    data: dict | list


@public_router.post("/comixto/token")
async def set_comixto_token(body: ComixtoToken):
    """Update the comixto _= API token at runtime. No auth — called by browser userscript."""
    from app.services.proxy_service import set_runtime_token
    set_runtime_token("comixto", body.token.strip())
    return {"status": "ok", "token_length": len(body.token.strip())}


@public_router.post("/comixto/cache")
async def cache_comixto_response(body: ComixtoCache):
    """Store a comixto API response relayed by the browser userscript."""
    from app.services.proxy_service import cache_api_response
    cache_api_response(body.url, body.data)
    return {"status": "ok", "url": body.url}
