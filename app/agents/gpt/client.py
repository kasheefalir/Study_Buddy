"""GPT-only reasoning budget and explicit completion validation."""
import logging

import httpx
from app.errors import transport_code

from app.agents.context_budget import estimate, input_limit, reply_reserve
from app.config import settings
from app.llm.ollama_client import OllamaClient, OllamaError
from app.llm.usage import record_usage
from time import monotonic

logger = logging.getLogger(__name__)


class GPTClient(OllamaClient):
    async def chat(self, messages, *, json_mode=False, schema=None):
        started = monotonic()
        reserve = reply_reserve(self.model)
        limit = input_limit(self.model)
        if estimate(messages) > limit:
            raise OllamaError("This GPT request exceeds its input budget. Select fewer materials or narrow the request.", "context_limit")
        payload = {"model": self.model, "messages": messages, "stream": False,
                   "think": "low", "keep_alive": "30m",
                   "options": {"num_ctx": settings.context_window, "num_predict": reserve, "temperature": 0.2}}
        if json_mode:
            payload["format"] = schema or "json"
        try:
            async with httpx.AsyncClient(timeout=max(self.timeout, 240)) as client:
                response = await client.post(self.base_url + "/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
            content = data["message"].get("content", "")
            diagnostic = {"estimated_input_tokens": estimate(messages), "input_budget": limit,
                          "reply_reserved": reserve, "done_reason": data.get("done_reason"),
                          "total_seconds": (data.get("total_duration") or 0) / 1e9,
                          "thinking_characters": len(data["message"].get("thinking") or "")}
            record_usage(data, self.model, diagnostic, wall_seconds=monotonic() - started)
            logger.info("GPT completion: %s", diagnostic)
            if data.get("done") is not True or data.get("done_reason") == "length":
                raise OllamaError("GPT reached its output limit. Try a shorter request.", "output_limit")
            if not isinstance(content, str) or not content.strip():
                raise OllamaError("GPT returned no final response. Please retry.", "empty_response")
            return content.strip()
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise OllamaError("GPT could not complete this request. Check Ollama and retry.", transport_code(exc)) from exc
