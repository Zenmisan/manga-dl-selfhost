"""
Server-side discovery cache.

Pre-fetches popular/latest manga for all built-in sources and stores results in
an in-memory dict. Refreshed every 30 minutes via a background asyncio task.
"""
import asyncio
import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession as CurlSession

from app.services.js_extensions import BUILT_IN_EXTENSIONS

log = logging.getLogger(__name__)

_cache: dict[str, dict[str, list]] = {}
_task_handle: asyncio.Task | None = None

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


async def get_discovery(provider_ids: list[str]) -> dict[str, dict[str, list]]:
    """Return cached popular+latest for the requested providers."""
    return {pid: _cache.get(pid, {"popular": [], "latest": []}) for pid in provider_ids}


def start_discovery_refresh() -> None:
    global _task_handle
    _task_handle = asyncio.create_task(_refresh_loop())
    log.info("[Discovery] Background refresh task started")


def stop_discovery_refresh() -> None:
    global _task_handle
    if _task_handle:
        _task_handle.cancel()
        _task_handle = None


async def _refresh_loop() -> None:
    await warm_all()
    while True:
        await asyncio.sleep(30 * 60)
        await warm_all()


async def warm_all() -> None:
    """Fire scrapers for all built-in sources concurrently."""
    log.info("[Discovery] Warming cache for %d built-in sources...", len(BUILT_IN_EXTENSIONS))
    tasks: list[Any] = []
    for pid, meta in BUILT_IN_EXTENSIONS.items():
        if pid == "mangadex":
            tasks.append(_warm_mangadex())
        elif pid == "flamescans":
            tasks.append(_warm_flamecomics())
        elif pid == "asurascans":
            tasks.append(_warm_asurascans())
        elif meta.get("template") == "mangathemesia":
            tasks.append(_warm_mangathemesia(pid, meta["base_url"]))
        elif meta.get("template") == "madara":
            tasks.append(_warm_madara(pid, meta["base_url"]))
        elif pid == "comixto":
            tasks.append(_warm_comixto())
    results = await asyncio.gather(*tasks, return_exceptions=True)
    errors = sum(1 for r in results if isinstance(r, Exception))
    log.info("[Discovery] Cache warm complete — %d sources, %d errors", len(tasks), errors)


# ── AsuraScans ───────────────────────────────────────────────────────────────

async def _warm_asurascans() -> None:
    base = "https://asurascans.com"
    try:
        async with CurlSession(impersonate="chrome") as client:
            pop_r = await client.get(f"{base}/series-ranking", timeout=15)
            lat_r = await client.get(f"{base}/comics", timeout=15, params={"page": "1"})
        pop_r.raise_for_status()
        lat_r.raise_for_status()
        _cache["asurascans"] = {
            "popular": _parse_asurascans(pop_r.text, "ranking"),
            "latest": _parse_asurascans(lat_r.text, "latest"),
        }
        log.debug("[Discovery] asurascans: %d popular, %d latest", len(_cache["asurascans"]["popular"]), len(_cache["asurascans"]["latest"]))
    except Exception as exc:
        log.warning("[Discovery] asurascans failed: %s", exc)
        _cache.setdefault("asurascans", {"popular": [], "latest": []})


def _parse_asurascans(html: str, mode: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict] = []
    seen: set[str] = set()
    for a in soup.select("a[href*='/comics/']"):
        href = a.get("href", "")
        if "/chapter/" in href:
            continue
        slug = href.split("/comics/")[-1].rstrip("/")
        if not slug or slug in seen or re.match(r"^\d+$", slug):
            continue
        seen.add(slug)
        img = a.find("img")
        cover = img.get("src") if img else None
        if not cover or cover.startswith("data:") or len(cover) < 10:
            cover = None

        # Title extraction:
        # 1. img alt attribute (cleanest source on AsuraScans)
        alt = img.get("alt", "").strip() if img else ""
        if alt and not re.match(r"^[\d.]+$", alt):
            title = alt
        else:
            # 2. Text elements inside card (avoiding tabular-nums, rank numbers, ratings)
            title_el = (
                a.find(["h3", "h4", "h2"])
                or a.find("span", class_=lambda c: c and ("font-semibold" in c or "truncate" in c) and "tabular-nums" not in c)
            )
            raw_title = title_el.get_text(strip=True) if title_el else ""
            if raw_title and not re.match(r"^[\d.]+$", raw_title):
                title = raw_title
            else:
                # 3. Slug fallback: strip trailing 6-8 hex hash and title-case
                clean_slug = re.sub(r"-[a-f0-9]{6,8}$", "", slug)
                title = clean_slug.replace("-", " ").title()

        results.append({
            "id": slug,
            "title": title,
            "cover_url": cover,
            "provider": "asurascans",
            "url": f"https://asurascans.com/comics/{slug}",
            "status": None,
        })
        if len(results) >= 20:
            break
    return results


