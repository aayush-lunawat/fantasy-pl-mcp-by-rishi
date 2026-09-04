"""Inbound HTTP rate limiting: sheds excess requests instead of queuing them.

Distinct from the outbound FPL rate limiter (tests/test_rate_limiter.py),
which paces our calls to FPL's API and makes a caller wait. This one caps
how fast one client can call the shared server before further calls get an
immediate 429 — see fpl.inbound_limiter and http_middleware for why.
"""
import asyncio

from fpl_mcp.fpl.inbound_limiter import InboundRateLimiter
from fpl_mcp.http_middleware import InboundRateLimitMiddleware, _client_key


def test_allows_up_to_the_limit_then_rejects():
    limiter = InboundRateLimiter(max_requests=3, per_seconds=60)
    key = "1.2.3.4"

    assert limiter.allow(key) is True
    assert limiter.allow(key) is True
    assert limiter.allow(key) is True
    assert limiter.allow(key) is False  # 4th request in the window: shed


def test_different_keys_have_independent_budgets():
    """One heavy caller must not use up another caller's budget."""
    limiter = InboundRateLimiter(max_requests=1, per_seconds=60)

    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is False
    assert limiter.allow("client-b") is True  # unaffected by client-a


def test_old_requests_age_out_of_the_window():
    limiter = InboundRateLimiter(max_requests=1, per_seconds=60)
    key = "1.2.3.4"

    assert limiter.allow(key) is True
    assert limiter.allow(key) is False

    # Simulate the window having passed.
    limiter._requests[key] = [0.0]
    assert limiter.allow(key) is True


def test_client_key_prefers_x_forwarded_for():
    scope = {
        "headers": [(b"x-forwarded-for", b"9.9.9.9, 10.0.0.1")],
        "client": ("127.0.0.1", 12345),
    }
    assert _client_key(scope) == "9.9.9.9"


def test_client_key_falls_back_to_direct_peer():
    scope = {"headers": [], "client": ("5.6.7.8", 12345)}
    assert _client_key(scope) == "5.6.7.8"


async def test_middleware_rejects_with_429_once_over_budget():
    async def downstream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    limiter = InboundRateLimiter(max_requests=1, per_seconds=60)
    import fpl_mcp.http_middleware as mod
    from unittest.mock import patch

    with patch.object(mod, "inbound_limiter", limiter):
        middleware = InboundRateLimitMiddleware(downstream)
        scope = {"type": "http", "headers": [], "client": ("5.6.7.8", 1)}

        sent = []

        async def send(message):
            sent.append(message)

        async def receive():
            return {"type": "http.request"}

        await middleware(scope, receive, send)  # 1st: allowed, hits downstream
        assert sent[-1]["body"] == b"ok"

        sent.clear()
        await middleware(scope, receive, send)  # 2nd: shed
        assert sent[0]["status"] == 429
