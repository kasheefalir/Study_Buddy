"""DeepSeek-only inference policy, including reasoning headroom and completion checks."""
import logging

import httpx

from app.agents.context_budget import estimate
from app.config import settings
from app.llm.ollama_client import OllamaClient, OllamaError
from app.llm.usage import record_usage

logger = logging.getLogger(__name__)


class DeepSeekClient(OllamaClient):
    async def control_plan(self, messages, schema):
        return await self._complete(messages, json_mode=True, schema=schema, control=True)

    async def chat(self, messages, *, json_mode=False, schema=None):
        return await self._complete(messages, json_mode=json_mode, schema=schema)

    async def _complete(self, messages, *, json_mode=False, schema=None, control=False):
        reserve = 4096 if json_mode else 6144
        limit = settings.context_window - reserve - 512
        if estimate(messages) > limit:
            raise OllamaError("DeepSeek needs more reasoning headroom. Narrow this request or select fewer materials.")
        payload = {"model": self.model, "messages": messages, "stream": False,
                   "think": True, "keep_alive": "30m",
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
                          "reply_reserved": reserve, "control_stage": control, "done_reason": data.get("done_reason"),
                          "total_seconds": (data.get("total_duration") or 0) / 1e9,
                          "load_seconds": (data.get("load_duration") or 0) / 1e9,
                          "generation_seconds": (data.get("eval_duration") or 0) / 1e9,
                          "thinking_characters": len(data["message"].get("thinking") or "")}
            record_usage(data, self.model, diagnostic)
            logger.info("DeepSeek completion: %s", diagnostic)
            if data.get("done") is not True or data.get("done_reason") == "length":
                raise OllamaError("DeepSeek reached its reasoning limit before completing this step. Please retry or choose another model.")
            if not isinstance(content, str) or not content.strip():
                raise OllamaError("DeepSeek produced no final response. Please retry or choose another model.")
            return content.strip()
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise OllamaError("DeepSeek could not complete this step. Check Ollama and retry; no task progress was saved.") from exc