# ── MangaDex ─────────────────────────────────────────────────────────────────

async def _warm_mangadex() -> None:
    base = "https://api.mangadex.org"
    params_common: dict[str, Any] = {
        "limit": 20,
        "contentRating[]": "safe",
        "includes[]": "cover_art",
    }
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            pop_r = await client.get(f"{base}/manga", params={**params_common, "order[followedCount]": "desc"})
            lat_r = await client.get(f"{base}/manga", params={**params_common, "order[latestUploadedChapter]": "desc"})
        pop_r.raise_for_status()
        lat_r.raise_for_status()
        _cache["mangadex"] = {
            "popular": _parse_mangadex(pop_r.json()),
            "latest": _parse_mangadex(lat_r.json()),
        }
        log.debug("[Discovery] mangadex: %d popular, %d latest", len(_cache["mangadex"]["popular"]), len(_cache["mangadex"]["latest"]))
    except Exception as exc:
        log.warning("[Discovery] mangadex failed: %s", exc)
        _cache.setdefault("mangadex", {"popular": [], "latest": []})


def _parse_mangadex(data: dict) -> list[dict]:
    results = []
    for m in data.get("data", []):
        mid = m["id"]
        attrs = m.get("attributes", {})
        title = next(iter(attrs.get("title", {}).values()), "")
        cover_rel = next((r for r in m.get("relationships", []) if r["type"] == "cover_art"), None)
        cover_url = None
        if cover_rel and cover_rel.get("attributes"):
            fname = cover_rel["attributes"].get("fileName", "")
            cover_url = f"https://uploads.mangadex.org/covers/{mid}/{fname}.256.jpg" if fname else None
        results.append({
            "id": mid,
            "title": title,
            "cover_url": cover_url,
            "provider": "mangadex",
            "url": f"https://mangadex.org/title/{mid}",
            "status": attrs.get("status"),
        })
    return results


# ── Flame Comics (flamecomics.xyz — Next.js, __NEXT_DATA__ JSON) ─────────────

async def _warm_flamecomics() -> None:
    base = "https://flamecomics.xyz"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers=_site_headers(base)) as client:
            pop_r = await client.get(f"{base}/browse", params={"order": "trending"})
            lat_r = await client.get(f"{base}/browse", params={"order": "latest"})
        pop_r.raise_for_status()
        lat_r.raise_for_status()
        _cache["flamescans"] = {
            "popular": _parse_flamecomics(pop_r.text),
            "latest": _parse_flamecomics(lat_r.text),
        }
        log.debug("[Discovery] flamescans: %d popular, %d latest", len(_cache["flamescans"]["popular"]), len(_cache["flamescans"]["latest"]))
    except Exception as exc:
        log.warning("[Discovery] flamescans (flamecomics.xyz) failed: %s", exc)
        _cache.setdefault("flamescans", {"popular": [], "latest": []})


def _parse_flamecomics(html: str) -> list[dict]:
    import json as _json, re as _re
    nd_match = _re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, _re.DOTALL)
    if not nd_match:
        return []
    try:
        data = _json.loads(nd_match.group(1))
        series_list = data["props"]["pageProps"]["series"]
    except (KeyError, _json.JSONDecodeError):
        return []
    results = []
    for s in series_list[:20]:
        sid = s.get("series_id")
        title = s.get("title", "")
        if not sid or not title:
            continue
        cover = f"https://cdn.flamecomics.xyz/uploads/images/series/{sid}/{s.get('cover', 'thumbnail.webp')}"
        results.append({
            "id": str(sid),
            "title": title,
            "cover_url": cover,
            "provider": "flamescans",
            "url": f"https://flamecomics.xyz/series/{sid}",
            "status": s.get("status"),
        })
    return results


# ── Comixto ──────────────────────────────────────────────────────────────────

async def _warm_comixto() -> None:
    base = "https://comix.to"
    try:
        async with CurlSession(impersonate="chrome120") as client:
            resp = await client.get(base + "/", headers={**_HEADERS, "Referer": base + "/"}, timeout=20.0, allow_redirects=True)
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}")
        _cache["comixto"] = {
            "popular": _parse_comixto_popular(resp.text),
            "latest": _parse_comixto_latest(resp.text),
        }
        log.debug("[Discovery] comixto: %d popular, %d latest", len(_cache["comixto"]["popular"]), len(_cache["comixto"]["latest"]))
    except Exception as exc:
        log.warning("[Discovery] comixto failed: %s", exc)
        _cache.setdefault("comixto", {"popular": [], "latest": []})


def _parse_comixto_popular(html: str) -> list[dict]:
    import json as _json, re as _re
    ssr = _re.search(r'id="initial-data"[^>]*>([^<]+)', html)
    if not ssr:
        return []
    try:
        data = _json.loads(ssr.group(1))
    except _json.JSONDecodeError:
        return []
    for val in (data.get("queries") or {}).values():
        if isinstance(val, list) and val and isinstance(val[0], dict) and "hid" in val[0]:
            return [_comixto_item(m) for m in val if m.get("hid")]
    return []


