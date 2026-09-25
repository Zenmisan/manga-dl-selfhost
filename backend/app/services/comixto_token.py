"""
Manages the comixto _= token generation server (a Bun subprocess).

The Bun process loads secure-chunk.js once, then handles token requests
via HTTP on localhost:5175. Tokens are deterministic so we also cache
in Python to avoid round-trips on repeated chapter IDs.
"""
import asyncio
import logging
import os
import re
import shutil

import httpx

log = logging.getLogger(__name__)

_SERVER_PORT = 5175
_TOKEN_URL = f"http://127.0.0.1:{_SERVER_PORT}/token"
_PROXY_URL = f"http://127.0.0.1:{_SERVER_PORT}/proxy"
_SERVER_URL = _TOKEN_URL  # backwards compat alias
_SCRIPT = os.path.join(os.path.dirname(__file__), "comixto_token_server.mjs")

_proc: asyncio.subprocess.Process | None = None
_ready = asyncio.Event()
_lock = asyncio.Lock()
_cache: dict[str, str] = {}

# Only these paths get tokens
_CHAPTER_PATH_RE = re.compile(r".*/chapters/\d+$")


async def _start_server() -> None:
    global _proc
    bun = shutil.which("bun")
    if not bun:
        log.warning("comixto token server: bun not found — token generation disabled")
        return
    if not os.path.exists(_SCRIPT):
        log.warning("comixto token server: %s not found", _SCRIPT)
        return

    log.info("Starting comixto token server…")
    _ready.clear()
    _proc = await asyncio.create_subprocess_exec(
        bun, "run", _SCRIPT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    asyncio.create_task(_watch_stdout())
    asyncio.create_task(_drain_stderr())


async def _watch_stdout() -> None:
    if not _proc or not _proc.stdout:
        return
    async for line in _proc.stdout:
        text = line.decode().strip()
        if text.startswith("ready:"):
            log.info("comixto token server ready on port %s", text.split(":", 1)[1])
            _ready.set()


async def _drain_stderr() -> None:
    if not _proc or not _proc.stderr:
        return
    async for line in _proc.stderr:
        text = line.decode().strip()
        if text:
            log.debug("comixto-token-server: %s", text)


async def ensure_server() -> bool:
    """Start the token server if not already running. Returns True if ready."""
    global _proc
    async with _lock:
        if _proc is None or _proc.returncode is not None:
            await _start_server()

    if not _proc:
        return False

    try:
        await asyncio.wait_for(_ready.wait(), timeout=30)
        return True
    except asyncio.TimeoutError:
        log.error("comixto token server did not become ready in 30s")
        return False


async def get_token(url_path: str) -> str | None:
    """Return _= token for the given URL path, or None if unavailable."""
    if not _CHAPTER_PATH_RE.match(url_path):
        return None
    if url_path in _cache:
        return _cache[url_path]
    if not await ensure_server():
        return None
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(_TOKEN_URL, json={"path": url_path})
            resp.raise_for_status()
            token = resp.json().get("token")
            if token:
                _cache[url_path] = token
            return token
    except Exception as exc:
        log.debug("comixto token request failed for %s: %s", url_path, exc)
        return None


async def proxy_chapter(url: str, cookie: str | None = None) -> dict | list | None:
    """Fetch a comixto chapter URL via the token server: generates token, fetches, decrypts.

    Returns the decrypted JSON or None on failure.
    """
    if not await ensure_server():
        return None
    try:
        payload: dict = {"url": url}
        if cookie:
            payload["cookie"] = cookie
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(_PROXY_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                log.debug("comixto proxy error for %s: %s", url, data["error"])
                return None
            return data
    except Exception as exc:
        log.debug("comixto proxy request failed for %s: %s", url, exc)
        return None


def stop_server() -> None:
    if _proc and _proc.returncode is None:
        _proc.kill()
