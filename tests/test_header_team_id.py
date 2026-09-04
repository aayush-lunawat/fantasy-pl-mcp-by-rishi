"""Tests for per-request team ID resolution (the hosted-server header path).

The shared server can't store a team ID per person, so a Claude connector
sends each caller's own team ID as a custom X-FPL-Team-ID request header.
FPLAuthManager.team_id must prefer that header when one is present, and
fall back to whatever team ID the process itself was configured with
(self-hosted / stdio usage, or no header sent) otherwise.
"""
from unittest.mock import MagicMock, patch

from fpl_mcp.fpl.auth_manager import FPLAuthManager
from fpl_mcp.fpl.request_context import get_header_team_id


def _make_manager(refresh_token=None, team_id=None):
    with patch("fpl_mcp.fpl.auth_manager.CredentialManager") as mock_cm:
        instance = mock_cm.return_value
        instance.migrate_legacy_credentials.return_value = None
        instance.load_credentials.return_value = (refresh_token, team_id)
        return FPLAuthManager()


def _request_ctx_with_header(value):
    """A stand-in for mcp's request_ctx.get() carrying one header."""
    fake_request = MagicMock()
    fake_request.headers = {"x-fpl-team-id": value} if value is not None else {}
    fake_ctx = MagicMock()
    fake_ctx.request = fake_request
    return fake_ctx


def test_get_header_team_id_returns_none_outside_a_request():
    """CLI usage (fpl-mcp-config test) and stdio have no request_ctx set at all."""
    with patch("mcp.server.lowlevel.server.request_ctx") as mock_var:
        mock_var.get.side_effect = LookupError
        assert get_header_team_id() is None


def test_get_header_team_id_returns_none_for_stdio():
    """stdio requests are set in request_ctx but carry no HTTP request."""
    fake_ctx = MagicMock()
    fake_ctx.request = None
    with patch("mcp.server.lowlevel.server.request_ctx") as mock_var:
        mock_var.get.return_value = fake_ctx
        assert get_header_team_id() is None


def test_get_header_team_id_reads_the_header():
    with patch("mcp.server.lowlevel.server.request_ctx") as mock_var:
        mock_var.get.return_value = _request_ctx_with_header("6071111")
        assert get_header_team_id() == "6071111"


def test_get_header_team_id_strips_whitespace_and_treats_blank_as_absent():
    with patch("mcp.server.lowlevel.server.request_ctx") as mock_var:
        mock_var.get.return_value = _request_ctx_with_header("  6071111  ")
        assert get_header_team_id() == "6071111"

        mock_var.get.return_value = _request_ctx_with_header("   ")
        assert get_header_team_id() is None


def test_auth_manager_team_id_prefers_the_header_over_the_stored_default():
    """Two friends sharing the hosted server must each see their own team."""
    manager = _make_manager(team_id="1111")  # process default, e.g. FPL_TEAM_ID
    with patch(
        "fpl_mcp.fpl.request_context.get_header_team_id", return_value="2222"
    ):
        assert manager.team_id == "2222"


def test_auth_manager_team_id_falls_back_with_no_header():
    """Self-hosted / stdio usage: no header exists, so the stored default wins."""
    manager = _make_manager(team_id="1111")
    with patch("fpl_mcp.fpl.request_context.get_header_team_id", return_value=None):
        assert manager.team_id == "1111"
