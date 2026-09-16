import os
import json
import re
import logging
from pathlib import Path
from curl_cffi import requests

log = logging.getLogger(__name__)
KEIYOUSHI_INDEX = "https://raw.githubusercontent.com/keiyoushi/extensions/repo/index.min.json"

EXTENSIONS_DIR = Path(__file__).parent / "extensions"


def load_extension_script(filename: str) -> str:
    """Read JavaScript template file from extensions directory."""
    path = EXTENSIONS_DIR / filename
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        log.error("Failed to load JS extension script %s: %s", filename, e)
        return ""


# Built-in extensions registry
# Each entry has either:
#   "script": "filename.js"             — custom hand-written JS
#   "template": "madara"|"mangathemesia", "base_url": "https://..."  — generated from template
BUILT_IN_EXTENSIONS: dict[str, dict] = {
    # ── Custom JS ────────────────────────────────────────────
    "mangadex": {
        "script": "mangadex.js",
        "name": "MangaDex",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://mangadex.org/favicon.ico",
        "nsfw": False,
        "skip_proxy": True,
    },
    "omegascans": {
        "script": "omegascans.js",
        "name": "Omega Scans",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://omegascans.org/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "asurascans": {
        "script": "asurascans.js",
        "name": "Asura Scans",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://asurascans.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "mangakatana": {
        "script": "mangakatana.js",
        "name": "MangaKatana",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://mangakatana.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    # ── Madara (WordPress) ────────────────────────────────────
    "manhuahot": {
        "template": "madara",
        "base_url": "https://manhuahot.com",
        "name": "ManhuaHot",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://manhuahot.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "manhwatop": {
        "template": "madara",
        "base_url": "https://manhwatop.com",
        "name": "ManhwaTop",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://manhwatop.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "manhwaget": {
        "template": "madara",
        "base_url": "https://manhwaget.com",
        "name": "ManhwaGet",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://manhwaget.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "s2manga": {
        "template": "madara",
        "base_url": "https://s2read.com",
        "name": "S2Manga",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://s2read.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "mangadrama": {
        "template": "madara",
        "base_url": "https://mangadrama.com",
        "name": "MangaDrama",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://mangadrama.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "mangagg": {
        "template": "madara",
        "base_url": "https://mangagg.com",
        "name": "MangaGG",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://mangagg.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "lhtranslation": {
        "template": "madara",
        "base_url": "https://lhtranslation.net",
        "name": "LHTranslation",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://lhtranslation.net/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "mangafree": {
        "template": "madara",
        "base_url": "https://mangafree.info",
        "name": "MangaFree",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://mangafree.info/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "pawmanga": {
        "template": "madara",
        "base_url": "https://pawmanga.com",
        "name": "PawManga",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://pawmanga.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "mangasushi": {
        "template": "madara",
        "base_url": "https://mangasushi.org",
        "name": "MangaSushi",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://mangasushi.org/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "flamescans": {
        "script": "flamecomics.js",
        "name": "Flame Comics",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://flamecomics.xyz/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "manhwamanhua": {
        "template": "madara",
        "base_url": "https://manhwamanhua.com",
        "name": "ManhwaManhua",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://manhwamanhua.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "manhwareads": {
        "template": "madara",
        "base_url": "https://manhwareads.com",
        "name": "ManhwaReads",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://manhwareads.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "octopusmanga": {
        "template": "madara",
        "base_url": "https://octopusmanga.com",
        "name": "OctopusManga",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://octopusmanga.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "spmanhwa": {
        "template": "madara",
        "base_url": "https://spmanhwa.online",
        "name": "SPManhwa",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://spmanhwa.online/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "tritiniascans": {
        "template": "madara",
        "base_url": "https://tritinia.org",
        "name": "Tritinia Scans",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://tritinia.org/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "zinmanga": {
        "template": "madara",
        "base_url": "https://mangazin.org",
        "name": "ZinManga",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://mangazin.org/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    # ── Custom JS (non-WordPress) ─────────────────────────────
    "mangakakalot": {
        "script": "mangakakalot.js",
        "name": "MangaKakalot",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://mangakakalot.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "manganato": {
        "script": "manganato.js",
        "name": "MangaNato",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://manganato.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "bato": {
        "script": "bato.js",
        "name": "Bato.to",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://bato.to/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "mangapill": {
        "script": "mangapill.js",
        "name": "MangaPill",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://mangapill.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "tcbscans": {
        "script": "tcbscans.js",
        "name": "TCB Scans",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://tcbscans.me/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "mangahere": {
        "script": "mangahere.js",
        "name": "MangaHere",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://www.mangahere.cc/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "webtoons": {
        "script": "webtoons.js",
        "name": "Webtoons",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://webtoons.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "mangaplus": {
        "script": "mangaplus.js",
        "name": "MANGA Plus",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://mangaplus.shueisha.co.jp/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "azuki": {
        "script": "azuki.js",
        "name": "Azuki",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://www.azuki.co/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "comixto": {
        "script": "comixto.js",
        "name": "Comix.to",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://comix.to/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    # ── Web Novels ───────────────────────────────────────────────
    "royalroad": {
        "script": "royalroad.js",
        "type": "novel",
        "name": "Royal Road",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://www.royalroad.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": True,
    },
    "scribblehub": {
        "script": "scribblehub.js",
        "type": "novel",
        "name": "Scribble Hub",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://www.scribblehub.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": True,
    },
    "lightnovelworld": {
        "script": "lightnovelworld.js",
        "type": "novel",
        "name": "Light Novel World",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://www.lightnovelworld.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": False,
    },
    "wuxiaworld": {
        "script": "wuxiaworld.js",
        "type": "novel",
        "name": "WuxiaWorld",
        "lang": "en",
        "version": "1.0.0",
        "icon": "https://www.wuxiaworld.com/favicon.ico",
        "nsfw": False,
        "skip_proxy": True,
    },
}


def get_extension_code_by_pkg(pkg_id: str) -> dict | None:
    """Return extension code dict or dynamically build theme JS for community sources."""
    if pkg_id in BUILT_IN_EXTENSIONS:
        meta = BUILT_IN_EXTENSIONS[pkg_id]
        if "script" in meta:
            code = load_extension_script(meta["script"])
        elif "template" in meta:
            template_file = f"{meta['template']}.template.js"
            template = load_extension_script(template_file)
            code = template.replace("{BASE_URL}", meta["base_url"].rstrip("/"))
        else:
            return None
        return {
            "code": code,
            "skip_proxy": meta.get("skip_proxy", False),
            "type": meta.get("type", "manga"),
        }

    home_url = None
    index_json_path = "/home/zenmi/Projects/extensions/index.json"
    if os.path.exists(index_json_path):
        try:
            with open(index_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for ext in data.get("extensions", []):
                    if ext.get("packageName") == pkg_id:
                        sources = ext.get("sources", [])
                        if sources:
                            home_url = sources[0].get("homeUrl")
                            break
        except Exception as e:
            log.warning("Failed to parse local extensions index.json: %s", e)

    theme = None
    parts = pkg_id.split(".")
    if len(parts) >= 6:
        lang = parts[4]
        name = parts[5]
        src_dir = f"/home/zenmi/Projects/extensions-source/src/{lang}/{name}"
        if not os.path.exists(src_dir):
            src_dir = f"/home/zenmi/Projects/extensions-source/src/all/{name}"

        if os.path.exists(src_dir):
            for root, dirs, files in os.walk(src_dir):
                for f in files:
                    if f.endswith(".kt"):
                        path = os.path.join(root, f)
                        try:
                            with open(path, "r", encoding="utf-8") as file:
                                content = file.read()
                                if re.search(r":\s*Madara\b", content):
                                    theme = "Madara"
                                    break
                                elif re.search(r":\s*MangaThemesia\b", content):
                                    theme = "MangaThemesia"
                                    break
                        except Exception:
                            pass
                if theme:
                    break

    if home_url and theme:
        base_url = home_url.rstrip("/")
        if theme == "Madara":
            template = load_extension_script("madara.template.js")
            code = template.replace("{BASE_URL}", base_url)
            log.info("Dynamically generated Madara code for package: %s, URL: %s", pkg_id, base_url)
            return {"code": code, "skip_proxy": False}
        elif theme == "MangaThemesia":
            template = load_extension_script("mangathemesia.template.js")
            code = template.replace("{BASE_URL}", base_url)
            log.info("Dynamically generated MangaThemesia code for package: %s, URL: %s", pkg_id, base_url)
            return {"code": code, "skip_proxy": False}

    # Community extension fallback — attempt Keiyoushi online
    try:
        ext_url = f"https://raw.githubusercontent.com/keiyoushi/extensions/repo/sources/{pkg_id}/index.js"
        response = requests.get(ext_url, impersonate="chrome110", timeout=10)
        if response.status_code == 200:
            return {"code": response.text, "skip_proxy": False}
        return None
    except Exception as e:
        log.error("Failed to fetch extension code for %s: %s", pkg_id, e)
        return None
