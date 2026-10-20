import asyncio

import httpx
from fastapi.testclient import TestClient

from app import main, model_catalog as catalog


def mock_ollama(monkeypatch, handler):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(catalog.httpx, "AsyncClient",
                        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))


def test_discovery_excludes_embeddings(monkeypatch):
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "custom:4b"}, {"name": "embed:latest"}]})
        import json
        name = json.loads(request.content)["model"]
        return httpx.Response(200, json={"capabilities": ["embedding" if name.startswith("embed") else "completion"]})
    mock_ollama(monkeypatch, handler)
    result = TestClient(main.app).get("/api/models")
    assert result.status_code == 200
    assert result.json()["models"] == [{"name": "custom:4b", "size": 0}]
    assert "gpt-oss:20b" in result.json()["recommended"]


def test_download_allowlist_and_concurrency(monkeypatch):
    monkeypatch.setattr(catalog, "download", {"active": True})
    client = TestClient(main.app)
    assert client.post("/api/models/download", json={"model": "arbitrary:huge"}).status_code == 400
    assert client.post("/api/models/download", json={"model": "llama3.2:3b"}).status_code == 409


def test_retired_model_does_not_break_discovery(monkeypatch):
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "retired:cloud"}]})
        return httpx.Response(410, json={"error": "Retired"})
    mock_ollama(monkeypatch, handler)
    result = TestClient(main.app).get("/api/models")
    assert result.status_code == 200
    assert result.json()["models"] == []
    assert result.json()["unavailable"] == ["retired:cloud"]


def test_pull_success_and_failure(monkeypatch):
    monkeypatch.setattr(catalog, "download", {"active": True})
    mock_ollama(monkeypatch, lambda request: httpx.Response(
        200, text='{"status":"pulling","total":100,"completed":50}\n{"status":"success"}\n'))
    asyncio.run(catalog.pull("llama3.2:3b"))
    assert catalog.download["status"] == "success"
    assert not catalog.download["active"]


def test_pull_error_is_retryable(monkeypatch):
    monkeypatch.setattr(catalog, "download", {"active": True})
    mock_ollama(monkeypatch, lambda request: httpx.Response(200, text='{"error":"disk full"}\n'))
    asyncio.run(catalog.pull("llama3.2:3b"))
    assert catalog.download["error"] == "disk full"
    assert not catalog.download["active"]
