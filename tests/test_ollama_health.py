import asyncio
import httpx
import pytest
from app.llm.ollama_client import OllamaClient


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
