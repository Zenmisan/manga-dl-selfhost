"""
Downloads chapter images and packages them into CBZ archives.
"""
import asyncio
from curl_cffi.requests import AsyncSession
import zipfile
import os
import re
from pathlib import Path
import logging
from io import BytesIO
from xml.sax.saxutils import escape as xml_escape
from PIL import Image

log = logging.getLogger(__name__)


async def download_image(client: AsyncSession, url: str, dest: Path, filename: str):
    """Download a single image to dest/filename, descrambling it if metadata is present in the hash fragment."""
    import urllib.parse
    import json

    dest.mkdir(parents=True, exist_ok=True)
    out = dest / filename
    if out.exists():
        return

    # Parse and strip any '#' hash fragments from the URL.
    parts = url.split("#", 1)
    clean_url = parts[0]
    fragment = parts[1] if len(parts) > 1 else ""

    descramble_data = None
    if fragment:
        try:
            decoded_fragment = urllib.parse.unquote(fragment)
            if decoded_fragment.startswith("{"):
                data = json.loads(decoded_fragment)
                if (isinstance(data.get("tiles"), list) and 
                    isinstance(data.get("tileCols"), (int, float)) and 
                    isinstance(data.get("tileRows"), (int, float))):
                    descramble_data = {
                        "tiles": [int(x) for x in data["tiles"]],
                        "tileCols": int(data["tileCols"]),
                        "tileRows": int(data["tileRows"]),
                    }
        except Exception as e:
            log.warning("Failed to parse descramble fragment: %s", e)

    try:
        resp = await client.get(clean_url, timeout=30.0)
        # curl_cffi uses status_code
        if resp.status_code != 200:
            log.warning("Failed to download %s: Status %s", clean_url, resp.status_code)
            return

        content = resp.content

        # Reconstruct image if descramble metadata is present
        if descramble_data:
            try:
                img = Image.open(BytesIO(content))
                width, height = img.size

                cols = descramble_data["tileCols"]
                rows = descramble_data["tileRows"]
                tiles = descramble_data["tiles"]

                tile_w = width // cols
                tile_h = height // rows

                new_width = tile_w * cols
                new_height = tile_h * rows

                descrambled_img = Image.new(img.mode, (new_width, new_height))

                for w, j in enumerate(tiles):
                    src_col = w % cols
                    src_row = w // cols
                    dst_col = j % cols
                    dst_row = j // cols

                    box = (
                        src_col * tile_w,
                        src_row * tile_h,
                        (src_col + 1) * tile_w,
                        (src_row + 1) * tile_h
                    )
                    tile = img.crop(box)

                    dst_box = (
                        dst_col * tile_w,
                        dst_row * tile_h,
                        (dst_col + 1) * tile_w,
                        (dst_row + 1) * tile_h
                    )
                    descrambled_img.paste(tile, dst_box)

                fmt = img.format or "JPEG"
                out_buf = BytesIO()
                descrambled_img.save(out_buf, format=fmt)
                content = out_buf.getvalue()
                log.info("Successfully descrambled downloaded image %s", filename)
            except Exception as e:
                log.error("Failed to descramble image %s: %s", filename, e)

        out.write_bytes(content)
    except Exception as exc:
        log.warning("Failed to download %s: %s", url, exc)
        raise



def _safe_filename(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", s).strip()


def build_comic_info_xml(
    manga_title: str = "",
    chapter_title: str = "",
    chapter_number: float = 0,
    page_count: int = 0,
) -> str:
    num_str = f"{chapter_number:g}" if chapter_number else ""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ComicInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema">\n'
        f'  <Series>{xml_escape(manga_title)}</Series>\n'
        f'  <Title>{xml_escape(chapter_title)}</Title>\n'
        f'  <Number>{xml_escape(num_str)}</Number>\n'
        f'  <PageCount>{page_count}</PageCount>\n'
        '  <Manga>Yes</Manga>\n'
        '</ComicInfo>\n'
    )


def package_cbz(
    image_dir: Path,
    output_path: Path,
    manga_title: str = "",
    chapter_title: str = "",
    chapter_number: float = 0,
):
    """
    Compress images to WebP to save space and zip them into a CBZ at output_path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    images = sorted(
        [f for f in image_dir.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif")],
        key=lambda f: f.name,
    )
    if not images:
        log.warning("No images found in %s, skipping CBZ packaging", image_dir)
        return

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Embed ComicInfo.xml for Kavita/Komga/Paperback compatibility
        comic_info = build_comic_info_xml(
            manga_title=manga_title,
            chapter_title=chapter_title,
            chapter_number=chapter_number,
            page_count=len(images),
        )
        zf.writestr("ComicInfo.xml", comic_info.encode("utf-8"))

        for img_path in images:
            try:
                with Image.open(img_path) as img:
                    webp_buffer = BytesIO()
                    img.save(webp_buffer, format="WEBP", quality=75, method=4)
                    new_name = img_path.stem + ".webp"
                    zf.writestr(new_name, webp_buffer.getvalue())
            except Exception as e:
                log.error("Failed to process and compress %s: %s", img_path, e)
                zf.write(img_path, img_path.name)


async def download_chapter_to_cbz(
    provider_id: str,
    manga_title: str,
    chapter_title: str,
    chapter_number: float,
    page_urls: list[str],
    library_path: Path,
    cache_path: Path,
    on_progress=None,  # async callable(downloaded, total)
) -> tuple[Path, int]:
    """
    Download all pages of a chapter, compress them, and package into a CBZ.
    Returns a tuple of (path to the CBZ file, file size in bytes).
    """
    safe_title = _safe_filename(manga_title)
    ch_num = f"{chapter_number:06.1f}".rstrip("0").rstrip(".")
    cbz_name = f"{safe_title} Ch.{ch_num}.cbz"
    cbz_path = library_path / safe_title / cbz_name

    if cbz_path.exists():
        return cbz_path, cbz_path.stat().st_size

    tmp_dir = cache_path / "downloads" / provider_id / _safe_filename(f"{manga_title}-ch{chapter_number}")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    async with AsyncSession(
        impersonate="chrome110",
        allow_redirects=True,
        timeout=60.0,
    ) as client:
        for i, url in enumerate(page_urls, start=1):
            url_no_fragment = url.split("#")[0]
            ext = "." + url_no_fragment.split("?")[0].split(".")[-1].lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                ext = ".jpg"
            filename = f"{i:04d}{ext}"
            try:
                await download_image(client, url, tmp_dir, filename)
            except Exception as exc:
                log.warning("Failed to download page %d/%d (%s): %s — skipping", i, len(page_urls), url, exc)

            if on_progress:
                await on_progress(i, len(page_urls))

            await asyncio.sleep(0.05)  # polite delay between page downloads

    # Run blocking image compression and zip packaging in a thread
    await asyncio.to_thread(package_cbz, tmp_dir, cbz_path, manga_title, chapter_title, chapter_number)

    # Clean up temp images
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    file_size = cbz_path.stat().st_size if cbz_path.exists() else 0
    return cbz_path, file_size
