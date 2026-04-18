"""Tests for neuralmind.local_client."""

from unittest.mock import MagicMock

import httpx


def test_query_returns_disabled_message_when_local_models_disabled(monkeypatch):
    from neuralmind import local_client

    monkeypatch.setattr(local_client, "CONFIG", {"local_models": {"enabled": False}})
    client = local_client.OllamaClient()

    result = client.query("hello")

    assert result == "Local model support is not enabled in the configuration."


def test_query_returns_model_response(monkeypatch):
    from neuralmind import local_client

    monkeypatch.setattr(
        local_client,
        "CONFIG",
        {
            "local_models": {
                "enabled": True,
                "endpoint": "http://localhost:11434",
                "model": "llama3.1",
            }
        },
    )

    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"response": "model says hi"}

    http_client = MagicMock()
    http_client.post.return_value = response

    client_cm = MagicMock()
    client_cm.__enter__.return_value = http_client
    client_cm.__exit__.return_value = False
    monkeypatch.setattr(local_client.httpx, "Client", MagicMock(return_value=client_cm))

    client = local_client.OllamaClient()
    result = client.query("hi")

    assert result == "model says hi"
    http_client.post.assert_called_once_with(
        "http://localhost:11434/api/generate",
        json={"model": "llama3.1", "prompt": "hi", "stream": False},
        timeout=60.0,
    )


def test_query_returns_default_when_response_key_missing(monkeypatch):
    from neuralmind import local_client

    monkeypatch.setattr(
        local_client,
        "CONFIG",
        {"local_models": {"enabled": True, "endpoint": "http://localhost:11434", "model": "llama3.1"}},
    )

    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {}

    http_client = MagicMock()
    http_client.post.return_value = response

    client_cm = MagicMock()
    client_cm.__enter__.return_value = http_client
    client_cm.__exit__.return_value = False
    monkeypatch.setattr(local_client.httpx, "Client", MagicMock(return_value=client_cm))

    client = local_client.OllamaClient()

    assert client.query("hello") == "Error: No response from model."


def test_query_handles_httpx_request_error(monkeypatch):
    from neuralmind import local_client

    monkeypatch.setattr(
        local_client,
        "CONFIG",
        {"local_models": {"enabled": True, "endpoint": "http://localhost:11434", "model": "llama3.1"}},
    )

    request = httpx.Request("POST", "http://localhost:11434/api/generate")
    request_error = httpx.RequestError("network issue", request=request)

    http_client = MagicMock()
    http_client.post.side_effect = request_error

    client_cm = MagicMock()
    client_cm.__enter__.return_value = http_client
    client_cm.__exit__.return_value = False
    monkeypatch.setattr(local_client.httpx, "Client", MagicMock(return_value=client_cm))

    client = local_client.OllamaClient()
    result = client.query("hello")

    assert "Error connecting to Ollama" in result


def test_query_handles_unexpected_exception(monkeypatch):
    from neuralmind import local_client

    monkeypatch.setattr(
        local_client,
        "CONFIG",
        {"local_models": {"enabled": True, "endpoint": "http://localhost:11434", "model": "llama3.1"}},
    )

    response = MagicMock()
    response.raise_for_status.side_effect = RuntimeError("boom")

    http_client = MagicMock()
    http_client.post.return_value = response

    client_cm = MagicMock()
    client_cm.__enter__.return_value = http_client
    client_cm.__exit__.return_value = False
    monkeypatch.setattr(local_client.httpx, "Client", MagicMock(return_value=client_cm))

    client = local_client.OllamaClient()
    result = client.query("hello")

    assert "An unexpected error occurred: boom" == result

