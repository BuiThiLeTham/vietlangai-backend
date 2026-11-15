import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

MAX_TRACKED_KEYS = 10000


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding-window rate limiter with X-Forwarded-For and bounded memory."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def clear(self) -> None:
        self._buckets.clear()

    @staticmethod
    def _client_ip(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            first_ip = forwarded.split(",", 1)[0].strip()
            if first_ip:
                return first_ip
        return request.client.host if request.client else "anonymous"

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        if not (path.startswith("/v1/auth/") or path.startswith("/v1/translate")):
            return await call_next(request)

        client_host = self._client_ip(request)
        key = f"{client_host}:{path}"
        now = time.monotonic()
        window = float(settings.rate_limit_window_seconds)
        limit = settings.rate_limit_requests

        if key not in self._buckets and len(self._buckets) >= MAX_TRACKED_KEYS:
            stale_keys = [k for k, q in self._buckets.items() if not q or now - q[-1] > window]
            for k in stale_keys:
                self._buckets.pop(k, None)
            if len(self._buckets) >= MAX_TRACKED_KEYS:
                oldest_key = next(iter(self._buckets))
                self._buckets.pop(oldest_key, None)

        bucket = self._buckets[key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()

        if len(bucket) >= limit:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": {
                        "code": "rate_limit_exceeded",
                        "message": "Quá nhiều yêu cầu trong thời gian ngắn, vui lòng thử lại sau.",
                    }
                },
            )

        bucket.append(now)
        return await call_next(request)
