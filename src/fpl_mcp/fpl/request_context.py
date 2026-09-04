# src/fpl_mcp/fpl/request_context.py
"""Read a per-request FPL team ID from an HTTP header.

The hosted server (fpl-mcp.duckdns.org) is shared: everyone talks to the
same process, so it can't store "your" team ID the way a self-hosted,
single-user copy does. Claude connectors let each person set up to four
custom request headers once, when they add the connector — so each friend
sends their own team ID on every call via the X-FPL-Team-ID header, and the
server reads it per request instead of storing anything about anyone.

Only the streamable-http and sse transports carry a real HTTP request with
headers. stdio (desktop clients launching this server themselves) has none,
and every function here returns None in that case — callers fall back to
whatever team ID the process was configured with, exactly as before this
existed.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

HEADER_NAME = "x-fpl-team-id"


def get_header_team_id() -> Optional[str]:
    """Return the team ID sent in this request's X-FPL-Team-ID header, if any."""
    try:
        from mcp.server.lowlevel.server import request_ctx
    except ImportError:  # pragma: no cover - defensive, shouldn't happen
        logger.debug("mcp.server.lowlevel.server.request_ctx unavailable")
        return None

    try:
        ctx = request_ctx.get()
    except LookupError:
        # Not inside a request (e.g. CLI 'test', or a lifespan hook).
        return None

    request = getattr(ctx, "request", None)
    if request is None:
        # stdio transport, or a transport that doesn't attach the raw
        # HTTP request to the message metadata.
        return None

    headers = getattr(request, "headers", None)
    if headers is None:
        return None

    try:
        # Starlette's Headers is case-insensitive; plain dicts are not, so
        # normalize to be safe either way.
        raw = headers.get(HEADER_NAME)
        if raw is None and hasattr(headers, "items"):
            for k, v in headers.items():
                if k.lower() == HEADER_NAME:
                    raw = v
                    break
    except Exception:
        logger.debug("Could not read headers from request", exc_info=True)
        return None

    if raw is None:
        return None

    team_id = raw.strip()
    return team_id or None
