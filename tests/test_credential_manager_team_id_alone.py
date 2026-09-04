"""FPL_TEAM_ID must work on its own, with no refresh token set.

A self-hoster who only wants public data about their own team shouldn't
need to hand over a refresh token just to say which team is theirs.
_load_legacy_credentials used to require both env vars together and
silently discard a lone FPL_TEAM_ID.
"""
import os
from unittest.mock import patch

import pytest

from fpl_mcp.fpl.credential_manager import CredentialManager


@pytest.fixture
def manager(tmp_path):
    with patch.object(CredentialManager, "__init__", lambda self: None):
        cm = CredentialManager()
        cm._config_dir = tmp_path
        cm._encrypted_file = tmp_path / "credentials.enc"
        cm._legacy_env_file = tmp_path / ".env"
        cm._legacy_json_file = tmp_path / "config.json"
        return cm


def test_team_id_alone_is_loaded(manager, monkeypatch):
    monkeypatch.delenv("FPL_REFRESH_TOKEN", raising=False)
    monkeypatch.setenv("FPL_TEAM_ID", "6071111")

    refresh_token, team_id = manager.load_credentials()

    assert team_id == "6071111"
    assert refresh_token is None


def test_refresh_token_alone_is_still_loaded(manager, monkeypatch):
    """The reverse case shouldn't regress either."""
    monkeypatch.setenv("FPL_REFRESH_TOKEN", "sometoken")
    monkeypatch.delenv("FPL_TEAM_ID", raising=False)

    refresh_token, team_id = manager.load_credentials()

    assert refresh_token == "sometoken"
    assert team_id is None


def test_neither_set_returns_none_none(manager, monkeypatch):
    monkeypatch.delenv("FPL_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("FPL_TEAM_ID", raising=False)

    assert manager.load_credentials() == (None, None)


def test_has_credentials_still_requires_both(manager, monkeypatch):
    """A team ID alone must not look like 'can authenticate'."""
    monkeypatch.delenv("FPL_REFRESH_TOKEN", raising=False)
    monkeypatch.setenv("FPL_TEAM_ID", "6071111")

    assert manager.has_credentials() is False
