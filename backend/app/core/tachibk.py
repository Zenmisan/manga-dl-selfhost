"""
Pure-Python Tachiyomi .tachibk decoder.
Format: gzip-compressed Protocol Buffers binary.
Schema derived from tachiyomi/app/.../data/backup/models/*.kt
"""
import gzip
import struct
from dataclasses import dataclass, field
from typing import Any


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

    # Enrich manga with resolved category names
    for m in manga_list:
        m['category_names'] = [cat_map.get(cid, '') for cid in m.pop('category_ids', [])]

    return {
        'manga': manga_list,
        'categories': categories,
        'sources': sources,
    }
