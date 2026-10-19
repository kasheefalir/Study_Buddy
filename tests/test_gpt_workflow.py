import asyncio

import pytest
import httpx

from app import main
from app.agents.gpt.agent import GPTAgent
from app.agents.gpt.client import GPTClient
from app.agents import quiz as quiz_module
from app.llm.ollama_client import OllamaClient, OllamaError
from app.storage.conversation_store import ConversationStore


def test_gpt_dispatch_and_prompt_isolation(tmp_path):
    store = ConversationStore(tmp_path)
    agent = main.selected_agent(OllamaClient("http://localhost", "gpt-oss:20b"), store)
    assert type(agent) is GPTAgent
    for model in ("llama3.2:3b", "phi4-mini:latest"):
        legacy = main.selected_agent(OllamaClient("http://localhost", model), store)
        assert type(legacy) is main.ChatAgent
        assert legacy.router_prompt != agent.router_prompt


def test_gpt_generates_only_current_question(tmp_path, monkeypatch):
    calls = []

    async def step(*args):
        calls.append(args)
        return "question", {"phase": "question", "pending_question": "Q1", "question_id": "one",
                            "cursor": 0, "total": 5}, []

    monkeypatch.setattr(quiz_module, "_quiz_turn", step)
    agent = GPTAgent(object(), ConversationStore(tmp_path))
    _, state, _ = asyncio.run(agent.quiz_step(tmp_path, [], "quiz", {}, agent.llm))
    assert len(calls) == 1
    assert "prepared_questions" not in state


def test_gpt_failed_next_keeps_saved_state(tmp_path, monkeypatch):
    store = ConversationStore(tmp_path)
    cid = store.create_id()
    state = {"version": 2, "active": True, "phase": "review", "question_id": "one",
             "cursor": 0, "total": 2, "pending_question": "Q1", "results": []}
    store.save(cid, [], quiz=state)

    async def failed(*args, **kwargs):
        raise ValueError("Invalid new question")

    monkeypatch.setattr(quiz_module, "_quiz_turn", failed)
    agent = GPTAgent(object(), store)
    with pytest.raises(ValueError, match="Invalid new question"):
        asyncio.run(agent.reply("Next question", cid, materials_root=tmp_path, document_ids=[], next_question_id="one"))
    assert store.quiz(cid) == state


def test_end_clarify_resume_preserves_structured_question(tmp_path, monkeypatch):
    from app.agents import chat_agent
    from app.agents.quiz import public_question

    store = ConversationStore(tmp_path)
    cid = store.create_id()
    state = {"version": 2, "active": True, "phase": "question", "question_id": "one",
             "cursor": 2, "total": 10, "pending_question": "Saved question?", "results": [],
             "options": ["Alpha", "Beta", "Gamma", "Delta"], "correct_answer": "Beta",
             "document_ids": [], "sources": []}
    store.save(cid, [], quiz=state)
    routes = iter([("quiz", "end"), ("clarify", "keep"), ("quiz", "resume")])

    async def structured(*args):
        route, action = next(routes)
        return {"route": route, "activity_action": action, "pause_activity": False,
                "mode": "quiz" if route == "quiz" else "chat", "query": ""}

    monkeypatch.setattr(chat_agent, "structured", structured)
    # No answer writer exists: these turns must be handled by code.
    agent = GPTAgent(object(), store)
    asyncio.run(agent.reply("end the quiz here", cid, materials_root=tmp_path, document_ids=[]))
    ended = store.quiz(cid)
    assert ended["ended"] and not ended["active"]
    assert public_question(ended) == {}
    with pytest.raises(ValueError, match="progress has changed"):
        asyncio.run(agent.reply("Next question", cid, materials_root=tmp_path,
                                document_ids=[], next_question_id="one"))
    _, response = asyncio.run(agent.reply("next queestion", cid, materials_root=tmp_path, document_ids=[]))
    assert "resume" in response and "Question 3" not in response
    assert store.quiz(cid) == ended
    _, response = asyncio.run(agent.reply("resume it", cid, materials_root=tmp_path, document_ids=[]))
    assert "Question 3 of 10" in response and "**B.** Beta" in response
    question = store.load(cid)[-1]["quiz_question"]
    assert question["id"] == "one" and question["options"] == state["options"]
    assert "correct_answer" not in question
    assert store.quiz(cid)["cursor"] == 2


@pytest.mark.parametrize("reason", ["stop", "length"])
def test_gpt_completion_budget_and_truncation(monkeypatch, reason):
    payloads = []

    async def post(self, url, **kwargs):
        payloads.append(kwargs["json"])
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "done": True, "done_reason": reason, "message": {"content": '{"ok":true}'}})

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    call = GPTClient("http://localhost", "gpt-oss:20b").structured_plan([], {"type": "object"})
    if reason == "length":
        with pytest.raises(OllamaError, match="output limit"):
            asyncio.run(call)
    else:
        assert asyncio.run(call) == '{"ok":true}'
    assert payloads[0]["think"] == "low"
    assert payloads[0]["options"]["num_predict"] == 4096
