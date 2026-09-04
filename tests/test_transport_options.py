"""Tests for the transport command-line options.

The server defaults to stdio, so existing configurations must keep working
untouched. The HTTP transports are opt-in, and hosting one behind a domain
requires telling it which Host headers to trust — the SDK rejects anything
not on that list with HTTP 421.
"""

import pytest

from fpl_mcp.__main__ import _build_arg_parser, _build_transport_security


def _parse(argv):
    return _build_arg_parser().parse_args(argv)


def test_defaults_are_stdio_and_loopback():
    """No arguments must mean the previous behaviour, unchanged."""
    args = _parse([])

    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.path == "/mcp"
    assert args.allowed_hosts is None


def test_http_options_parse():
    args = _parse(
        [
            "--transport", "streamable-http",
            "--host", "0.0.0.0",
            "--port", "9000",
            "--path", "/fpl",
            "--allowed-host", "fpl.example.com",
        ]
    )

    assert args.transport == "streamable-http"
    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.path == "/fpl"
    assert args.allowed_hosts == ["fpl.example.com"]


def test_allowed_host_is_repeatable():
    args = _parse(
        ["--allowed-host", "a.example.com", "--allowed-host", "b.example.com"]
    )

    assert args.allowed_hosts == ["a.example.com", "b.example.com"]


def test_unknown_transport_is_rejected():
    with pytest.raises(SystemExit):
        _parse(["--transport", "carrier-pigeon"])


def test_environment_variables_supply_defaults(monkeypatch):
    monkeypatch.setenv("FPL_MCP_TRANSPORT", "sse")
    monkeypatch.setenv("FPL_MCP_HOST", "10.0.0.5")
    monkeypatch.setenv("FPL_MCP_PORT", "8123")
    monkeypatch.setenv("FPL_MCP_PATH", "/custom")

    args = _parse([])

    assert (args.transport, args.host, args.port, args.path) == (
        "sse",
        "10.0.0.5",
        8123,
        "/custom",
    )


def test_explicit_flags_beat_environment_variables(monkeypatch):
    monkeypatch.setenv("FPL_MCP_PORT", "8123")

    assert _parse(["--port", "9999"]).port == 9999


class TestTransportSecurity:
    """`--allowed-host` has to accept the Host header a proxy actually sends."""

    def test_public_host_is_trusted_with_and_without_a_port(self):
        settings = _build_transport_security(["fpl.example.com"], 8000)

        # HTTPS on 443 sends no port; other ports appear in the header.
        assert "fpl.example.com" in settings.allowed_hosts
        assert "fpl.example.com:*" in settings.allowed_hosts

    def test_loopback_is_always_kept(self):
        """Local testing and health checks must not break when hosting."""
        settings = _build_transport_security(["fpl.example.com"], 8000)

        assert "127.0.0.1:8000" in settings.allowed_hosts
        assert "localhost:8000" in settings.allowed_hosts

    def test_origins_cover_the_named_hosts(self):
        settings = _build_transport_security(["fpl.example.com"], 8000)

        assert "https://fpl.example.com" in settings.allowed_origins

    def test_a_pasted_url_is_reduced_to_its_hostname(self):
        """People paste what they know: the URL they connect to."""
        settings = _build_transport_security(["https://fpl.example.com/mcp"], 8000)

        assert "fpl.example.com" in settings.allowed_hosts
        assert "https://fpl.example.com/mcp" not in settings.allowed_hosts

    def test_several_hosts_are_all_trusted(self):
        settings = _build_transport_security(["a.example.com", "b.example.com"], 8000)

        assert "a.example.com" in settings.allowed_hosts
        assert "b.example.com" in settings.allowed_hosts

    def test_blank_entries_are_ignored(self):
        settings = _build_transport_security(["", "   ", "fpl.example.com"], 8000)

        assert "" not in settings.allowed_hosts
        assert "fpl.example.com" in settings.allowed_hosts
