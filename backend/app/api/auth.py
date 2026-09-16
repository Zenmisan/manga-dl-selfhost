"""
MAL (MyAnimeList) OAuth2 PKCE integration.
The frontend generates the code_verifier/challenge and initiates the OAuth redirect.
After MAL redirects back with ?code=..., the frontend sends the code + verifier here
for the actual token exchange (avoids CORS restriction on MAL's token endpoint).
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from curl_cffi.requests import AsyncSession
from app.config import get_settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

MAL_TOKEN_URL = "https://myanimelist.net/v1/oauth2/token"
MAL_API_BASE = "https://api.myanimelist.net/v2"
ANILIST_GQL = "https://graphql.anilist.co"
ANILIST_TOKEN_URL = "https://anilist.co/api/v2/oauth/token"


class MALTokenRequest(BaseModel):
    client_id: str
    code: str
    code_verifier: str
    redirect_uri: str


class MALTrackRequest(BaseModel):
    access_token: str
    manga_id: int
    status: str = "reading"  # reading | completed | on_hold | dropped | plan_to_read
    chapters_read: int = 0
    score: int = 0  # 0–10
    start_date: str | None = None   # YYYY-MM-DD
    finish_date: str | None = None  # YYYY-MM-DD


class MALSearchRequest(BaseModel):
    access_token: str
    query: str


@router.post("/mal/token")
async def exchange_mal_token(req: MALTokenRequest):
    """Exchange MAL authorization code for access token."""
    mal_secret = get_settings().MAL_CLIENT_SECRET or ""
    async with AsyncSession() as client:
        try:
            token_data: dict = {
                "client_id": req.client_id,
                "code": req.code,
                "code_verifier": req.code_verifier,
                "grant_type": "authorization_code",
                "redirect_uri": req.redirect_uri,
            }
            if mal_secret:
                token_data["client_secret"] = mal_secret
            resp = await client.post(
                MAL_TOKEN_URL,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15.0,
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"MAL token error: {resp.text}")
            data = resp.json()

            # Fetch user info with the new token
            me_resp = await client.get(
                f"{MAL_API_BASE}/users/@me",
                headers={"Authorization": f"Bearer {data['access_token']}"},
                timeout=10.0,
            )
            username = me_resp.json().get("name", "Unknown") if me_resp.status_code == 200 else "Unknown"

            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token"),
                "expires_in": data.get("expires_in"),
                "username": username,
            }
        except HTTPException:
            raise
        except Exception as e:
            log.error("MAL token exchange failed: %s", e)
            raise HTTPException(status_code=502, detail=f"MAL request failed: {e}")


class AniListTokenRequest(BaseModel):
    code: str
    redirect_uri: str


@router.post("/anilist/token")
async def exchange_anilist_token(req: AniListTokenRequest):
    """Exchange AniList authorization code for access token."""
    settings = get_settings()
    client_id = settings.ANILIST_CLIENT_ID or ""
    client_secret = settings.ANILIST_CLIENT_SECRET or ""
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="AniList client credentials not configured on server")
    async with AsyncSession() as client:
        try:
            resp = await client.post(
                ANILIST_TOKEN_URL,
                json={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": req.redirect_uri,
                    "code": req.code,
                },
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=15.0,
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"AniList token error: {resp.text}")
            data = resp.json()
            access_token = data.get("access_token")
            if not access_token:
                raise HTTPException(status_code=502, detail="No access_token in AniList response")

            # Fetch viewer name
            me_resp = await client.post(
                ANILIST_GQL,
                json={"query": "{ Viewer { name } }"},
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            username = None
            if me_resp.status_code == 200:
                username = me_resp.json().get("data", {}).get("Viewer", {}).get("name")

            return {
                "access_token": access_token,
                "token_type": data.get("token_type", "Bearer"),
                "expires_in": data.get("expires_in"),
                "username": username,
            }
        except HTTPException:
            raise
        except Exception as e:
            log.error("AniList token exchange failed: %s", e)
            raise HTTPException(status_code=502, detail=str(e))


@router.get("/anilist/search")
async def search_anilist_manga(q: str, access_token: str = ""):
    """Search AniList manga by title."""
    gql = """
    query ($q: String) {
      Page(page: 1, perPage: 10) {
        media(search: $q, type: MANGA) {
          id
          title { romaji english }
          coverImage { medium }
          startDate { year }
          averageScore
          status
        }
      }
    }
    """
    headers: dict = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    async with AsyncSession() as client:
        try:
            resp = await client.post(
                ANILIST_GQL,
                json={"query": gql, "variables": {"q": q}},
                headers=headers,
                timeout=10.0,
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"AniList error: {resp.text}")
            data = resp.json()
            media_list = data.get("data", {}).get("Page", {}).get("media", [])
            return [
                {
                    "id": m["id"],
                    "title": m["title"].get("english") or m["title"].get("romaji") or "",
                    "cover": m.get("coverImage", {}).get("medium"),
                    "year": m.get("startDate", {}).get("year"),
                    "score": m.get("averageScore"),
                    "status": m.get("status"),
                }
                for m in media_list
            ]
        except HTTPException:
            raise
        except Exception as e:
            log.error("AniList search failed: %s", e)
            raise HTTPException(status_code=502, detail=str(e))


class AniListTrackRequest(BaseModel):
    access_token: str
    media_id: int
    status: str = "CURRENT"     # CURRENT | COMPLETED | PAUSED | DROPPED | PLANNING | REPEATING
    score: float = 0
    progress: int = 0
    start_date: str | None = None   # YYYY-MM-DD
    finish_date: str | None = None  # YYYY-MM-DD


@router.post("/anilist/track")
async def update_anilist_status(req: AniListTrackRequest):
    """Save manga reading progress to AniList via GraphQL mutation."""
    def _ymd(s: str | None):
        if not s:
            return None
        parts = s.split("-")
        if len(parts) != 3:
            return None
        return {"year": int(parts[0]), "month": int(parts[1]), "day": int(parts[2])}

    mutation = """
    mutation ($mediaId: Int, $status: MediaListStatus, $score: Float, $progress: Int,
              $startedAt: FuzzyDateInput, $completedAt: FuzzyDateInput) {
      SaveMediaListEntry(mediaId: $mediaId, status: $status, score: $score,
                         progress: $progress, startedAt: $startedAt, completedAt: $completedAt) {
        id status score progress
      }
    }
    """
    variables = {
        "mediaId": req.media_id,
        "status": req.status,
        "score": req.score,
        "progress": req.progress,
    }
    sd = _ymd(req.start_date)
    ed = _ymd(req.finish_date)
    if sd:
        variables["startedAt"] = sd
    if ed:
        variables["completedAt"] = ed

    async with AsyncSession() as client:
        try:
            resp = await client.post(
                ANILIST_GQL,
                json={"query": mutation, "variables": variables},
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {req.access_token}"},
                timeout=10.0,
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"AniList error: {resp.text}")
            data = resp.json()
            if "errors" in data:
                raise HTTPException(status_code=502, detail=str(data["errors"]))
            return {"status": "ok", "data": data.get("data", {}).get("SaveMediaListEntry")}
        except HTTPException:
            raise
        except Exception as e:
            log.error("AniList track failed: %s", e)
            raise HTTPException(status_code=502, detail=str(e))


@router.get("/mal/search")
async def search_mal_manga_get(q: str, access_token: str):
    """Search MAL manga to find the MAL ID for a given title."""
    async with AsyncSession() as client:
        try:
            resp = await client.get(
                f"{MAL_API_BASE}/manga",
                params={"q": q, "limit": 10, "fields": "id,title,main_picture,num_chapters,status,mean"},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"MAL search failed: {resp.text}")
            data = resp.json()
            return [
                {
                    "id": item["node"]["id"],
                    "title": item["node"]["title"],
                    "cover": item["node"].get("main_picture", {}).get("medium"),
                    "chapters": item["node"].get("num_chapters", 0),
                    "score": item["node"].get("mean"),
                    "status": item["node"].get("status"),
                }
                for item in data.get("data", [])
            ]
        except HTTPException:
            raise
        except Exception as e:
            log.error("MAL search failed: %s", e)
            raise HTTPException(status_code=502, detail=str(e))


@router.post("/mal/search")
async def search_mal_manga(req: MALSearchRequest):
    """Search MAL manga to find the MAL ID for a given title."""
    async with AsyncSession() as client:
        try:
            resp = await client.get(
                f"{MAL_API_BASE}/manga",
                params={"q": req.query, "limit": 5, "fields": "id,title,main_picture,num_chapters"},
                headers={"Authorization": f"Bearer {req.access_token}"},
                timeout=10.0,
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"MAL search failed: {resp.text}")
            data = resp.json()
            return {
                "results": [
                    {
                        "id": item["node"]["id"],
                        "title": item["node"]["title"],
                        "cover": item["node"].get("main_picture", {}).get("medium"),
                        "chapters": item["node"].get("num_chapters", 0),
                    }
                    for item in data.get("data", [])
                ]
            }
        except HTTPException:
            raise
        except Exception as e:
            log.error("MAL search failed: %s", e)
            raise HTTPException(status_code=502, detail=str(e))


@router.post("/mal/track")
async def update_mal_status(req: MALTrackRequest):
    """Update manga reading status on MAL."""
    async with AsyncSession() as client:
        try:
            resp = await client.patch(
                f"{MAL_API_BASE}/manga/{req.manga_id}/my_list_status",
                data={
                    k: v for k, v in {
                        "status": req.status,
                        "num_chapters_read": req.chapters_read,
                        "score": req.score if req.score else None,
                        "start_date": req.start_date,
                        "finish_date": req.finish_date,
                    }.items() if v is not None
                },
                headers={
                    "Authorization": f"Bearer {req.access_token}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=10.0,
            )
            if resp.status_code not in (200, 201):
                raise HTTPException(status_code=502, detail=f"MAL update failed: {resp.text}")
            return {"status": "ok", "data": resp.json()}
        except HTTPException:
            raise
        except Exception as e:
            log.error("MAL track failed: %s", e)
            raise HTTPException(status_code=502, detail=str(e))
