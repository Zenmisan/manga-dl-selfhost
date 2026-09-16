from fastapi import Security, HTTPException, status, Query, Request, WebSocketException
from fastapi.security import APIKeyHeader
from app.config import get_settings
from typing import Annotated

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(
    request: Request,
    api_key_header: str = Security(api_key_header),
    api_key_query: Annotated[str | None, Query(alias="api_key")] = None
):
    settings = get_settings()
    if settings.API_KEY is None:
        return True # Auth disabled
        
    # Check header first, then query param
    key = api_key_header or api_key_query
    
    if key == settings.API_KEY:
        return True
        
    if request.scope.get("type") == "websocket":
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Could not validate credentials")

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate credentials"
    )
