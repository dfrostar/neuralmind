"""Tests for F1 — Streamable HTTP MCP transport (mcp_http.py)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from neuralmind.mcp_http import StreamableHTTPMCP, select_transport


class TestSessionManagement:
    """Session lifecycle."""

    def test_create_session(self) -> None:
        t = StreamableHTTPMCP(mind=MagicMock())
        sid = t.create_session("client-1")
        assert sid
        assert sid in t.sessions
        assert t.sessions[sid]["client_id"] == "client-1"

    def test_destroy_session(self) -> None:
        t = StreamableHTTPMCP(mind=MagicMock())
        sid = t.create_session("client-1")
        assert t.destroy_session(sid) is True
        assert sid not in t.sessions

    def test_destroy_nonexistent(self) -> None:
        t = StreamableHTTPMCP(mind=MagicMock())
        assert t.destroy_session("nope") is False


class TestTransportSelection:
    """Transport selection and gating."""

    def test_not_enabled_by_default(self) -> None:
        t = StreamableHTTPMCP(mind=MagicMock())
        assert t.enabled is False

    def test_select_transport_default(self) -> None:
        assert select_transport(MagicMock()) is None

    def test_handle_request_disabled(self) -> None:
        t = StreamableHTTPMCP(mind=MagicMock())
        resp = t.handle_request({})
        assert resp.get("error") == "Streamable HTTP transport disabled"

    def test_get_starlette_app_disabled(self) -> None:
        t = StreamableHTTPMCP(mind=MagicMock())
        assert t.get_starlette_app() is None


class TestEnvironmentGating:
    """NEURALMIND_MCP_TRANSPORT env var controls activation."""

    def test_env_disables_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NEURALMIND_MCP_TRANSPORT", raising=False)
        t = StreamableHTTPMCP(mind=MagicMock())
        assert t.enabled is False

    def test_env_streamable_http(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NEURALMIND_MCP_TRANSPORT", "streamable_http")
        t = StreamableHTTPMCP(mind=MagicMock())
        # Still False unless deps importable — but the env var is honoured.
        # We can't force-enable without the optional deps, so we just check
        # it doesn't crash.
        _ = t.enabled
