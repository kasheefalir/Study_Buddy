from __future__ import annotations

import logging
from typing import Any

import httpx
from app.llm.usage import record_usage
from app.config import settings
from app.agents.context_budget import estimate, input_limit

logger = logging.getLogger(__name__)


class OllamaError(RuntimeError):
    """Raised when the local Ollama service cannot complete a request."""


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: float = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                models = [item.get("name", "") for item in response.json().get("models", [])]
        except (httpx.HTTPError, ValueError) as exc:
            return {"connected": False, "model": self.model, "model_available": False, "error": str(exc)}

        available = self.model in models or any(name.startswith(f"{self.model}:") for name in models)
        loaded = None
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                running = await client.get(f"{self.base_url}/api/ps")
                running.raise_for_status()
                names = [item.get("name", item.get("model", "")) for item in running.json().get("models", [])]
                loaded = self.model in names or f"{self.model}:latest" in names
        except (httpx.HTTPError, ValueError):
            logger.warning("Could not verify loaded Ollama models")
        return {"connected": True, "model": self.model, "model_available": available,
                "model_loaded": loaded, "models": models}

    async def plan(self, messages: list[dict[str, str]]) -> str:
        return await self.chat(messages, json_mode=True)

    async def structured_plan(self, messages, schema):
        return await self.chat(messages, json_mode=True, schema=schema)

    async def chat(self, messages: list[dict[str, str]], *, json_mode: bool = False, schema=None) -> str:
        if estimate(messages) > input_limit():
            raise OllamaError("This study request exceeds the configured context budget. Use a smaller material batch or increase CONTEXT_WINDOW.")
        payload = {"model": self.model, "messages": messages, "stream": False, "keep_alive": "30m",
                   "options": {"num_ctx": settings.context_window, "num_predict": settings.response_tokens, "temperature": 0.2}}
        if json_mode:
            payload["format"] = schema or "json"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                record_usage(data, self.model, {"estimated_input_tokens": estimate(messages),
                    "input_budget": input_limit(), "reply_reserved": settings.response_tokens})
                content = data["message"]["content"]
        except httpx.ConnectError as exc:
            raise OllamaError("Ollama is not running. Start Ollama and try again.") from exc
        except httpx.TimeoutException as exc:
            raise OllamaError("The local model took too long to respond.") from exc
        except (httpx.HTTPStatusError, KeyError, TypeError, ValueError) as exc:
            logger.exception("Ollama returned an invalid response")
            raise OllamaError("Ollama could not complete the request. Check that the configured model is installed.") from exc

        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama returned an empty response.")
        return content.strip()
