import logging
import asyncio
from typing import Optional, Dict, Any
from curl_cffi.requests import AsyncSession

log = logging.getLogger(__name__)

ANILIST_API = "https://graphql.anilist.co"

QUERY = """
query ($search: String) {
  Media (search: $search, type: MANGA) {
    id
    title {
      romaji
      english
      native
    }
    averageScore
    popularity
    status
    description
    coverImage {
      large
    }
    genres
    siteUrl
  }
}
"""

async def fetch_anilist_metadata(title: str) -> Optional[Dict[str, Any]]:
    """Fetch manga metadata from AniList using its GraphQL API."""
    async with AsyncSession(impersonate="chrome110") as s:
        try:
            resp = await s.post(
                ANILIST_API,
                json={"query": QUERY, "variables": {"search": title}},
                timeout=10.0
            )
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            return data.get("data", {}).get("Media")
        except Exception as e:
            log.warning(f"Failed to fetch AniList metadata for {title}: {e}")
            return None

async def enrich_results_with_metadata(results: list) -> list:
    """Concurrently fetch AniList metadata for a list of manga results."""
    # To avoid rate limits and too many requests, we only fetch for unique titles
    unique_titles = list(set(r.title for r in results))
    
    # AniList rate limit is 90 per minute, so we should be careful with large lists
    # For now, we fetch them concurrently
    tasks = [fetch_anilist_metadata(t) for t in unique_titles]
    metadata_list = await asyncio.gather(*tasks)
    
    metadata_map = dict(zip(unique_titles, metadata_list))
    
    for r in results:
        meta = metadata_map.get(r.title)
        if meta:
            r.anilist_score = meta.get("averageScore")
            r.anilist_url = meta.get("siteUrl")
            # We could also overwrite cover_url if it's missing
            if not r.cover_url:
                r.cover_url = meta.get("coverImage", {}).get("large")
                
    return results
