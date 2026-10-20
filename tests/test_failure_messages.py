import asyncio

import httpx
import pytest

from app import main
from app.errors import StudyError, transport_code
from app.llm.ollama_client import OllamaError
from app.agents.study_tools import StudyResponseError


@pytest.mark.parametrize("failure,status,code", [
    (OllamaError("offline", "ollama_offline"), 503, "ollama_offline"),
    (OllamaError("timeout", "model_timeout"), 503, "model_timeout"),
    (OllamaError("length", "output_limit"), 503, "output_limit"),
    (StudyError("quiz failed", "quiz_generation"), 400, "quiz_generation"),
    (StudyResponseError("choice feedback"), 400, "quiz_feedback"),
    (ValueError("Invalid material ID"), 400, "invalid_request"),
    (RuntimeError("private diagnostic"), 500, "unexpected"),
])
def test_chat_returns_stable_error_code(monkeypatch, failure, status, code):
    class Agent:
        async def reply(self, *args, **kwargs):
            raise failure

    monkeypatch.setattr(main, "agent", Agent())

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                     base_url="http://test") as client:
            response = await client.post("/api/chat", json={"message": "quiz me"})
        assert response.status_code == status
        assert response.headers["X-Study-Error"] == code
        assert "private diagnostic" not in response.text

    asyncio.run(run())


@pytest.mark.parametrize("status,code", [
    (401, "model_access"), (403, "model_access"), (429, "rate_limit"),
    (404, "model_missing"), (500, "model_service"),
])
def test_transport_status_categories(status, code):
    request = httpx.Request("POST", "http://localhost/api/chat")
    response = httpx.Response(status, request=request)
    assert transport_code(httpx.HTTPStatusError("failed", request=request, response=response)) == code


def test_transport_timeout_and_connection_are_distinct():
    assert transport_code(httpx.ReadTimeout("timeout")) == "model_timeout"
    assert transport_code(httpx.ConnectError("offline")) == "ollama_offline"
