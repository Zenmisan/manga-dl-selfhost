import asyncio
import logging
import ipaddress
import json
import os
from functools import partial
from urllib.parse import urlparse
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from curl_cffi.requests import AsyncSession as CurlSession
import cloudscraper
from app.config import get_settings

log = logging.getLogger(__name__)

MAX_RETRIES = 2

_TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "runtime_tokens.json")
_TOKEN_FILE = os.path.normpath(_TOKEN_FILE)

# Runtime-settable token overrides — persisted to file so reloads don't clear them
_runtime_tokens: dict[str, str] = {}


def _load_tokens() -> None:
    try:
        if os.path.exists(_TOKEN_FILE):
            with open(_TOKEN_FILE) as f:
                _runtime_tokens.update(json.load(f))
    except Exception:
        pass


def _save_tokens() -> None:
    try:
        with open(_TOKEN_FILE, "w") as f:
            json.dump(_runtime_tokens, f)
    except Exception:
        pass


_load_tokens()


def set_runtime_token(site: str, token: str) -> None:
    _runtime_tokens[site] = token
    _save_tokens()


_CACHE_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "runtime_cache.json"))

# Persisted response cache: normalized URL → parsed JSON data
_response_cache: dict[str, any] = {}


def _load_cache() -> None:
    try:
        if os.path.exists(_CACHE_FILE):
            with open(_CACHE_FILE) as f:
                _response_cache.update(json.load(f))
            log.info("Loaded %d comixto cached responses from disk", len(_response_cache))
    except Exception:
        pass


def _save_cache() -> None:
    try:
        with open(_CACHE_FILE, "w") as f:
            json.dump(_response_cache, f)
    except Exception:
        pass


_load_cache()


def cache_api_response(url: str, data: any) -> None:
    """Store a comixto API response keyed by normalized URL (no _= param)."""
    _response_cache[url] = data
    _save_cache()


def _normalize_comixto_url(url: str) -> str:
    """Strip _= query param for cache lookup."""
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params.pop("_", None)
    new_query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=new_query))


def _find_cached_comixto(url: str) -> "dict | list | None":
    """Exact URL match first; fall back to same-path match (ignores query params)."""
    key = _normalize_comixto_url(url)
    if key in _response_cache:
        return _response_cache[key]
    # Path-only fallback: comixto's page may request same path with different params
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path
    netloc = parsed.netloc
    for cached_url, data in _response_cache.items():
        cp = urlparse(cached_url)
        if cp.netloc == netloc and cp.path == path:
            log.debug("comixto cache path-fallback hit: %s → %s", url, cached_url)
            return data
    return None

PRIVATE_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def _site_cookie(hostname: str) -> str | None:
    """Return stored auth cookie for known sites."""
    settings = get_settings()
    if "comix.to" in hostname:
        return settings.COMIXTO_COOKIE
    return None


async def _inject_api_token(url: str) -> str:
    """Append site-specific API token query param when available.

    For comixto, tries the live token server first (deterministic, path-derived),
    then falls back to the stored runtime token.
    """
    parsed = urlparse(url)
    if "comix.to" in (parsed.hostname or "") and "/api/v1/" in parsed.path:
        from app.services.comixto_token import get_token as _get_token
        token = await _get_token(parsed.path)
        if not token:
            token = _runtime_tokens.get("comixto") or get_settings().COMIXTO_API_TOKEN
        if token:
            sep = "&" if parsed.query else "?"
            return url + sep + "_=" + token
    return url


def _is_cf_challenge(html: str) -> bool:
    markers = ("Just a moment", "cf-browser-verification", "Checking your browser", "Enable JavaScript and cookies", "_cf_chl_opt")
    return any(m in html for m in markers)


def _cloudscraper_get(url: str, headers: dict) -> dict:
    scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
    resp = scraper.get(url, headers=headers, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    return {"html": resp.text, "url": resp.url}


def validate_proxy_url(url: str) -> None:
    """Sanitize and validate proxy target URL to prevent Server-Side Request Forgery (SSRF)."""
    if not url or not isinstance(url, str):
        raise HTTPException(status_code=400, detail="URL parameter must be a non-empty string.")

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Invalid URL scheme. Only HTTP and HTTPS are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="Invalid URL hostname.")

    host_lower = hostname.lower()
    if host_lower in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "169.254.169.254"):
        raise HTTPException(status_code=400, detail="Proxy requests to local loopback or metadata IP interfaces are forbidden.")

    try:
        ip = ipaddress.ip_address(host_lower)
        if any(ip in net for net in PRIVATE_NETWORKS):
            raise HTTPException(status_code=400, detail="Proxy requests to private network IP addresses are forbidden.")
    except ValueError:
        pass


