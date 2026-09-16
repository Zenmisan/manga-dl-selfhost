import os
import zipfile
import io
import re
import asyncio
from pathlib import Path
from fastapi import HTTPException
from PIL import Image

def natural_sort_key(s: str | int) -> list:
    """Sort strings with numbers in human order (1, 2, 10 instead of 1, 10, 2)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]


async def read_cbz_pages(file_path: Path) -> list[str]:
    """Read and list image files inside a CBZ archive."""
    def _read_zip():
        with zipfile.ZipFile(file_path, 'r') as zf:
            images = [
                name for name in zf.namelist() 
                if name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif'))
            ]
            return sorted(images, key=natural_sort_key)

    return await asyncio.to_thread(_read_zip)


async def extract_cbz_image_bytes(file_path: Path, image_name: str, upscale: bool = False) -> tuple[bytes, str]:
    """Extract a single image from a CBZ archive, with optional upscaling and media type resolution."""
    def _extract():
        with zipfile.ZipFile(file_path, 'r') as zf:
            if image_name not in zf.namelist():
                return None
            with zf.open(image_name) as img_file:
                return img_file.read()

    content = await asyncio.to_thread(_extract)
    if not content:
        raise HTTPException(status_code=404, detail="Image not found in archive")

    if upscale:
        from app.core.ai import upscale_image
        content = await upscale_image(content)

    ext = Path(image_name).suffix.lower()
    media_type_map = {
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    media_type = media_type_map.get(ext, "image/jpeg")

    return content, media_type


async def convert_cbz_to_pdf_stream(file_path: Path) -> io.BytesIO:
    """Losslessly convert a CBZ archive to PDF stream."""
    import img2pdf

    def _generate_pdf():
        with zipfile.ZipFile(file_path, 'r') as zf:
            images = sorted([
                name for name in zf.namelist()
                if name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif'))
            ], key=natural_sort_key)

            image_data = []
            for name in images:
                data = zf.open(name).read()
                if name.lower().endswith('.webp'):
                    buf = io.BytesIO(data)
                    with Image.open(buf) as img:
                        out = io.BytesIO()
                        img.convert('RGB').save(out, format='JPEG', quality=90)
                        data = out.getvalue()
                image_data.append(data)

            pdf_bytes = io.BytesIO()
            img2pdf.convert(image_data, outputstream=pdf_bytes)
            pdf_bytes.seek(0)
            return pdf_bytes

    return await asyncio.to_thread(_generate_pdf)


async def convert_cbz_to_epub_stream(manga_title: str, file_path: Path) -> io.BytesIO:
    """Convert a CBZ archive to EPUB3 stream."""
    def _generate_epub() -> io.BytesIO:
        with zipfile.ZipFile(file_path, "r") as cbz:
            images = sorted(
                [n for n in cbz.namelist() if n.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))],
                key=natural_sort_key,
            )

            epub_buf = io.BytesIO()
            with zipfile.ZipFile(epub_buf, "w") as epub:
                # mimetype — must be first and uncompressed
                mi = zipfile.ZipInfo("mimetype")
                mi.compress_type = zipfile.ZIP_STORED
                epub.writestr(mi, "application/epub+zip")

                epub.writestr("META-INF/container.xml", (
                    '<?xml version="1.0"?>'
                    '<container version="1.0" xmlns="urn:oasis:schemas:container">'
                    "<rootfiles>"
                    '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                    "</rootfiles></container>"
                ))

                manifest_items, spine_items, nav_items = [], [], []

                for idx, img_name in enumerate(images):
                    raw = cbz.open(img_name).read()

                    if img_name.lower().endswith(".webp"):
                        buf = io.BytesIO(raw)
                        with Image.open(buf) as img:
                            out = io.BytesIO()
                            img.convert("RGB").save(out, format="JPEG", quality=90)
                            raw = out.getvalue()
                        ext, mime = ".jpg", "image/jpeg"
                    else:
                        ext = os.path.splitext(img_name)[1].lower()
                        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif"}
                        mime = mime_map.get(ext, "image/jpeg")

                    img_id = f"img{idx:04d}"
                    page_id = f"page{idx:04d}"
                    img_rel = f"images/{img_id}{ext}"
                    page_rel = f"pages/{page_id}.xhtml"

                    epub.writestr(f"OEBPS/{img_rel}", raw)
                    epub.writestr(f"OEBPS/{page_rel}", (
                        '<?xml version="1.0" encoding="UTF-8"?>'
                        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">'
                        '<html xmlns="http://www.w3.org/1999/xhtml"><head>'
                        f"<title>Page {idx + 1}</title>"
                        "<style>body{margin:0;padding:0;background:#000;}"
                        "img{display:block;max-width:100%;height:auto;margin:0 auto;}</style>"
                        f"</head><body><img src=\"../{img_rel}\" alt=\"Page {idx + 1}\"/></body></html>"
                    ))

                    manifest_items.append(f'<item id="{img_id}" href="{img_rel}" media-type="{mime}"/>')
                    manifest_items.append(f'<item id="{page_id}" href="{page_rel}" media-type="application/xhtml+xml"/>')
                    spine_items.append(f'<itemref idref="{page_id}"/>')
                    nav_items.append(f'<li><a href="{page_rel}">Page {idx + 1}</a></li>')

                epub.writestr("OEBPS/content.opf", (
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">'
                    "<metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\">"
                    f"<dc:identifier id=\"uid\">{manga_title}</dc:identifier>"
                    f"<dc:title>{manga_title}</dc:title>"
                    "<dc:language>en</dc:language></metadata>"
                    "<manifest>"
                    + "".join(manifest_items)
                    + '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
                    "</manifest><spine>" + "".join(spine_items) + "</spine></package>"
                ))

                epub.writestr("OEBPS/nav.xhtml", (
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
                    f"<head><title>{manga_title}</title></head><body>"
                    '<nav epub:type="toc"><ol>' + "".join(nav_items) + "</ol></nav>"
                    "</body></html>"
                ))

            epub_buf.seek(0)
            return epub_buf

    return await asyncio.to_thread(_generate_epub)
