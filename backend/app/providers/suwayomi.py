"""
Suwayomi-Server provider (self-hosted Tachiyomi server).
Uses Suwayomi's GraphQL API (/api/graphql).
"""
import logging
from curl_cffi.requests import AsyncSession

from .base import Provider, MangaResult, ChapterResult, MangaDetail

log = logging.getLogger(__name__)

PROVIDER_ID = "suwayomi"

_GQL_SEARCH = """
query Search($query: String!, $page: Int!) {
  fetchSourceManga(input: {sourceId: "all", query: $query, page: $page, type: SEARCH}) {
    mangas { id title thumbnailUrl }
  }
}
"""

_GQL_POPULAR = """
query Popular($page: Int!) {
  fetchSourceManga(input: {sourceId: "all", page: $page, type: POPULAR}) {
    mangas { id title thumbnailUrl }
  }
}
"""

_GQL_MANGA = """
query Manga($id: Int!) {
  manga(id: $id) {
    id title description status genre author artist thumbnailUrl
    chapters { nodes { id name chapterNumber uploadDate } }
  }
}
"""

_GQL_PAGES = """
query Pages($chapterId: Int!) {
  fetchChapterPages(chapterId: $chapterId) { pages }
}
"""


class SuwayomiProvider(Provider):
    id = PROVIDER_ID
    name = "Suwayomi"
    icon = "🌊"
    base_url = ""  # set via configure()

    def __init__(self):
        super().__init__()
        self._base_url: str = ""

    def configure(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    def _gql_url(self) -> str:
        return f"{self._base_url}/api/graphql"

    async def _gql(self, query: str, variables: dict) -> dict:
        async with AsyncSession() as s:
            r = await s.post(
                self._gql_url(),
                json={"query": query, "variables": variables},
                headers={"Content-Type": "application/json"},
            )
            return r.json().get("data", {})

    def _manga_from_node(self, m: dict) -> MangaResult:
        thumbnail = m.get("thumbnailUrl", "")
        if thumbnail and not thumbnail.startswith("http"):
            thumbnail = f"{self._base_url}{thumbnail}"
        return MangaResult(
            id=str(m["id"]),
            title=m.get("title", ""),
            cover_url=thumbnail or None,
            provider=self.id,
            url=f"{self._base_url}/manga/{m['id']}",
        )

    async def search(self, query: str, page: int = 1) -> list[MangaResult]:
        if not self._base_url:
            return []
        try:
            data = await self._gql(_GQL_SEARCH, {"query": query, "page": page})
            mangas = data.get("fetchSourceManga", {}).get("mangas", [])
            return [self._manga_from_node(m) for m in mangas]
        except Exception as e:
            log.warning(f"Suwayomi search error: {e}")
            return []

    async def get_popular(self, page: int = 1) -> list[MangaResult]:
        if not self._base_url:
            return []
        try:
            data = await self._gql(_GQL_POPULAR, {"page": page})
            mangas = data.get("fetchSourceManga", {}).get("mangas", [])
            return [self._manga_from_node(m) for m in mangas]
        except Exception as e:
            log.warning(f"Suwayomi popular error: {e}")
            return []

    async def get_manga(self, manga_id: str) -> MangaDetail:
        data = await self._gql(_GQL_MANGA, {"id": int(manga_id)})
        m = data.get("manga", {})
        chapters = [
            ChapterResult(
                id=str(ch["id"]),
                title=ch.get("name", ""),
                number=ch.get("chapterNumber") or 0,
                published_at=ch.get("uploadDate"),
            )
            for ch in m.get("chapters", {}).get("nodes", [])
        ]
        thumbnail = m.get("thumbnailUrl", "")
        if thumbnail and not thumbnail.startswith("http"):
            thumbnail = f"{self._base_url}{thumbnail}"
        return MangaDetail(
            id=manga_id,
            title=m.get("title", ""),
            cover_url=thumbnail or None,
            description=m.get("description"),
            status=m.get("status"),
            genres=m.get("genre", []),
            authors=[a for a in [m.get("author"), m.get("artist")] if a],
            provider=self.id,
            url=f"{self._base_url}/manga/{manga_id}",
            chapters=chapters,
        )

    async def get_pages(self, chapter_id: str) -> list[str]:
        if not self._base_url:
            return []
        try:
            data = await self._gql(_GQL_PAGES, {"chapterId": int(chapter_id)})
            pages = data.get("fetchChapterPages", {}).get("pages", [])
            return [
                p if p.startswith("http") else f"{self._base_url}{p}"
                for p in pages
            ]
        except Exception as e:
            log.warning(f"Suwayomi pages error: {e}")
            return []
