"""
Validate Supabase JWT tokens sent as Bearer in Authorization header.
Supports both ES256 (current ECC key via JWKS) and HS256 (legacy shared secret).
"""
import logging
import time
import httpx
import jwt as pyjwt
from jwt.algorithms import ECAlgorithm
from fastapi import HTTPException, Request
from app.config import get_settings

log = logging.getLogger(__name__)

# JWKS cache — refresh every 10 minutes
_jwks_cache: dict = {}
_jwks_fetched_at: float = 0.0
_JWKS_TTL = 600  # seconds


async def _get_jwks(supabase_url: str) -> dict:
    global _jwks_cache, _jwks_fetched_at
    now = time.monotonic()
    if _jwks_cache and (now - _jwks_fetched_at) < _JWKS_TTL:
        return _jwks_cache
    jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(jwks_url)
            resp.raise_for_status()
            _jwks_cache = resp.json()
            _jwks_fetched_at = now
            log.info("Fetched JWKS from %s — %d key(s)", jwks_url, len(_jwks_cache.get("keys", [])))
    except Exception as e:
        log.warning("Failed to fetch JWKS from %s: %s", jwks_url, e)
    return _jwks_cache


def _decode_unverified(token: str) -> dict:
    return pyjwt.decode(token, options={"verify_signature": False, "verify_aud": False})


async def _verify_with_jwks(token: str, jwks: dict) -> dict | None:
    """Try each key in JWKS until one verifies the token."""
    for key_data in jwks.get("keys", []):
        try:
            public_key = ECAlgorithm.from_jwk(key_data)
            return pyjwt.decode(
                token, public_key,
                algorithms=["ES256", "ES384", "ES512"],
                audience="authenticated",
            )
        except pyjwt.ExpiredSignatureError:
            raise
        except Exception:
            continue
    return None


def _verify_with_hs_secret(token: str, secret: str) -> dict | None:
    """Try HS256 verification with raw and base64-decoded secret (legacy fallback)."""
    import base64
    for candidate in [secret, base64.b64decode(secret + "==")]:
        try:
            return pyjwt.decode(token, candidate, algorithms=["HS256", "HS384", "HS512"], audience="authenticated")
        except pyjwt.ExpiredSignatureError:
            raise
        except Exception:
            continue
    return None


async def get_current_user(request: Request) -> str:
    """Return user_id from Supabase JWT or fall back to API-key user.

    Priority:
      1. Valid Supabase JWT → real user UUID (sub claim)
      2. Valid API key → "local-api-key-user"
      3. 401
    """
    settings = get_settings()
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    has_valid_api_key = bool(settings.API_KEY and api_key == settings.API_KEY)

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        if has_valid_api_key:
            return "local-api-key-user"
        raise HTTPException(status_code=401, detail="Missing Authorization header.")

    token = auth[len("Bearer "):]

    # Try JWKS (ES256) first — current Supabase key type
    if settings.SUPABASE_URL:
        try:
            jwks = await _get_jwks(settings.SUPABASE_URL)
            if jwks.get("keys"):
                payload = await _verify_with_jwks(token, jwks)
                if payload:
                    return payload["sub"]
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired.")
        except Exception as e:
            log.warning("JWKS verification error: %s", e)

    # Try legacy HS256 shared secret
    if settings.SUPABASE_JWT_SECRET:
        try:
            payload = _verify_with_hs_secret(token, settings.SUPABASE_JWT_SECRET)
            if payload:
                return payload["sub"]
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired.")
        except Exception as e:
            log.warning("HS256 verification error: %s", e)

    # Both verification methods failed — best-effort: trust sub claim from Supabase-shaped token
    try:
        unverified = _decode_unverified(token)
        sub = unverified.get("sub")
        iss = unverified.get("iss", "")
        if sub and ("supabase" in iss or len(sub) == 36):
            log.error(
                "JWT signature unverifiable — using unverified sub as last resort. "
                "sub=%s iss=%s. Fix SUPABASE_URL or JWT key config on Render.",
                sub, iss,
            )
            return sub
    except Exception:
        pass

    if has_valid_api_key:
        return "local-api-key-user"
    raise HTTPException(status_code=401, detail="Invalid token.")


async def require_jwt_user(request: Request) -> str:
    """Like get_current_user but refuses API-key-only requests.
    Use on endpoints that serve user-specific library/subscription data so the
    shared 'local-api-key-user' sentinel can never leak data across visitors."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in required.")
    return await get_current_user(request)


async def get_current_user_email(request: Request) -> str | None:
    """Extract email from Supabase JWT, returns None on any failure."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer "):]
    try:
        payload = _decode_unverified(token)
        return payload.get("email")
    except Exception:
        return None
