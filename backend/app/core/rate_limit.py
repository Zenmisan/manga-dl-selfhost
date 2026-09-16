import time
import logging
from collections import defaultdict, deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

log = logging.getLogger(__name__)

# Max request payload size: 10 MB (prevents memory spikes on Render 512MB RAM tier)
MAX_PAYLOAD_BYTES = 10 * 1024 * 1024

# Sliding Window Rate Limits
DEFAULT_MAX_REQUESTS_PER_MINUTE = 120
STRICT_MAX_REQUESTS_PER_MINUTE = 30


class RateLimitAndSecurityMiddleware(BaseHTTPMiddleware):
    """
    In-memory sliding window rate limiter and payload size guard.
    Protects backend services on free tier from DDoS, request floods, and memory exhaustion.
    """

    def __init__(self, app, max_requests: int = DEFAULT_MAX_REQUESTS_PER_MINUTE, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        # 1. Payload Size Guard (prevents 413 Denial of Service)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_PAYLOAD_BYTES:
                    log.warning("Rejected oversized payload: %s bytes from %s", content_length, request.client.host if request.client else "unknown")
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request payload exceeds maximum allowed size (10 MB)."}
                    )
            except ValueError:
                pass

        # 2. Extract Client IP
        client_ip = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
        elif request.client:
            client_ip = request.client.host
        else:
            client_ip = "unknown"

        # Bypass rate limits for health checks and local static assets
        path = request.url.path
        if path in ("/health", "/", "/robots.txt", "/sitemap.xml") or path.startswith("/assets/"):
            return await call_next(request)

        # Stricter rate limits on sensitive public endpoints (contact ticket / proxy)
        is_strict = path.startswith("/api/support") or path.startswith("/api/manga/proxy")
        limit = STRICT_MAX_REQUESTS_PER_MINUTE if is_strict else self.max_requests

        now = time.time()
        queue = self.requests[client_ip]

        # Purge entries older than the sliding window
        while queue and queue[0] < now - self.window_seconds:
            queue.popleft()

        # Check rate limit
        if len(queue) >= limit:
            log.warning("Rate limit exceeded for IP: %s on %s (%d requests in %ds)", client_ip, path, len(queue), self.window_seconds)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down and try again."},
                headers={"Retry-After": str(self.window_seconds)}
            )

        queue.append(now)
        return await call_next(request)
