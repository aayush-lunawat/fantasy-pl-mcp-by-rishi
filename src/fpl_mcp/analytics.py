# src/fpl_mcp/analytics.py
"""Anonymous, opt-in usage analytics for hosted deployments.

Off unless POSTHOG_API_KEY is set, so desktop/stdio users and self-hosters
send nothing. When on, each MCP tool call produces one PostHog event:

    tool_called   tool, success, error_type, duration_ms,
                  client_name, client_version, country, mcp_session
    tools_listed  client_name, client_version, country, mcp_session
                  (a client connected and fetched the tool list)

What is never sent: tool arguments (team IDs, league IDs, player names),
tool results, raw IP addresses, request headers. The distinct ID is a keyed
hash of the caller's IP (HMAC-SHA256 with ANALYTICS_SALT), so the same
caller counts as one user over time without the IP being recoverable from
PostHog. Country comes from Cloudflare's CF-IPCountry header, not GeoIP;
PostHog's own GeoIP is disabled because it would only see this server's IP.

Events are queued and sent by the PostHog SDK's background thread, so a
tool call never waits on analytics, and an analytics failure never fails a
tool call.
"""
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_client = None
_salt = b""
_server_version = "unknown"


def _header(request: Any, name: str) -> Optional[str]:
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    try:
        value = headers.get(name)
    except Exception:
        return None
    return value.strip() if isinstance(value, str) and value.strip() else None


def _caller_ip(request: Any) -> Optional[str]:
    ip = _header(request, "cf-connecting-ip")
    if ip:
        return ip
    xff = _header(request, "x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    client = getattr(request, "client", None)
    return getattr(client, "host", None)


def _distinct_id(ip: Optional[str]) -> str:
    if not ip:
        return "anonymous"
    return "u_" + hmac.new(_salt, ip.encode(), hashlib.sha256).hexdigest()[:24]


def _request_context() -> dict:
    """Who is calling, from the current MCP request. Empty outside a request."""
    try:
        from mcp.server.lowlevel.server import request_ctx

        ctx = request_ctx.get()
    except Exception:
        return {"distinct_id": "anonymous"}

    props: dict = {}
    try:
        params = ctx.session.client_params
        info = getattr(params, "clientInfo", None) if params else None
        if info is not None:
            props["client_name"] = getattr(info, "name", None)
            props["client_version"] = getattr(info, "version", None)
    except Exception:
        pass

    request = getattr(ctx, "request", None)
    ip = _caller_ip(request) if request is not None else None
    props["distinct_id"] = _distinct_id(ip)
    if request is not None:
        props["country"] = _header(request, "cf-ipcountry")
        session = _header(request, "mcp-session-id")
        if session:
            props["mcp_session"] = hmac.new(
                _salt, session.encode(), hashlib.sha256
            ).hexdigest()[:16]
    return props


def _result_has_error(result: Any) -> bool:
    """Whether a tool returned {"error": ...} rather than raising.

    The tool manager hands back the raw dict, a (content, structured) tuple,
    or a list of content blocks depending on the tool's return annotation.
    """
    try:
        if isinstance(result, tuple) and len(result) == 2:
            structured = result[1]
            if isinstance(structured, dict):
                inner = structured.get("result", structured)
                return isinstance(inner, dict) and bool(inner.get("error"))
            result = result[0]
        if isinstance(result, dict):
            return bool(result.get("error"))
        if isinstance(result, (list, tuple)) and result:
            text = getattr(result[0], "text", None)
            if isinstance(text, str) and text.lstrip().startswith("{"):
                parsed = json.loads(text)
                return isinstance(parsed, dict) and bool(parsed.get("error"))
    except Exception:
        pass
    return False


def _capture(event: str, properties: dict) -> None:
    if _client is None:
        return
    try:
        context = _request_context()
        distinct_id = context.pop("distinct_id")
        props = {k: v for k, v in {**context, **properties}.items() if v is not None}
        props.update(
            {
                "server_version": _server_version,
                "$geoip_disable": True,
                "$process_person_profile": False,
            }
        )
        _client.capture(distinct_id=distinct_id, event=event, properties=props)
    except Exception:
        logger.debug("analytics capture failed", exc_info=True)


def is_enabled() -> bool:
    return _client is not None


def init_analytics(mcp) -> bool:
    """Wrap the server's tool manager with event capture if configured.

    Returns True when analytics is on. Safe to call once at startup; does
    nothing (and imports nothing) when POSTHOG_API_KEY is unset.
    """
    global _client, _salt, _server_version

    api_key = os.environ.get("POSTHOG_API_KEY", "").strip()
    if not api_key:
        logger.info("Analytics off (POSTHOG_API_KEY not set)")
        return False

    salt = os.environ.get("ANALYTICS_SALT", "").strip()
    if len(salt) < 16:
        logger.warning("Analytics off: ANALYTICS_SALT must be at least 16 characters")
        return False

    try:
        from posthog import Posthog
    except ImportError:
        logger.warning("Analytics off: install the 'analytics' extra (posthog)")
        return False

    try:
        from importlib.metadata import version

        _server_version = version("fpl-mcp")
    except Exception:
        pass

    _salt = salt.encode()
    _client = Posthog(
        api_key,
        host=os.environ.get("POSTHOG_HOST", "https://us.i.posthog.com"),
        disable_geoip=True,
    )

    manager = mcp._tool_manager
    original_call = manager.call_tool
    original_list = manager.list_tools

    async def call_tool(name, arguments, *args, **kwargs):
        started = time.perf_counter()
        error_type = None
        try:
            result = await original_call(name, arguments, *args, **kwargs)
            # Many tools report failure as {"error": ...} instead of raising.
            if _result_has_error(result):
                error_type = "returned_error"
            return result
        except Exception as exc:
            error_type = type(exc).__name__
            raise
        finally:
            _capture(
                "tool_called",
                {
                    "tool": name,
                    "success": error_type is None,
                    "error_type": error_type,
                    "duration_ms": round((time.perf_counter() - started) * 1000),
                },
            )

    def list_tools(*args, **kwargs):
        tools = original_list(*args, **kwargs)
        _capture("tools_listed", {"tool_count": len(tools)})
        return tools

    manager.call_tool = call_tool
    manager.list_tools = list_tools

    import atexit

    atexit.register(shutdown)
    logger.info("Analytics on (PostHog); tool names and timings only, no arguments")
    return True


def shutdown() -> None:
    """Flush queued events. Called at process exit."""
    if _client is not None:
        try:
            _client.shutdown()
        except Exception:
            pass
