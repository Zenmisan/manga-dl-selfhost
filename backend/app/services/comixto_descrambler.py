import io
import logging
from fastapi import HTTPException
from fastapi.responses import Response
from curl_cffi import requests as cffi_requests
from PIL import Image

log = logging.getLogger(__name__)

GRID_COLS = 5
GRID_ROWS = 5
NUM_TILES = GRID_COLS * GRID_ROWS

ENC_MULTIPLIER = 1000005
ENC_INCREMENT = 1234567891
LCG_MULTIPLIER = 1664525
LCG_INCREMENT = 1013904223


def _int32(n: int) -> int:
    """Truncate to signed 32-bit, matching Kotlin's Int arithmetic."""
    n = n & 0xFFFFFFFF
    return n if n < 0x80000000 else n - 0x100000000


def _next_xorshift(state: int) -> int:
    s = _int32(state)
    s = _int32(s ^ _int32(s << 13))
    s = _int32(s ^ (s >> 17 & 0x7FFF))
    s = _int32(s ^ _int32(s << 5))
    return s


def _build_order_xorshift(seed: int, n: int) -> list[int]:
    arr = list(range(n))
    state = _int32(seed | 1)
    for i in range(n - 1, 0, -1):
        state = _next_xorshift(state)
        j = (state & 0xFFFFFFFF) % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
    inverse = [0] * n
    for i, v in enumerate(arr):
        inverse[v] = i
    return inverse


def _build_order_lcg(seed: int, n: int) -> list[int]:
    arr = list(range(n))
    state = _int32(seed)
    for i in range(n - 1, 0, -1):
        state = _int32(_int32(state * LCG_MULTIPLIER) + LCG_INCREMENT)
        j = (state & 0xFFFFFFFF) % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
    inverse = [0] * n
    for i, v in enumerate(arr):
        inverse[v] = i
    return inverse


def _decode_with_lcg(data: bytearray, seed: int, length: int) -> bytearray:
    result = bytearray(data)
    state = _int32(seed)
    limit = min(len(result), length)
    for i in range(limit):
        state = _int32(_int32(state * ENC_MULTIPLIER) + ENC_INCREMENT)
        result[i] ^= (state >> 24) & 0xFF
    return result


def _decode_with_xorshift(data: bytearray, initial_state: int, length: int, high_byte: bool) -> bytearray:
    result = bytearray(data)
    state = _int32(initial_state)
    limit = min(len(result), length)
    for i in range(limit):
        state = _next_xorshift(state)
        key = (state >> 24) & 0xFF if high_byte else state & 0xFF
        result[i] ^= key
    return result


def _has_image_signature(data: bytes | bytearray) -> bool:
    if len(data) < 12:
        return False
    # JPEG
    if data[0] == 0xFF and data[1] == 0xD8:
        return True
    # PNG
    if data[0] == 0x89 and data[1] == 0x50 and data[2] == 0x4E and data[3] == 0x47:
        return True
    # WEBP
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return True
    return False


def _descramble_image(img: Image.Image, seed: int, algo: str | None) -> Image.Image:
    w, h = img.size
    tile_w = w // GRID_COLS
    tile_h = h // GRID_ROWS
    order = _build_order_xorshift(seed, NUM_TILES) if algo == "3" else _build_order_lcg(seed, NUM_TILES)
    out = Image.new(img.mode, img.size)
    for dst_idx in range(NUM_TILES):
        src_idx = order[dst_idx]
        src_col, src_row = src_idx % GRID_COLS, src_idx // GRID_COLS
        dst_col = dst_idx % GRID_COLS
        dst_row = dst_idx // GRID_COLS
        tile = img.crop((src_col * tile_w, src_row * tile_h, (src_col + 1) * tile_w, (src_row + 1) * tile_h))
        out.paste(tile, (dst_col * tile_w, dst_row * tile_h))
    return out


