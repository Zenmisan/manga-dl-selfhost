import re
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
    return JSONResponse(content=data, headers={"Cache-Control": "public, max-age=3600"})


@router.get("/market")
async def list_market_sources():
    """Return built-in extensions + Keiyoushi community extensions."""
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
    ]

    try:
        response = requests.get(KEIYOUSHI_INDEX, impersonate="chrome110", timeout=10)
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

    return sources


@router.get("/code/{pkg_id}")
async def get_extension_code(pkg_id: str, request: Request):
    """Return built-in JS extension code, or proxy from Keiyoushi for community extensions."""
    res = get_extension_code_by_pkg(pkg_id)
    if res:
        etag = '"' + hashlib.md5(res["code"].encode()).hexdigest()[:12] + '"'
        if request.headers.get("if-none-match") == etag:
            from fastapi.responses import Response
            return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "no-cache"})
        return JSONResponse(content=res, headers={"Cache-Control": "no-cache", "ETag": etag})
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
