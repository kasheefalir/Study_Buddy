import asyncio
from dataclasses import replace
import json
import pytest

from app.agents import context_budget as budget
from app.agents.chat_agent import ChatAgent
from app.storage.conversation_store import ConversationStore


def test_long_history_keeps_current_question_sources_and_reply_space(monkeypatch):
    monkeypatch.setattr(budget, "settings", replace(budget.settings, context_window=4096, response_tokens=512))
    history = [{"role": "assistant" if i % 2 else "user", "content": "Earlier discussion " * 1000 + "Latest question?"} for i in range(40)]
    sources = [{"label": f"S{i}", "text": "Relevant study facts. " * 40, "location": "Page 2"} for i in range(12)]
    messages, included, report = budget.pack("You are Professor.", "My exact current question", history, {"saved_study_notes": "Focus on regression"}, sources, 16)
    assert report["estimated_input_tokens"] <= report["input_budget"]
    assert included and messages[-1]["content"] == "My exact current question"
    assert "Latest question?" in messages[-3]["content"]
    assert messages[-2]["content"].startswith("Reviewed session materials")
    assert report["input_budget"] + report["reply_reserved"] + report["safety_margin"] == 4096
    reference = next(m for m in messages if m["content"].startswith("Reviewed session materials"))
    assert json.loads(reference["content"].split("\n", 1)[1]) == included


def test_rolling_summary_survives_reload_without_losing_transcript(tmp_path):
    class Model:
        async def chat(self, messages):
            if "Update a compact" in messages[0]["content"]:
                return "The student is reviewing regression and needs practice with recall."
            return "Let's review recall."
    store = ConversationStore(tmp_path)
    identifier = store.create_id()
    history = [{"role": "assistant" if i % 2 else "user", "content": f"Discuss regression concept {i}"} for i in range(40)]
    store.save(identifier, history)
    asyncio.run(ChatAgent(Model(), store).reply("Continue", identifier))
    reopened = ConversationStore(tmp_path)
    assert reopened.summary(identifier)["through"] == 24
    assert len(reopened.load(identifier)) == 42
    reopened.save(identifier, reopened.load(identifier), memory="Prefer examples")
    assert "recall" in reopened.summary(identifier)["text"]
    assert reopened.load(identifier)[-1]["usage"]["context"]["summarized_messages"] == 24


def test_oversized_current_question_is_not_silently_truncated():
    with pytest.raises(ValueError, match="too long"):
        budget.pack("Professor", "word " * 50_000, [], {}, [], 16)


def test_invalid_summary_keeps_previous_memory_and_all_messages(tmp_path):
    class Model:
        async def structured_plan(self, messages, schema):
            if schema.get("title") == "ResponseReview":
                return '{"action":"accept","issues":[],"repair_request":""}'
            return '{"messages": [{"role": "user", "content": "copied transcript"}]}'

        async def chat(self, messages):
            return "A normal reply."
    store = ConversationStore(tmp_path)
    identifier = store.create_id()
    history = [{"role": "user", "content": f"Study question {i}"} for i in range(40)]
    saved = {"text": "Earlier focus: probability", "through": 2}
    store.save(identifier, history, summary=saved)
    asyncio.run(ChatAgent(Model(), store).reply("Continue", identifier))
    assert store.summary(identifier) == saved
    assert len(store.load(identifier)) == 42