async def proxy_html_content(
    url: str,
    method: str = "GET",
    body: bytes | None = None,
    content_type: str | None = None,
) -> dict:
    """Proxy HTML content for extensions unable to bypass CORS directly."""
    validate_proxy_url(url)
    parsed = urlparse(url)
    referer = f"{parsed.scheme}://{parsed.netloc}/"
    last_exc = None

    req_headers = {
        "Referer": referer,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    }
    if content_type:
        req_headers["Content-Type"] = content_type
    cookie = _site_cookie(parsed.hostname or "")
    if cookie:
        req_headers["Cookie"] = cookie

    ssl_verified = True
    for attempt in range(1 + MAX_RETRIES):
        try:
            async with CurlSession(impersonate="chrome120") as client:
                req_kwargs = dict(headers=req_headers, timeout=20.0, allow_redirects=True, verify=ssl_verified)
                if method.upper() == "POST":
                    resp = await client.post(url, data=body, **req_kwargs)
                else:
                    resp = await client.get(url, **req_kwargs)
                if resp.status_code not in (200, 206):
                    raise HTTPException(status_code=resp.status_code, detail=f"Upstream HTML error: {resp.status_code}")
                html = resp.text
                if _is_cf_challenge(html):
                    log.info("CF challenge detected for %s, retrying with cloudscraper", url)
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, partial(_cloudscraper_get, url, req_headers))
                return {"html": html, "url": str(resp.url)}
        except HTTPException:
            raise
        except Exception as exc:
            # Retry with SSL verification disabled on cert errors
            if ssl_verified and ("SSL" in str(exc) or "(60)" in str(exc) or "certificate" in str(exc).lower()):
                log.warning("SSL error for %s, retrying without verification", url)
                ssl_verified = False
                continue
            last_exc = exc
            if attempt < MAX_RETRIES:
                log.warning("HTML proxy retry %d for %s due to %s", attempt + 1, url, exc)
                await asyncio.sleep(0.5 * (attempt + 1))

    err_str = str(last_exc)
    log.error("HTML proxy failed for %s: %s", url, err_str)
    if "Could not resolve host" in err_str or "(6)" in err_str:
        raise HTTPException(status_code=502, detail=f"Could not resolve host: {parsed.netloc}. Check DNS or internet connection.")
    raise HTTPException(status_code=502, detail=f"HTML proxy failed: {err_str}")


async def proxy_json_content(url: str) -> dict | list:
    """Proxy JSON API responses for JS extensions."""
    parsed_pre = urlparse(url)
    if "comix.to" in (parsed_pre.hostname or "") and "/api/v1/" in parsed_pre.path:
        # Check userscript response cache first
        cached = _find_cached_comixto(url)
        if cached is not None:
            return cached
        # Use token server as full proxy: generates token + fetches + decrypts
        from app.services.comixto_token import proxy_chapter as _proxy_chapter
        cookie = _site_cookie(parsed_pre.hostname or "")
        data = await _proxy_chapter(url, cookie=cookie)
        if data is not None:
            return data
        # Fall through to legacy path if proxy_chapter unavailable

    url = await _inject_api_token(url)
    validate_proxy_url(url)
    parsed = urlparse(url)
    referer = f"{parsed.scheme}://{parsed.netloc}/"
    last_exc = None

    json_headers: dict[str, str] = {"Referer": referer, "Accept": "application/json"}
    cookie = _site_cookie(parsed.hostname or "")
    if cookie:
        json_headers["Cookie"] = cookie
        json_headers["X-Requested-With"] = "XMLHttpRequest"

    for attempt in range(1 + MAX_RETRIES):
        try:
            async with CurlSession(impersonate="chrome110") as client:
                resp = await client.get(
                    url,
                    headers=json_headers,
                    timeout=20.0,
                    allow_redirects=True,
                )
                if resp.status_code != 200:
                    raise HTTPException(status_code=resp.status_code, detail=f"Upstream JSON error: {resp.status_code}")
                return resp.json()
        except HTTPException:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                log.warning("JSON proxy retry %d for %s due to %s", attempt + 1, url, exc)
                await asyncio.sleep(0.5 * (attempt + 1))

    err_str = str(last_exc)
    log.error("JSON proxy failed for %s: %s", url, err_str)
    if "Could not resolve host" in err_str or "(6)" in err_str:
        raise HTTPException(status_code=502, detail=f"Could not resolve host: {parsed.netloc}. Check DNS or internet connection.")
    raise HTTPException(status_code=502, detail=f"JSON proxy failed: {err_str}")


async def proxy_image_response(url: str) -> StreamingResponse:
    """Proxy image content to bypass hotlinking restrictions."""
    validate_proxy_url(url)
    parsed = urlparse(url)
    referer = f"{parsed.scheme}://{parsed.netloc}/"
    last_exc = None

    for attempt in range(1 + MAX_RETRIES):
        try:
            async with CurlSession(impersonate="chrome110") as client:
                resp = await client.get(
                    url,
                    headers={
                        "Referer": referer,
                        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Cache-Control": "no-cache",
                    },
                    timeout=30.0,
                    allow_redirects=True,
                )
                if resp.status_code != 200:
                    log.warning("Image proxy upstream %s for %s", resp.status_code, url)
                    raise HTTPException(status_code=resp.status_code, detail=f"Upstream image error: {resp.status_code}")
                content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
                content = resp.content
                extra_headers: dict[str, str] = {
                    "Cache-Control": "public, max-age=86400, stale-while-revalidate=3600",
                    "Access-Control-Allow-Origin": "*",
                    "Content-Length": str(len(content)),
                }
                if cl := resp.headers.get("content-length"):
                    # Validate upstream claimed length matches what we actually got
                    if int(cl) != len(content):
                        log.warning("Image proxy incomplete: upstream claimed %s bytes, got %d for %s", cl, len(content), url)
                        raise ValueError(f"Incomplete image: expected {cl} bytes, received {len(content)}")
                return StreamingResponse(
                    iter([content]),
                    media_type=content_type,
                    headers=extra_headers,
                )
        except HTTPException:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                log.warning("Image proxy retry %d for %s due to %s", attempt + 1, url, exc)
                await asyncio.sleep(0.5 * (attempt + 1))

    err_str = str(last_exc)
    log.error("Image proxy failed for %s: %s", url, err_str)
    if "Could not resolve host" in err_str or "(6)" in err_str:
        raise HTTPException(status_code=502, detail=f"Could not resolve host: {parsed.netloc}. Check DNS or internet connection.")
    raise HTTPException(status_code=502, detail=f"Image proxy failed: {err_str}")
