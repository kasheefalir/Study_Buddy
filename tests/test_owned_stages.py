import asyncio
import json

import pytest

from app.agents.chat_agent import ChatAgent
from app.agents.study_tools import RetrievalPlan
from app.agents.quiz import quiz_turn
from app.storage.conversation_store import ConversationStore
from scripts.evaluate_owned_attribution import render_bound, FALLBACK
from tests.test_intent_router import RouterModel, source


def test_planner_cannot_return_intent_or_activity():
    for field, value in [("route", "quiz"), ("mode", "quiz"), ("pause_activity", True)]:
        with pytest.raises(ValueError):
            RetrievalPlan.model_validate({"query": "R", "reasoning": "source", "document_ids": [], field: value})


def test_code_attaches_assigned_source_and_preserves_abstention():
    assert render_bound('{"status":"answered","points":["A supported fact."]}', {"label": "S7"}) == "A supported fact. [S7]"
    assert render_bound('{"status":"insufficient_evidence","points":[]}', {"label": "S7"}) == FALLBACK
    with pytest.raises(ValueError):
        render_bound('{"status":"answered","points":["A fact [S2]"]}', {"label": "S7"})


def test_pause_greeting_resume_preserves_question_and_results(tmp_path):
    class Model:
        def __init__(self):
            self.actions = iter([("conversation", "pause"), ("conversation", "keep"), ("quiz", "resume")])
            self.stages = []

        async def structured_plan(self, messages, schema):
            self.stages.append(schema["title"])
            assert schema["title"] == "IntentRoute", "No planner or grading on these turns"
            route, action = next(self.actions)
            return json.dumps({"route": route, "mode": "quiz" if route == "quiz" else "chat",
                               "activity_action": action, "reasoning": "Student intent", "query": ""})

        async def chat(self, messages):
            return "Hello!"

    store = ConversationStore(tmp_path / "conversations")
    cid = store.create_id()
    quiz = {"active": True, "version": 2, "phase": "question", "pending_question": "What is R?",
            "results": [{"verdict": "correct", "number": 1}], "cursor": 1, "total": 10}
    store.save(cid, [], document_ids=[], quiz=quiz)
    agent = ChatAgent(Model(), store)
    for message in ["Let's take a break", "Hey again"]:
        asyncio.run(agent.reply(message, cid, materials_root=tmp_path, document_ids=[]))
        assert store.quiz(cid)["paused"] and not store.quiz(cid)["active"]
        assert store.quiz(cid)["results"] == quiz["results"]
    _, reply = asyncio.run(agent.reply("Back to where we left off", cid, materials_root=tmp_path, document_ids=[]))
    assert reply == "What is R?"
    assert store.quiz(cid)["active"] and not store.quiz(cid)["paused"]
    assert store.quiz(cid)["cursor"] == 1
    assert store.quiz(cid)["results"] == quiz["results"]


def test_natural_language_owner_overrides_legacy_quiz_keywords(tmp_path):
    identifier = source(tmp_path / "documents")
    store = ConversationStore(tmp_path / "conversations")
    model = RouterModel("conversation")
    cid, _ = asyncio.run(ChatAgent(model, store).reply("Don't quiz me; I just want to talk.",
        materials_root=tmp_path / "documents", document_ids=[identifier]))
    assert not store.quiz(cid).get("active")
    assert len(model.calls) == 2  # One intent decision and the conversational writer.
    assert store.load(cid)[-1]["sources"] == []


def test_invalid_planner_cannot_override_source_route(tmp_path):
    class Model(RouterModel):
        async def structured_plan(self, messages, schema):
            if schema["title"] == "RetrievalPlan":
                return json.dumps({"route": "conversation", "query": "R", "reasoning": "override", "document_ids": []})
            return await super().structured_plan(messages, schema)

    identifier = source(tmp_path / "documents")
    store = ConversationStore(tmp_path / "conversations")
    cid, text = asyncio.run(ChatAgent(Model("retrieve"), store).reply("What does the book say about R?",
        materials_root=tmp_path / "documents", document_ids=[identifier]))
    assert text == "R is used for statistics. [S1]"
    assert store.load(cid)[-1]["sources"]


def test_resume_completed_quiz_does_not_reopen_last_question():
    state = {"phase": "complete", "active": False, "total": 1, "pending_question": "Old question?",
             "results": [{"verdict": "correct"}]}
    text, saved, _ = asyncio.run(quiz_turn(None, [], "Return to the quiz", state, None, activity_action="resume"))
    assert "Quiz complete" in text and not saved["active"]


def test_resume_answered_question_does_not_repeat_stem():
    state = {"phase": "review", "pending_question": "Old question?", "cursor": 0,
             "results": [{"verdict": "correct"}]}
    text, saved, _ = asyncio.run(quiz_turn(None, [], "Resume", state, None, activity_action="resume"))
    assert "Old question?" not in text
    assert "already answered" in text
    assert saved == state


def test_next_button_bypasses_intent_and_keeps_results(tmp_path, monkeypatch):
    from app.agents import chat_agent
    store = ConversationStore(tmp_path / "conversations")
    cid = store.create_id()
    state = {"version": 2, "phase": "review", "question_id": "q1", "cursor": 0,
             "pending_question": "Old question?", "results": [{"verdict": "correct"}]}
    store.save(cid, [], document_ids=[], quiz=state)

    async def advance(root, ids, message, quiz, llm, history, **kwargs):
        assert kwargs["activity_action"] == "next"
        assert quiz["results"] == state["results"]
        quiz.update(cursor=1, phase="question", question_id="q2", pending_question="New question?",
                    options=["One", "Two", "Three", "Four"], total=5)
        return "Question 2 of 5", quiz, []

    monkeypatch.setattr(chat_agent, "quiz_turn", advance)
    asyncio.run(ChatAgent(object(), store).reply("Next question", cid, materials_root=tmp_path,
                                                document_ids=[], next_question_id="q1"))
    assert store.quiz(cid)["cursor"] == 1
    assert len(store.load(cid)[-1]["quiz_question"]["options"]) == 4
    with pytest.raises(ValueError, match="progress has changed"):
        asyncio.run(ChatAgent(object(), store).reply("Next question", cid, materials_root=tmp_path,
                                                    document_ids=[], next_question_id="q1"))


def test_typed_letter_during_pause_does_not_bypass_intent(tmp_path):
    store = ConversationStore(tmp_path / "conversations")
    cid = store.create_id()
    quiz = {"version": 2, "active": False, "paused": True, "phase": "question",
            "pending_question": "What is R?", "options": ["A language", "A book", "A page", "A number"],
            "results": []}
    store.save(cid, [], document_ids=[], quiz=quiz)
    model = RouterModel("conversation")
    asyncio.run(ChatAgent(model, store).reply("A", cid, materials_root=tmp_path, document_ids=[]))
    assert store.quiz(cid)["paused"] and not store.quiz(cid)["results"]
    assert len(model.calls) == 2
