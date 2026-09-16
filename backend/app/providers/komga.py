"""
Komga self-hosted server provider.
Connects to a Komga instance via its REST API (/api/v1/...).
User configures base_url + credentials via Source preferences.
"""
import logging
from curl_cffi.requests import AsyncSession

from .base import Provider, MangaResult, ChapterResult, MangaDetail

log = logging.getLogger(__name__)

PROVIDER_ID = "komga"


class KomgaProvider(Provider):
    id = PROVIDER_ID
    name = "Komga"
    icon = "🏠"
    base_url = ""  # set via configure()

    def __init__(self):
        super().__init__()
        self._base_url: str = ""
        self._auth: tuple[str, str] | None = None

    def configure(self, base_url: str, username: str, password: str):
        self._base_url = base_url.rstrip("/")
        self._auth = (username, password)

    def _api(self, path: str) -> str:
        return f"{self._base_url}/api/v1{path}"

    def _headers(self) -> dict:
        import base64
        if not self._auth:
            return {}
        token = base64.b64encode(f"{self._auth[0]}:{self._auth[1]}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    async def search(self, query: str, page: int = 1) -> list[MangaResult]:
        if not self._base_url:
            return []
        async with AsyncSession() as s:
            try:
                r = await s.get(
                    self._api(f"/series?search={query}&page={page - 1}&size=20"),
                    headers=self._headers(),
                )
                data = r.json()
                results = []
                for item in data.get("content", []):
                    results.append(MangaResult(
                        id=item["id"],
                        title=item["name"],
                        cover_url=f"{self._base_url}/api/v1/series/{item['id']}/thumbnail",
                        provider=self.id,
                        url=f"{self._base_url}/series/{item['id']}",
                        status=item.get("metadata", {}).get("status"),
                    ))
                return results
            except Exception as e:
                log.warning(f"Komga search error: {e}")
                return []

    async def get_popular(self, page: int = 1) -> list[MangaResult]:
        if not self._base_url:
            return []
        async with AsyncSession() as s:
            try:
                r = await s.get(
                    self._api(f"/series?page={page - 1}&size=20&sort=lastModified,desc"),
                    headers=self._headers(),
                )
                data = r.json()
                return [
                    MangaResult(
                        id=item["id"],
                        title=item["name"],
                        cover_url=f"{self._base_url}/api/v1/series/{item['id']}/thumbnail",
                        provider=self.id,
                        url=f"{self._base_url}/series/{item['id']}",
                        status=item.get("metadata", {}).get("status"),
                    )
                    for item in data.get("content", [])
                ]
            except Exception as e:
                log.warning(f"Komga popular error: {e}")
                return []

    async def get_manga(self, manga_id: str) -> MangaDetail:
        async with AsyncSession() as s:
            r = await s.get(self._api(f"/series/{manga_id}"), headers=self._headers())
            data = r.json()
            meta = data.get("metadata", {})

            books_r = await s.get(
                self._api(f"/series/{manga_id}/books?size=500&sort=metadata.numberSort,asc"),
                headers=self._headers(),
            )
            books = books_r.json().get("content", [])
            chapters = [
                ChapterResult(
                    id=b["id"],
                    title=b.get("metadata", {}).get("title") or b.get("name", ""),
                    number=b.get("metadata", {}).get("numberSort") or 0,
                    published_at=b.get("created"),
                )
                for b in books
            ]
            return MangaDetail(
                id=manga_id,
                title=data.get("name", ""),
                cover_url=f"{self._base_url}/api/v1/series/{manga_id}/thumbnail",
                description=meta.get("summary"),
                status=meta.get("status"),
                genres=meta.get("tags", []),
                authors=meta.get("authors", []),
                provider=self.id,
                url=f"{self._base_url}/series/{manga_id}",
                chapters=chapters,
            )

    async def get_pages(self, chapter_id: str) -> list[str]:
        if not self._base_url:
            return []
        async with AsyncSession() as s:
            r = await s.get(self._api(f"/books/{chapter_id}/pages"), headers=self._headers())
            pages = r.json()
            return [
                f"{self._base_url}/api/v1/books/{chapter_id}/pages/{p['number']}/raw"
                for p in pages
            ]
