"""Opt-in usage analytics: off by default, and never leaks arguments or IPs."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from fpl_mcp import analytics


@pytest.fixture(autouse=True)
def _reset_analytics():
    yield
    analytics._client = None
    analytics._salt = b""


def _server():
    mcp = FastMCP("test")

    @mcp.tool()
    async def lookup(team_id: int) -> dict:
        return {"team": team_id}

    @mcp.tool()
    async def broken() -> dict:
        return {"error": "no such team"}

    @mcp.tool()
    async def explodes() -> dict:
        raise RuntimeError("boom")

    return mcp


def _enable(monkeypatch, mcp):
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_test")
    monkeypatch.setenv("ANALYTICS_SALT", "s" * 32)
    fake = MagicMock()
    with patch("posthog.Posthog", return_value=fake):
        assert analytics.init_analytics(mcp) is True
    return fake


def _fake_request(ip="203.0.113.7", country="IN", session="sess-1"):
    headers = {"cf-connecting-ip": ip, "cf-ipcountry": country}
    if session:
        headers["mcp-session-id"] = session
    request = SimpleNamespace(headers=headers, client=None)
    session = SimpleNamespace(
        client_params=SimpleNamespace(clientInfo=SimpleNamespace(name="claude-ai", version="1.0"))
    )
    return SimpleNamespace(request=request, session=session)


def test_off_without_api_key(monkeypatch):
    monkeypatch.delenv("POSTHOG_API_KEY", raising=False)
    mcp = _server()
    original = mcp._tool_manager.call_tool
    assert analytics.init_analytics(mcp) is False
    assert mcp._tool_manager.call_tool == original
    assert not analytics.is_enabled()


def test_off_with_short_salt(monkeypatch):
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_test")
    monkeypatch.setenv("ANALYTICS_SALT", "short")
    assert analytics.init_analytics(_server()) is False


async def test_tool_call_event_has_no_arguments_or_ip(monkeypatch):
    mcp = _server()
    fake = _enable(monkeypatch, mcp)

    from mcp.server.lowlevel.server import request_ctx

    token = request_ctx.set(_fake_request())
    try:
        await mcp.call_tool("lookup", {"team_id": 6071111})
    finally:
        request_ctx.reset(token)

    kwargs = fake.capture.call_args.kwargs
    assert kwargs["event"] == "tool_called"
    props = kwargs["properties"]
    assert props["tool"] == "lookup"
    assert props["success"] is True
    assert props["client_name"] == "claude-ai"
    assert props["country"] == "IN"
    assert props["$process_person_profile"] is False
    flat = repr(kwargs)
    assert "6071111" not in flat
    assert "203.0.113.7" not in flat
    assert "sess-1" not in flat
    assert kwargs["distinct_id"].startswith("s_")


async def test_same_ip_same_user_different_ip_different_user(monkeypatch):
    mcp = _server()
    fake = _enable(monkeypatch, mcp)
    from mcp.server.lowlevel.server import request_ctx

    ids = []
    for ip in ("203.0.113.7", "203.0.113.7", "198.51.100.1"):
        token = request_ctx.set(_fake_request(ip=ip, session=None))
        try:
            await mcp.call_tool("lookup", {"team_id": 1})
        finally:
            request_ctx.reset(token)
        ids.append(fake.capture.call_args.kwargs["distinct_id"])
    assert ids[0] == ids[1] != ids[2]


async def test_errors_are_recorded_and_still_raised(monkeypatch):
    mcp = _server()
    fake = _enable(monkeypatch, mcp)

    await mcp.call_tool("broken", {})
    props = fake.capture.call_args.kwargs["properties"]
    assert props["success"] is False and props["error_type"] == "returned_error"

    with pytest.raises(Exception):
        await mcp.call_tool("explodes", {})
    props = fake.capture.call_args.kwargs["properties"]
    assert props["success"] is False


async def test_analytics_failure_never_breaks_a_tool_call(monkeypatch):
    mcp = _server()
    fake = _enable(monkeypatch, mcp)
    fake.capture.side_effect = RuntimeError("posthog down")

    result = await mcp.call_tool("lookup", {"team_id": 5})
    assert '"team": 5' in result[0].text


async def test_listing_tools_is_recorded(monkeypatch):
    mcp = _server()
    fake = _enable(monkeypatch, mcp)
    tools = await mcp.list_tools()
    assert len(tools) == 3
    kwargs = fake.capture.call_args.kwargs
    assert kwargs["event"] == "tools_listed"
    assert kwargs["properties"]["tool_count"] == 3


async def test_identity_prefers_team_header_then_session(monkeypatch):
    """Hosted connectors share provider IPs, so IP must be the last resort."""
    mcp = _server()
    fake = _enable(monkeypatch, mcp)
    from mcp.server.lowlevel.server import request_ctx

    async def call(headers):
        ctx = _fake_request()
        ctx.request.headers = headers
        token = request_ctx.set(ctx)
        try:
            await mcp.call_tool("lookup", {"team_id": 1})
        finally:
            request_ctx.reset(token)
        return fake.capture.call_args.kwargs

    shared_ip = {"cf-connecting-ip": "160.79.104.1"}
    a = await call({**shared_ip, "mcp-session-id": "one", "x-fpl-team-id": "6071111"})
    b = await call({**shared_ip, "mcp-session-id": "two"})
    c = await call({**shared_ip, "mcp-session-id": "three"})
    d = await call(shared_ip)

    assert a["properties"]["id_source"] == "team_header"
    assert a["distinct_id"].startswith("t_") and "6071111" not in repr(a)
    assert b["properties"]["id_source"] == "session"
    assert b["distinct_id"] != c["distinct_id"]  # two people, same provider IP
    assert d["properties"]["id_source"] == "ip"
