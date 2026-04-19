"""Tests for neuralmind.local_client — Ollama client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestOllamaClient:
    """Tests for OllamaClient class."""

    def test_init_reads_config(self):
        """Client initializes with config values."""
        from neuralmind.local_client import OllamaClient

        client = OllamaClient()
        assert hasattr(client, "endpoint")
        assert hasattr(client, "model")
        assert "localhost" in client.endpoint or "11434" in client.endpoint

    def test_query_disabled_returns_message(self):
        """When local models are disabled, query returns an informative message."""
        from neuralmind.local_client import OllamaClient

        client = OllamaClient()
        # Default config has enabled=False
        client.config = {"enabled": False}
        result = client.query("test prompt")
        assert "not enabled" in result.lower()

    def test_query_enabled_success(self):
        """Successful query with mocked httpx response."""
        from neuralmind.local_client import OllamaClient

        client = OllamaClient()
        client.config = {"enabled": True}

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "This is the answer."}
        mock_response.raise_for_status = MagicMock()

        mock_http_client = MagicMock()
        mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
        mock_http_client.__exit__ = MagicMock(return_value=False)
        mock_http_client.post.return_value = mock_response

        with patch("neuralmind.local_client.httpx.Client", return_value=mock_http_client):
            result = client.query("test prompt")

        assert result == "This is the answer."

    def test_query_connection_error(self):
        """Query handles connection errors gracefully."""
        import httpx

        from neuralmind.local_client import OllamaClient

        client = OllamaClient()
        client.config = {"enabled": True}

        mock_http_client = MagicMock()
        mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
        mock_http_client.__exit__ = MagicMock(return_value=False)
        mock_http_client.post.side_effect = httpx.RequestError("Connection refused")

        with patch("neuralmind.local_client.httpx.Client", return_value=mock_http_client):
            result = client.query("test prompt")

        assert "error" in result.lower()

    def test_query_unexpected_error(self):
        """Query handles unexpected errors gracefully."""
        from neuralmind.local_client import OllamaClient

        client = OllamaClient()
        client.config = {"enabled": True}

        mock_http_client = MagicMock()
        mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
        mock_http_client.__exit__ = MagicMock(return_value=False)
        mock_http_client.post.side_effect = RuntimeError("boom")

        with patch("neuralmind.local_client.httpx.Client", return_value=mock_http_client):
            result = client.query("test prompt")

        assert "error" in result.lower() or "unexpected" in result.lower()

    def test_query_empty_response(self):
        """Query handles empty response from the model."""
        from neuralmind.local_client import OllamaClient

        client = OllamaClient()
        client.config = {"enabled": True}

        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_http_client = MagicMock()
        mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
        mock_http_client.__exit__ = MagicMock(return_value=False)
        mock_http_client.post.return_value = mock_response

        with patch("neuralmind.local_client.httpx.Client", return_value=mock_http_client):
            result = client.query("test prompt")

        # Should return the fallback error message
        assert "error" in result.lower() or "no response" in result.lower()
