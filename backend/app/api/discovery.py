from fastapi import APIRouter, Query
from app.core.discovery_cache import get_discovery

router = APIRouter()


@router.get("/sources/discovery")
async def discovery_endpoint(providers: str = Query(default="")):
    """Return cached popular+latest manga for the requested provider IDs."""
    ids = [p.strip() for p in providers.split(",") if p.strip()]
    return await get_discovery(ids)
