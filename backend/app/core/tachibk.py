"""
Pure-Python Tachiyomi .tachibk decoder.
Format: gzip-compressed Protocol Buffers binary.
Schema derived from tachiyomi/app/.../data/backup/models/*.kt
"""
import gzip
import json
import logging
import re
import struct
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


# ── ProtoBuf wire-format decoder ──────────────────────────────────────────────

def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result, shift = 0, 0
    while True:
        b = data[pos]; pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7

def _decode_message(data: bytes) -> dict[int, list[Any]]:
    """Decode a raw protobuf message into {field_number: [values...]}."""
    fields: dict[int, list] = {}
    pos = 0
    length = len(data)
    while pos < length:
        tag, pos = _read_varint(data, pos)
        field_num = tag >> 3
        wire_type = tag & 0x07
        if wire_type == 0:          # varint
            val, pos = _read_varint(data, pos)
        elif wire_type == 1:        # 64-bit
            val = struct.unpack_from('<Q', data, pos)[0]; pos += 8
        elif wire_type == 2:        # length-delimited
            length_val, pos = _read_varint(data, pos)
            val = data[pos:pos + length_val]; pos += length_val
        elif wire_type == 5:        # 32-bit
            val = struct.unpack_from('<I', data, pos)[0]; pos += 4
        else:
            break
        fields.setdefault(field_num, []).append(val)
    return fields


def _str(fields: dict, num: int, default: str = '') -> str:
    vals = fields.get(num, [])
    if not vals:
        return default
    v = vals[0]
    return v.decode('utf-8', errors='replace') if isinstance(v, bytes) else str(v)

def _bool(fields: dict, num: int, default: bool = False) -> bool:
    vals = fields.get(num, [])
    return bool(vals[0]) if vals else default

def _int(fields: dict, num: int, default: int = 0) -> int:
    vals = fields.get(num, [])
    return int(vals[0]) if vals else default

def _float_field(fields: dict, num: int, default: float = 0.0) -> float:
    vals = fields.get(num, [])
    if not vals:
        return default
    v = vals[0]
    if isinstance(v, int):
        return struct.unpack('<f', struct.pack('<I', v))[0]
    return float(v)

def _msgs(fields: dict, num: int) -> list[bytes]:
    """Return all embedded message bytes for a repeated field."""
    return [v for v in fields.get(num, []) if isinstance(v, bytes)]


# ── Model parsers ─────────────────────────────────────────────────────────────

def _parse_chapter(raw: bytes) -> dict:
    f = _decode_message(raw)
    return {
        'url': _str(f, 1),
        'name': _str(f, 2),
        'scanlator': _str(f, 3) or None,
        'read': _bool(f, 4),
        'bookmark': _bool(f, 5),
        'last_page_read': _int(f, 6),
        'chapter_number': _float_field(f, 9),
        'source_order': _int(f, 10),
    }

def _parse_history(raw: bytes) -> dict:
    f = _decode_message(raw)
    return {
        'url': _str(f, 1),
        'last_read': _int(f, 2),
    }

def _parse_tracking(raw: bytes) -> dict:
    f = _decode_message(raw)
    return {
        'sync_id': _int(f, 1),
        'media_id': _int(f, 100) or _int(f, 3),
        'title': _str(f, 5),
        'last_chapter_read': _float_field(f, 6),
        'score': _float_field(f, 8),
        'status': _int(f, 9),
        'tracking_url': _str(f, 4),
    }

def _parse_manga(raw: bytes) -> dict:
    f = _decode_message(raw)
    return {
        'source': _int(f, 1),
        'url': _str(f, 2),
        'title': _str(f, 3),
        'artist': _str(f, 4) or None,
        'author': _str(f, 5) or None,
        'description': _str(f, 6) or None,
        'thumbnail_url': _str(f, 9) or None,
        'favorite': _bool(f, 100, True),
        'chapters': [_parse_chapter(c) for c in _msgs(f, 16)],
        'category_ids': list(f.get(17, [])),
        'tracking': [_parse_tracking(t) for t in _msgs(f, 18)],
        'history': [_parse_history(h) for h in _msgs(f, 104)],
    }

