import asyncio
import httpx
import pytest
import json
from dataclasses import replace
from app.llm import ollama_client
from app.llm.ollama_client import OllamaClient


@pytest.mark.parametrize("thinking, expected", [("", "low"), ("false", "low"), ("true", "low"), ("high", "high")])
def test_gpt_oss_named_reasoning_and_structured_output(monkeypatch, thinking, expected):
    client_type = httpx.AsyncClient
    monkeypatch.setattr(ollama_client, "settings", replace(ollama_client.settings, ollama_think=thinking))
    schema = {"type": "object", "properties": {"route": {"type": "string"}}}

    def handle(request):
        payload = json.loads(request.content)
        assert payload["model"] == "gpt-oss:20b"
        assert payload["think"] == expected
        assert payload["format"] == schema
        return httpx.Response(200, json={"message": {"content": '{"route":"conversation"}', "thinking": "private"}})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs))
    result = asyncio.run(OllamaClient("http://localhost:11434", "gpt-oss:20b").structured_plan([
        {"role": "user", "content": "hey"}], schema))
    assert json.loads(result) == {"route": "conversation"}


@pytest.mark.parametrize("done", [True, False])
def test_preload_waits_for_done_without_generating_text(monkeypatch, done):
    client_type = httpx.AsyncClient

    def handle(request):
        assert request.url.path == "/api/chat"
        payload = json.loads(request.content)
        assert payload["messages"] == []
        assert payload["stream"] is False
        assert payload["options"]["num_ctx"] == ollama_client.settings.context_window
        return httpx.Response(200, json={"done": done, "message": {"content": ""}})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs))
    call = OllamaClient("http://localhost:11434", "phi4-mini:latest").preload
    if done:
        asyncio.run(call())
    else:
        with pytest.raises(ollama_client.OllamaError):
            asyncio.run(call())


@pytest.mark.parametrize("loaded", [True, False, None])
def test_health_distinguishes_installed_and_loaded(monkeypatch, loaded):
    client_type = httpx.AsyncClient

    def handle(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "llama3.2:3b"}]})
        if loaded is None:
            return httpx.Response(404)
        return httpx.Response(200, json={"models": [{"name": "llama3.2:3b"}] if loaded else []})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs))
    result = asyncio.run(OllamaClient("http://localhost:11434", "llama3.2:3b").health())
    assert result["model_available"] is True
    assert result["model_loaded"] is loaded


@pytest.mark.parametrize("thinking, expected", [("", None), ("false", False), ("true", True)])
def test_optional_thinking_control(monkeypatch, thinking, expected):
    client_type = httpx.AsyncClient
    monkeypatch.setattr(ollama_client, "settings", replace(ollama_client.settings, ollama_think=thinking))

    def handle(request):
        payload = json.loads(request.content)
        if expected is None:
            assert "think" not in payload
        else:
            assert payload["think"] is expected
        return httpx.Response(200, json={"message": {"content": "Hello"}})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs))
    assert asyncio.run(OllamaClient("http://localhost:11434", "qwen3:4b").chat([
        {"role": "user", "content": "hey"}])) == "Hello"
