# src/fpl_mcp/fpl/inbound_limiter.py
"""Inbound HTTP rate limiting for the hosted streamable-http server.

This is a different job from rate_limiter.RateLimiter, which paces this
server's own outbound calls to the FPL API and makes a caller *wait* when
the shared budget is used up. That protects FPL, not us: one heavy or
abusive caller doesn't get throttled, everyone else just queues behind them
on the same 20-requests/60s budget.

This limiter protects the server itself, and sheds instead of queuing: once
a client has made too many requests too fast, further requests from them
get an immediate 429 rather than waiting in line — so a burst from one
caller can't starve everyone else who's sharing this box. Only meaningful
for streamable-http; stdio serves a single local client at a time.
"""
import os
import time
from collections import defaultdict
from typing import Dict, List


class InboundRateLimiter:
    """Non-blocking sliding-window limiter, keyed by caller."""

    def __init__(self, max_requests: int = 30, per_seconds: int = 60):
        self.max_requests = max_requests
        self.time_window = per_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        """Return True and record the hit if `key` is under budget.

        Returns False immediately (no waiting) if `key` is over budget.
        """
        now = time.time()
        window = self._requests[key]

        cutoff = now - self.time_window
        drop = 0
        while drop < len(window) and window[drop] < cutoff:
            drop += 1
        if drop:
            del window[:drop]

        if len(window) >= self.max_requests:
            return False

        window.append(now)
        return True


# Shared instance for the process. Defaults are generous enough for one
# person's normal back-and-forth (a few tool calls per message) while still
# capping a runaway client. Override via env if friends' usage patterns need it.
inbound_limiter = InboundRateLimiter(
    max_requests=int(os.environ.get("FPL_MCP_INBOUND_MAX_REQUESTS", "30")),
    per_seconds=int(os.environ.get("FPL_MCP_INBOUND_PERIOD_SECONDS", "60")),
)
