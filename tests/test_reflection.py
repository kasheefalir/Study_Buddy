import asyncio
import json
from dataclasses import replace

import pytest

from app.agents.reflection import reflect
from app.agents import context_budget
from app.llm.usage import record_usage, track_usage, summarize


class Model:
    def __init__(self, reviews):
        self.reviews = iter(reviews)
        self.calls = []

    async def structured_plan(self, messages, schema):
        self.calls.append(messages)
        assert context_budget.estimate(messages) <= context_budget.input_limit()
        record_usage({"prompt_eval_count": 10, "eval_count": 5}, "test")
        return json.dumps(next(self.reviews))

    async def chat(self, messages):
        self.calls.append(messages)
        assert context_budget.estimate(messages) <= context_budget.input_limit()
        record_usage({"prompt_eval_count": 20, "eval_count": 8}, "test")
        return "Scripts make analysis repeatable [S1]."


def assessment(action, issues=None):
    return {"action": action, "issues": issues or [], "repair_request": "Retrieve the selected tutorial before claiming to summarize it."}


def run(model, **kwargs):
    return asyncio.run(reflect(model, "Summarize this", "The source includes neural networks.",
        "You are a helpful tutor.", [], {}, [], 16, **kwargs))


def test_acceptance_does_not_rewrite():
    model = Model([assessment("accept")])
    answer, _, trace = run(model)
    assert answer == "The source includes neural networks."
    assert trace["status"] == "accepted" and len(model.calls) == 1


def test_retrieval_repair_and_usage_are_bounded():
    model = Model([assessment("retrieve", ["No evidence was retrieved"]), assessment("accept")])
    requested = []
    async def retrieve(feedback):
        requested.append(feedback)
        return [{"label": "S1", "text": "Scripts are repeatable.", "document_id": "a" * 32}]
    with track_usage() as calls:
        answer, sources, trace = run(model, retrieve=retrieve)
    assert len(requested) == 1 and len(model.calls) == 3
    assert sources[0]["label"] == "S1" and "repeatable" in answer
    assert len(trace["reviews"]) == 2
    assert [c["stage"] for c in calls] == ["response review", "response revision", "response review"]
    assert summarize(calls)["input_tokens"] == 40


def test_failed_second_review_does_not_publish_draft():
    model = Model([assessment("revise", ["Unsupported claim"]), assessment("revise", ["Still unsupported"])])
    with pytest.raises(ValueError, match="after one revision"):
        run(model)
    assert len(model.calls) == 3


def test_small_context_stays_within_budget(monkeypatch):
    monkeypatch.setattr(context_budget, "settings", replace(context_budget.settings, context_window=4096, response_tokens=512))
    model = Model([assessment("revise", ["Unclear"]), assessment("accept")])
    asyncio.run(reflect(model, "Explain this", "A long answer. " * 700,
        "You are a tutor.", [], {}, [{"label": "S1", "text": "Evidence. " * 1000}], 16))
    assert len(model.calls) == 3


def test_inconsistent_acceptance_gets_revised():
    model = Model([assessment("accept", ["Wrong source"]), assessment("accept")])
    assert run(model)[0] == "Scripts make analysis repeatable [S1]."


def test_agent_persists_enabled_review_and_usage(tmp_path, monkeypatch):
    from app.agents import chat_agent
    from app.storage.conversation_store import ConversationStore
    monkeypatch.setattr(chat_agent, "settings", replace(chat_agent.settings, response_review_enabled=True))
    store = ConversationStore(tmp_path)
    model = Model([assessment("accept")])
    cid, _ = asyncio.run(chat_agent.ChatAgent(model, store).reply("Explain scripts"))
    reply = store.load(cid)[-1]
    assert reply["reflection"]["status"] == "accepted"
    assert reply["usage"]["calls"][-1]["stage"] == "response review"
