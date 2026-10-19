import asyncio
import json

import httpx
import pytest

from app import main
from app.agents.deepseek.agent import DeepSeekAgent
from app.agents.deepseek.client import DeepSeekClient
from app.agents.deepseek.planning import Route
from app.llm.ollama_client import OllamaClient, OllamaError
from app.storage.conversation_store import ConversationStore


def test_dispatch_is_isolated(tmp_path):
    store = ConversationStore(tmp_path)
    for model in ("llama3.2:3b", "phi4-mini:latest"):
        client = OllamaClient("http://localhost", model)
        agent = main.selected_agent(client, store)
        assert type(agent) is main.ChatAgent
        assert agent.llm is client
    client = OllamaClient("http://localhost", "deepseek-r1:8b")
    agent = main.selected_agent(client, store)
    assert type(agent) is DeepSeekAgent
    assert type(agent.llm) is DeepSeekClient
    assert client.model == "deepseek-r1:8b"


def test_invalid_router_never_answers_or_saves(tmp_path):
    class Invalid:
        async def structured_plan(self, *args):
            return '{}'

        async def chat(self, *args):
            pytest.fail("Invalid intent must never fall through to chat")

    store = ConversationStore(tmp_path)
    cid = store.create_id()
    store.save(cid, [], quiz={"active": True, "pending_question": "Original"})
    with pytest.raises(ValueError, match="valid action"):
        asyncio.run(DeepSeekAgent(Invalid(), store).reply("hey", cid, document_ids=[]))
    assert store.load(cid) == []
    assert store.quiz(cid)["active"] is True


def test_conversation_pauses_without_discarding_quiz(tmp_path):
    class Fake:
        async def structured_plan(self, *args):
            assert "Required output schema" in args[0][0]["content"]
            return Route(route="conversation", question="How are you?", action="pause", clarification="").model_dump_json()

        async def chat(self, *args):
            return "Hello!"

    store = ConversationStore(tmp_path)
    cid = store.create_id()
    bank = [{"question": "Original"}]
    store.save(cid, [], quiz={"active": True, "prepared_questions": bank})
    asyncio.run(DeepSeekAgent(Fake(), store).reply("How are you?", cid, document_ids=[]))
    state = store.quiz(cid)
    assert state["paused"] and not state["active"]
    assert state["prepared_questions"] == bank


def test_retrieval_without_material_does_not_fall_through(tmp_path):
    class Fake:
        async def structured_plan(self, *args):
            return Route(route="retrieve", question="What does the book say?", action="keep", clarification="").model_dump_json()

        async def chat(self, *args):
            pytest.fail("A source request cannot become a general-knowledge answer")

    store = ConversationStore(tmp_path)
    cid, reply = asyncio.run(DeepSeekAgent(Fake(), store).reply("What does the book say?", document_ids=[]))
    assert "Select a material" in reply
    assert store.load(cid)[-1]["sources"] == []


def test_quiz_failure_preserves_saved_state(tmp_path, monkeypatch):
    import app.agents.deepseek.agent as module

    class Fake:
        async def structured_plan(self, *args):
            return Route(route="quiz", question="New quiz", action="start", clarification="").model_dump_json()

    async def failed(*args, **kwargs):
        raise OllamaError("Failed preparation")

    monkeypatch.setattr(module, "quiz_turn", failed)
    store = ConversationStore(tmp_path)
    cid = store.create_id()
    old = {"active": True, "pending_question": "Keep me", "results": [{"verdict": "correct"}]}
    store.save(cid, [], quiz=old)
    with pytest.raises(OllamaError):
        asyncio.run(DeepSeekAgent(Fake(), store).reply("New quiz", cid, document_ids=[]))
    assert store.quiz(cid) == old
    assert store.load(cid) == []


def test_search_rejects_out_of_scope_tool(monkeypatch):
    import importlib
    search_module = importlib.import_module("app.agents.deepseek.search")
    monkeypatch.setattr(search_module, "library", lambda *args: [({"id": "allowed", "name": "Book"}, [])])

    class Fake:
        async def structured_plan(self, *args):
            return json.dumps({"reads": [{"tool": "search", "document_id": "other", "query": "secret"}], "clarification": ""})

    with pytest.raises(ValueError, match="outside this session"):
        asyncio.run(search_module.search(Fake(), None, ["allowed"], "question"))


def test_next_uses_saved_bank_without_intent_or_model(tmp_path):
    class NoModel:
        async def structured_plan(self, *args):
            pytest.fail("Prepared next question must not call a model")

    store = ConversationStore(tmp_path)
    cid = store.create_id()
    second = {"question_id": "q2", "pending_question": "Second question?", "options": ["A", "B", "C", "D"],
              "correct_index": 1, "expected_answer": "B", "sources": [], "answer_key": "B"}
    store.save(cid, [], quiz={"version": 2, "document_ids": [], "active": True, "phase": "review",
                             "question_id": "q1", "cursor": 0, "total": 2, "results": [],
                             "prepared_questions": [{}, second], "pending_question": "First question?"})
    _, response = asyncio.run(DeepSeekAgent(NoModel(), store).reply("Next question", cid, document_ids=[], next_question_id="q1"))
    assert "Second question?" in response
    assert store.quiz(cid)["question_id"] == "q2"
    assert store.load(cid)[-1]["quiz_question"]["id"] == "q2"


def test_comparison_executes_both_searches_and_stops(monkeypatch):
    import importlib
    module = importlib.import_module("app.agents.deepseek.search")
    chunks = [{"id": i, "location": f"Page {i}", "text": word} for i, word in enumerate(["alpha", "beta"])]
    monkeypatch.setattr(module, "library", lambda *args: [({"id": "book", "name": "Book"}, chunks)])
    seen = []

    async def retrieve(root, item, chunks, query, k):
        seen.append(query)
        return [chunks[len(seen) - 1]]

    monkeypatch.setattr(module, "retrieve", retrieve)

    class Fake:
        count = 0

        async def structured_plan(self, *args):
            self.count += 1
            return json.dumps({"reads": [{"tool": "search", "document_id": "book", "query": query}
                                         for query in ("alpha", "beta")] if self.count == 1 else [], "clarification": ""})

    sources, calls, clarification = asyncio.run(module.search(Fake(), None, ["book"], "Compare alpha and beta"))
    assert seen == ["alpha", "beta"]
    assert [s["label"] for s in sources] == ["S1", "S2"]
    assert len(calls) == 2 and not clarification


@pytest.mark.parametrize("reason", ["stop", "length"])
def test_reasoning_budget_and_truncation(monkeypatch, reason):
    captured = []

    async def post(self, url, **kwargs):
        captured.append(kwargs["json"])
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "done": True, "done_reason": reason, "message": {"content": '{"ok":true}', "thinking": "private"}})

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    call = DeepSeekClient("http://localhost", "deepseek-r1:8b").structured_plan([], {"type": "object"})
    if reason == "length":
        with pytest.raises(OllamaError, match="reasoning limit"):
            asyncio.run(call)
    else:
        assert asyncio.run(call) == '{"ok":true}'
    assert captured[0]["options"]["num_predict"] == 4096
    assert captured[0]["think"] is True


def test_control_budget_is_separate(monkeypatch):
    captured = []

    async def post(self, url, **kwargs):
        captured.append(kwargs["json"])
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "done": True, "done_reason": "stop", "message": {"content": '{}'}})

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    client = DeepSeekClient("http://localhost", "deepseek-r1:8b")
    asyncio.run(client.control_plan([], {"type": "object"}))
    assert captured[0]["think"] is True
    assert captured[0]["options"]["num_predict"] == 4096
