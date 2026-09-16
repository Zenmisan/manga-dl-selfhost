import asyncio
import logging
import ipaddress
from urllib.parse import urlparse
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from curl_cffi.requests import AsyncSession as CurlSession

log = logging.getLogger(__name__)

MAX_RETRIES = 2

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


async def proxy_html_content(url: str) -> dict:
    """Proxy HTML content for extensions unable to bypass CORS directly."""
    validate_proxy_url(url)
    parsed = urlparse(url)
    referer = f"{parsed.scheme}://{parsed.netloc}/"
    last_exc = None

    for attempt in range(1 + MAX_RETRIES):
        try:
            async with CurlSession(impersonate="chrome110") as client:
                resp = await client.get(
                    url,
                    headers={"Referer": referer, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
                    timeout=20.0,
                    allow_redirects=True,
                )
                if resp.status_code != 200:
                    raise HTTPException(status_code=resp.status_code, detail=f"Upstream HTML error: {resp.status_code}")
                return {"html": resp.text, "url": str(resp.url)}
        except HTTPException:
            raise
        except Exception as exc:
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
    validate_proxy_url(url)
    parsed = urlparse(url)
    referer = f"{parsed.scheme}://{parsed.netloc}/"
    last_exc = None

    for attempt in range(1 + MAX_RETRIES):
        try:
            async with CurlSession(impersonate="chrome110") as client:
                resp = await client.get(
                    url,
                    headers={"Referer": referer, "Accept": "application/json"},
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
                content_type = resp.headers.get("content-type", "image/jpeg")
                return StreamingResponse(
                    iter([resp.content]),
                    media_type=content_type,
                    headers={
                        "Cache-Control": "public, max-age=86400",
                        "Access-Control-Allow-Origin": "*",
                    },
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
