# src/fpl_mcp/http_middleware.py
"""ASGI middleware that sheds excess inbound requests before they reach the
MCP app. See fpl.inbound_limiter for why this is separate from the outbound
FPL rate limiter.
"""
import logging

from .fpl.inbound_limiter import inbound_limiter

logger = logging.getLogger(__name__)


def _client_key(scope) -> str:
    """Best-effort caller identity to key the inbound limiter on.

    Trusts X-Forwarded-For: this server binds 127.0.0.1 and is reached only
    through the Caddy reverse proxy in front of it (see deployment docs), so
    nothing outside can talk to it directly and spoof the header. Falls back
    to the raw connection address for local/direct use (e.g. testing without
    a proxy in front).
    """
    headers = dict(scope.get("headers") or [])
    xff = headers.get(b"x-forwarded-for")
    if xff:
        return xff.decode("latin-1", "replace").split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


class InboundRateLimitMiddleware:
    """Rejects excess requests with HTTP 429 before the MCP app sees them."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        key = _client_key(scope)
        if not inbound_limiter.allow(key):
            logger.warning("Inbound rate limit exceeded for %s", key)
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"retry-after", b"60"),
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"error":"Too many requests. Please slow down and try again shortly."}',
                }
            )
            return

        await self.app(scope, receive, send)
