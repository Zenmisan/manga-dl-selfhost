from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import json
import os

from app.config import get_settings
from app.providers import get_provider, list_providers, register_provider
from app.providers.base import Provider, ProviderHealth, MangaResult, MangaDetail, ChapterResult

router = APIRouter(prefix="/settings", tags=["settings"])
settings = get_settings()


class AppSettings(BaseModel):
    library_path: str
    cache_path: str
    max_concurrent_downloads: int
    request_delay: float


class CustomProviderConfig(BaseModel):
    id: str
    name: str
    base_url: str
    search_url_template: str       # e.g. "{base}/search?q={query}"
    manga_url_template: str        # e.g. "{base}/manga/{id}"
    chapter_url_template: str      # e.g. "{base}/chapter/{id}"
    search_result_selector: str    # CSS selector for search result items
    title_selector: str
    cover_selector: str
    chapter_list_selector: str
    page_image_selector: str


@router.get("/", response_model=AppSettings)
async def get_app_settings():
    return AppSettings(
        library_path=settings.LIBRARY_PATH,
        cache_path=settings.CACHE_PATH,
        max_concurrent_downloads=settings.MAX_CONCURRENT_DOWNLOADS,
        request_delay=settings.REQUEST_DELAY,
    )


@router.get("/providers")
async def get_provider_settings():
    """List all providers with configuration and health."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "base_url": p.base_url,
            "health": p.health.value,
            "type": "builtin",
        }
        for p in list_providers()
    ]


@router.post("/providers/custom")
async def add_custom_provider(config: CustomProviderConfig):
    """
    Register a custom provider by providing CSS selectors and URL templates.
    This creates a generic scraper that follows the given patterns.
    """
    if get_provider(config.id):
        raise HTTPException(status_code=409, detail=f"Provider '{config.id}' already exists")

    # Dynamically create a provider class from the config
    provider = _build_generic_provider(config)
    register_provider(provider)

    return {"status": "registered", "provider_id": config.id}


def _build_generic_provider(config: CustomProviderConfig) -> Provider:
    """Build a runtime Provider instance from a CSS-selector config."""
    from bs4 import BeautifulSoup
    import httpx

    class GenericProvider(Provider):
        id = config.id
        name = config.name
        base_url = config.base_url
        fingerprints = []

        async def search(self, query: str, page: int = 1) -> list[MangaResult]:
            url = config.search_url_template.format(base=config.base_url, query=query, page=page)
            client = await self._get_client()
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for item in soup.select(config.search_result_selector):
                a = item.select_one("a")
                title_el = item.select_one(config.title_selector)
                img_el = item.select_one(config.cover_selector)
                if not a:
                    continue
                href = a.get("href", "")
                manga_id = href.rstrip("/").split("/")[-1]
                results.append(MangaResult(
                    id=manga_id,
                    title=title_el.get_text(strip=True) if title_el else manga_id,
                    cover_url=img_el.get("src") if img_el else None,
                    provider=self.id,
                    url=href,
                ))
            return results

        async def get_manga(self, manga_id: str) -> MangaDetail:
            url = config.manga_url_template.format(base=config.base_url, id=manga_id)
            client = await self._get_client()
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            title_el = soup.select_one(config.title_selector)
            chapters = []
            for a in soup.select(config.chapter_list_selector):
                href = a.get("href", "")
                ch_id = href.rstrip("/").split("/")[-1]
                import re
                num_match = re.search(r"[\d.]+", ch_id)
                num = float(num_match.group()) if num_match else 0.0
                chapters.append(ChapterResult(
                    id=ch_id, title=a.get_text(strip=True), number=num, url=href,
                ))
            return MangaDetail(
                id=manga_id,
                title=title_el.get_text(strip=True) if title_el else manga_id,
                cover_url=None,
                description=None,
                status=None,
                genres=[],
                authors=[],
                provider=self.id,
                url=url,
                chapters=chapters,
            )

        async def get_pages(self, chapter_id: str) -> list[str]:
            url = config.chapter_url_template.format(base=config.base_url, id=chapter_id)
            client = await self._get_client()
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            imgs = soup.select(config.page_image_selector)
            return [img.get("src") or img.get("data-src") for img in imgs
                    if img.get("src") or img.get("data-src")]

    provider = GenericProvider()
    return provider