def _parse_comixto_latest(html: str) -> list[dict]:
    import json as _json, re as _re
    ssr = _re.search(r'id="initial-data"[^>]*>([^<]+)', html)
    if not ssr:
        return []
    try:
        data = _json.loads(ssr.group(1))
    except _json.JSONDecodeError:
        return []
    for val in (data.get("queries") or {}).values():
        if isinstance(val, dict) and isinstance(val.get("items"), list):
            items = val["items"]
            if items and isinstance(items[0], dict) and "hid" in items[0]:
                return [_comixto_item(m) for m in items if m.get("hid")]
    return []


def _comixto_item(m: dict) -> dict:
    hid = m.get("hid", "")
    url = m.get("url") or f"/title/{hid}"
    poster = m.get("poster")
    cover = poster if isinstance(poster, str) else (
        (poster or {}).get("large") or (poster or {}).get("medium") or (poster or {}).get("small")
    )
    return {
        "id": hid,
        "title": m.get("title") or m.get("name") or "",
        "cover_url": cover,
        "provider": "comixto",
        "url": "https://comix.to" + url if url.startswith("/") else url,
        "status": m.get("status"),
    }


# ── MangaThemesia ─────────────────────────────────────────────────────────────

async def _warm_mangathemesia(pid: str, base_url: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers=_site_headers(base_url)) as client:
            pop_r = await client.get(f"{base_url}/manga/", params={"type": "", "status": "", "order": "popular"})
            lat_r = await client.get(f"{base_url}/manga/", params={"type": "", "status": "", "order": "update"})
        _cache[pid] = {
            "popular": _parse_mangathemesia(pop_r.text, pid),
            "latest": _parse_mangathemesia(lat_r.text, pid),
        }
        log.debug("[Discovery] %s (MangaThemesia): %d popular, %d latest", pid, len(_cache[pid]["popular"]), len(_cache[pid]["latest"]))
    except Exception as exc:
        log.warning("[Discovery] %s (MangaThemesia) failed: %s", pid, exc)
        _cache.setdefault(pid, {"popular": [], "latest": []})


def _parse_mangathemesia(html: str, provider: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for item in soup.select(".bsx")[:20]:
        a = item.select_one("a")
        if not a:
            continue
        url = a.get("href", "")
        title_el = item.select_one(".tt")
        img = item.select_one("img")
        cover = None
        if img:
            cover = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        slug = url.rstrip("/").split("/")[-1]
        results.append({
            "id": slug,
            "title": title_el.get_text(strip=True) if title_el else slug,
            "cover_url": cover,
            "provider": provider,
            "url": url,
            "status": None,
        })
    return results


# ── Madara (WordPress) ────────────────────────────────────────────────────────

def _site_headers(base_url: str) -> dict:
    return {**_HEADERS, "Referer": base_url + "/", "Origin": base_url}


async def _warm_madara(pid: str, base_url: str) -> None:
    headers = _site_headers(base_url)
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers=headers) as client:
            pop_r = await client.get(f"{base_url}/manga/", params={"m_orderby": "trending"})
            lat_r = await client.get(f"{base_url}/manga/", params={"m_orderby": "latest"})
        pop_r.raise_for_status()
        lat_r.raise_for_status()
        _cache[pid] = {
            "popular": _parse_madara_html(pop_r.text, pid),
            "latest": _parse_madara_html(lat_r.text, pid),
        }
        log.debug("[Discovery] %s (Madara): %d popular, %d latest", pid, len(_cache[pid]["popular"]), len(_cache[pid]["latest"]))
    except Exception as exc:
        log.warning("[Discovery] %s (Madara) failed: %s", pid, exc)
        _cache.setdefault(pid, {"popular": [], "latest": []})


def _parse_madara_html(html: str, provider: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    # GET browse pages use .page-item-detail; AJAX responses use .manga
    items = soup.select(".page-item-detail, .manga-item, .c-image-hover")[:20]
    if not items:
        # Some themes wrap items differently
        items = soup.select("div[class*='manga']")[:20]
    for item in items:
        a = item.select_one("a[href]")
        title_el = item.select_one(".post-title h3, .post-title h5, .post-title a, h3 a, h4 a")
        img = item.select_one("img")
        if not a:
            continue
        url = a.get("href", "")
        if not url or "wp-" in url:
            continue
        cover = None
        if img:
            cover = img.get("data-src") or img.get("data-lazy-src") or img.get("src")
        slug = url.rstrip("/").split("/")[-1]
        title_text = title_el.get_text(strip=True) if title_el else slug
        if not title_text:
            continue
        results.append({
            "id": slug,
            "title": title_text,
            "cover_url": cover,
            "provider": provider,
            "url": url,
            "status": None,
        })
    return results