def _parse_category(raw: bytes) -> dict:
    f = _decode_message(raw)
    return {
        'name': _str(f, 1),
        'order': _int(f, 2),
    }

def _parse_source(raw: bytes) -> dict:
    f = _decode_message(raw)
    return {
        'name': _str(f, 1),
        'source_id': _int(f, 2),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def decode_tachibk(data: bytes) -> dict:
    """
    Decode a .tachibk file (gzip-compressed protobuf) into a plain dict
    compatible with our import API.
    Returns:
        {
          "manga": [...],
          "categories": [...],
          "sources": [...],
        }
    """
    # Detect and strip gzip
    if data[:2] == b'\x1f\x8b':
        data = gzip.decompress(data)

    root = _decode_message(data)

    manga_list = [_parse_manga(m) for m in _msgs(root, 1)]
    categories = [_parse_category(c) for c in _msgs(root, 2)]
    sources = [_parse_source(s) for s in _msgs(root, 101)]

    # Build category id → name map from list order
    cat_map = {i + 1: c['name'] for i, c in enumerate(categories)}

    # Build source id → name map
    source_map = {s['source_id']: s['name'] for s in sources if s.get('source_id')}

    # Enrich manga with resolved category names and source name
    for m in manga_list:
        m['category_names'] = [cat_map.get(cid, '') for cid in m.pop('category_ids', [])]
        m['source_name'] = source_map.get(m.get('source'), '')

    return {
        'manga': manga_list,
        'categories': categories,
        'sources': sources,
    }


TRACKER_SYNC_ID_MAP = {
    1: 'mal',
    2: 'anilist',
    3: 'kitsu',
    4: 'shikimori',
    5: 'bangumi',
    6: 'mangaupdates',
}

PROVIDER_KEYWORDS = [
    ("mangadex", "mangadex"),
    ("asura", "asurascans"),
    ("omega", "omegascans"),
    ("flame", "flamescans"),
    ("katana", "mangakatana"),
    ("kakalot", "mangakakalot"),
    ("manganato", "manganato"),
    ("nato", "manganato"),
    ("batoto", "bato"),
    ("bato", "bato"),
    ("pill", "mangapill"),
    ("tcb", "tcbscans"),
    ("mangahere", "mangahere"),
    ("webtoon", "webtoons"),
    ("mangaplus", "mangaplus"),
    ("komga", "komga"),
    ("suwayomi", "suwayomi"),
    ("royalroad", "royalroad"),
    ("scribblehub", "scribblehub"),
    ("novelbin", "novelbin"),
    ("novelfull", "novelfull"),
    ("wuxiaworld", "wuxiaworld"),
    ("lightnovelworld", "lightnovelworld"),
]


def resolve_provider(source_name: str, manga_url: str = "") -> str:
    s = (source_name or "").lower().strip()
    u = (manga_url or "").lower().strip()
    target = f"{s} {u}"
    for kw, prov in PROVIDER_KEYWORDS:
        if kw in target:
            return prov
    slug = re.sub(r'[^a-z0-9]', '', s)
    return slug if slug else "tachiyomi"


def clean_manga_id(url: str, provider: str = "") -> str:
    if not url:
        return "unknown"
    u = url.strip()
    if "://" in u:
        u = u.split("://", 1)[1]
        if "/" in u:
            u = "/" + u.split("/", 1)[1]
    u = u.split("?")[0].split("#")[0].strip("/")
    if provider == "mangadex":
        m = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', u, re.I)
        if m:
            return m.group(0).lower()
    for prefix in ("manga/", "series/", "title/", "comic/"):
        if u.startswith(prefix):
            u = u[len(prefix):]
            break
    return u.strip("/") or "unknown"


def clean_chapter_id(url: str, chapter_number: float = 0.0) -> str:
    if not url:
        return str(chapter_number) if chapter_number else "ch-1"
    u = url.strip().split("?")[0].split("#")[0].strip("/")
    if "/" in u:
        last_seg = u.split("/")[-1]
        if last_seg:
            return last_seg
    return u or (str(chapter_number) if chapter_number else "ch-1")


def parse_tachiyomi_backup(data: bytes, filename: str = "") -> dict:
    """
    Parse a Tachiyomi backup in either .tachibk (protobuf) or .json format.
    Returns normalized dict with 'manga', 'categories', 'sources'.
    """
    filename_lower = (filename or "").lower()
    is_json = filename_lower.endswith(".json") or (not data.startswith(b"\x1f\x8b") and data.strip().startswith(b"{"))

    if is_json:
        try:
            obj = json.loads(data.decode("utf-8", errors="replace"))
            manga_raw = obj.get("backupManga") or obj.get("manga") or obj.get("library") or []
            cats_raw = obj.get("backupCategories") or obj.get("categories") or []
            sources_raw = obj.get("backupSources") or obj.get("sources") or []

            categories = [
                {"name": c.get("name", ""), "order": c.get("order", i)}
                if isinstance(c, dict) else {"name": str(c), "order": i}
                for i, c in enumerate(cats_raw)
            ]
            sources = [
                {"name": s.get("name", ""), "source_id": s.get("sourceId") or s.get("source_id") or 0}
                if isinstance(s, dict) else {"name": str(s), "source_id": 0}
                for s in sources_raw
            ]
            source_map = {s["source_id"]: s["name"] for s in sources if s["source_id"]}
            cat_map = {i + 1: c["name"] for i, c in enumerate(categories)}

            manga_list = []
            for m in manga_raw:
                cat_ids = m.get("categories", []) or m.get("category_ids", [])
                cat_names = []
                for cid in cat_ids:
                    if isinstance(cid, str):
                        cat_names.append(cid)
                    elif isinstance(cid, int) and cid in cat_map:
                        cat_names.append(cat_map[cid])

                m_chapters = []
                for ch in m.get("chapters", []):
                    m_chapters.append({
                        "url": ch.get("url", ""),
                        "name": ch.get("name", ""),
                        "scanlator": ch.get("scanlator"),
                        "read": bool(ch.get("read", False)),
                        "bookmark": bool(ch.get("bookmark", False)),
                        "last_page_read": int(ch.get("lastPageRead", 0) or ch.get("last_page_read", 0)),
                        "chapter_number": float(ch.get("chapterNumber", 0.0) or ch.get("chapter_number", 0.0)),
                        "source_order": int(ch.get("sourceOrder", 0) or ch.get("source_order", 0)),
                    })

                m_tracking = []
                for tr in m.get("tracking", []):
                    m_tracking.append({
                        "sync_id": tr.get("syncId") or tr.get("sync_id", 0),
                        "media_id": tr.get("mediaId") or tr.get("media_id", 0),
                        "title": tr.get("title", ""),
                        "last_chapter_read": float(tr.get("lastChapterRead") or tr.get("last_chapter_read", 0.0)),
                        "score": float(tr.get("score", 0.0)),
                        "status": int(tr.get("status", 0)),
                        "tracking_url": tr.get("trackingUrl") or tr.get("tracking_url", ""),
                    })

                source_val = m.get("source", 0)
                source_name = source_map.get(source_val, "") or (str(source_val) if isinstance(source_val, str) else "")

                manga_list.append({
                    "source": source_val,
                    "source_name": source_name,
                    "url": m.get("url", ""),
                    "title": m.get("title", ""),
                    "artist": m.get("artist"),
                    "author": m.get("author"),
                    "description": m.get("description"),
                    "thumbnail_url": m.get("thumbnailUrl") or m.get("thumbnail_url"),
                    "favorite": bool(m.get("favorite", True)),
                    "chapters": m_chapters,
                    "category_names": cat_names,
                    "tracking": m_tracking,
                    "history": m.get("history", []),
                })

            return {
                "manga": manga_list,
                "categories": categories,
                "sources": sources,
            }
        except Exception as e:
            log.warning("Failed to parse Tachiyomi backup as JSON, trying protobuf: %s", e)

    return decode_tachibk(data)