def _fetch_image(url: str, with_origin: bool) -> tuple[bytes, dict]:
    """Fetch image from Comix.to CDN, returning raw bytes and response headers."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://comix.to/",
    }
    if with_origin:
        headers["Origin"] = "https://comix.to"

    resp = cffi_requests.get(url, headers=headers, impersonate="chrome110", timeout=30)
    if resp.status_code == 404 and not with_origin:
        # Try alternate CDN paths
        for prefix in ["/si/", "/i/", "/sii/", "/ii/"]:
            import re
            alt = re.sub(r"/(?:si|i|sii|ii)/", prefix, url, count=1)
            if alt == url:
                break
            resp2 = cffi_requests.get(alt, headers=headers, impersonate="chrome110", timeout=30)
            if resp2.status_code == 200:
                return resp2.content, dict(resp2.headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"CDN returned {resp.status_code}")
    return resp.content, dict(resp.headers)


async def descramble_image_response(
    url: str,
    scramble_seed: int | None,
    scramble_algo: str | None,
    enc_seed: int | None,
    enc_len: int | None,
    enc_algo: str | None,
) -> Response:
    """
    Fetch a possibly-scrambled Comix.to image, descramble it, return clean JPEG.
    V3 (grid-scramble): server sends X-Scramble-Seed; no Origin header must be sent.
    Legacy (XOR): server sends X-Enc-Seed; Origin header must be present.
    """
    is_v3 = "v3" in url
    is_legacy_xor = not is_v3 and enc_seed is not None and enc_seed != 0

    try:
        raw_bytes, resp_headers = _fetch_image(url, with_origin=is_legacy_xor)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch image: {e}")

    # Read DRM headers from actual response (may differ from what JS knew)
    actual_enc_seed = enc_seed or (int(resp_headers.get("x-enc-seed", 0) or 0))
    actual_enc_len = enc_len or (int(resp_headers.get("x-enc-len", 0) or 0))
    actual_enc_algo = enc_algo or resp_headers.get("x-enc-algo")
    actual_scramble_seed = scramble_seed or (int(resp_headers.get("x-scramble-seed", 0) or 0))
    actual_scramble_algo = scramble_algo or resp_headers.get("x-scramble-algo")
    actual_scramble_grid = resp_headers.get("x-scramble-grid", "")

    needs_xor = actual_enc_seed and actual_enc_seed != 0 and actual_enc_len
    needs_grid = (
        actual_scramble_grid == "5x5" and
        actual_scramble_seed is not None and actual_scramble_seed != 0 and
        actual_scramble_algo in (None, "1", "2", "3")
    )

    if not needs_xor and not needs_grid:
        # No scrambling — just proxy it through
        content_type = resp_headers.get("content-type", "image/jpeg")
        return Response(content=raw_bytes, media_type=content_type)

    data = bytearray(raw_bytes)

    # Step 1: XOR decode
    if needs_xor:
        if actual_enc_algo == "2":
            seed32 = _int32(actual_enc_seed)
            candidates = [
                _decode_with_xorshift(data, _int32(seed32 | 1), actual_enc_len, False),
                _decode_with_xorshift(data, seed32, actual_enc_len, False),
                _decode_with_xorshift(data, _int32(seed32 | 1), actual_enc_len, True),
                _decode_with_lcg(data, seed32, actual_enc_len),
            ]
            decoded = next((c for c in candidates if _has_image_signature(c)), candidates[0])
        else:
            decoded = _decode_with_lcg(data, _int32(actual_enc_seed), actual_enc_len)
        data = decoded

    if not needs_grid:
        return Response(content=bytes(data), media_type="image/jpeg")

    # Step 2: Grid descramble via Pillow
    try:
        img = Image.open(io.BytesIO(bytes(data)))
        img = img.convert("RGB")
        descrambled = _descramble_image(img, _int32(actual_scramble_seed), actual_scramble_algo)
        out_buf = io.BytesIO()
        descrambled.save(out_buf, format="JPEG", quality=92)
        return Response(content=out_buf.getvalue(), media_type="image/jpeg")
    except Exception as e:
        log.error("Descramble failed for %s: %s", url, e)
        raise HTTPException(status_code=500, detail=f"Descramble error: {e}")
