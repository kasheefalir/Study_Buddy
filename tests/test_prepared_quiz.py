import asyncio
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app import main
from app.agents.chat_agent import ChatAgent
from app.agents.quiz import quiz_turn, public_question, missed_review
from app.agents import activity
from app.storage.conversation_store import ConversationStore
from tests.test_incremental_quiz import Model, book


def test_prepares_every_question_and_plays_back_after_reload(tmp_path, monkeypatch):
    identifier = book(tmp_path / "documents", count=8)
    model = Model()
    text, state, _ = asyncio.run(quiz_turn(tmp_path / "documents", [identifier], "Quiz me with two questions", {}, model))
    assert "Question 1 of 2" in text
    bank = deepcopy(state["prepared_questions"])
    assert len(bank) == 2 and all(len(q["options"]) == 4 for q in bank)
    assert bank[0]["question_id"] != bank[1]["question_id"]
    assert state["cursor"] == 0 and state["results"] == []
    assert model.question_count == 2
    # Deliberately miss the first question, then load a fresh store instance.
    _, state, _ = asyncio.run(quiz_turn(tmp_path / "documents", [identifier], "B", state, model))
    store = ConversationStore(tmp_path / "conversations")
    cid = store.create_id()
    store.save(cid, [], document_ids=[identifier], quiz=state)
    store = ConversationStore(tmp_path / "conversations")
    agent = ChatAgent(object(), store)  # Any model call during Next would fail.
    _, text = asyncio.run(agent.reply("Next question", cid, materials_root=tmp_path / "documents",
                                     document_ids=[identifier], next_question_id=state["question_id"]))
    state = store.quiz(cid)
    assert "Question 2 of 2" in text and state["question_id"] == bank[1]["question_id"]
    assert state["prepared_questions"] == bank
    assert public_question(state)["options"] == bank[1]["options"]
    _, completed, _ = asyncio.run(quiz_turn(tmp_path / "documents", [identifier], "A", state, model))
    assert completed["phase"] == "complete"
    assert completed["pending_question"] == bank[1]["pending_question"]
    assert completed["sources"] == bank[1]["sources"]
    review, _ = missed_review(completed)
    assert bank[0]["pending_question"] in review
    assert bank[1]["pending_question"] not in review
    store.save(cid, store.load(cid), document_ids=[identifier], quiz=completed)
    monkeypatch.setattr(main, "store", store)
    response = TestClient(main.app).get(f"/api/conversations/{cid}").json()
    assert "prepared_questions" not in response["quiz"]
    assert "answer_key" not in response["quiz"]["current_question"]


def test_preparation_failure_does_not_change_supplied_state():
    class Failing(Model):
        async def structured_plan(self, messages, schema):
            if self.question_count == 1 and schema["title"] == "ChoiceQuestion":
                raise RuntimeError("Second question failed")
            return await super().structured_plan(messages, schema)

    original = {}
    with pytest.raises(RuntimeError, match="Second question"):
        asyncio.run(quiz_turn(None, [], "Quiz me with two questions", original, Failing()))
    assert original == {}


def test_resume_does_not_rebuild_or_advance_prepared_quiz():
    model = Model()
    _, state, _ = asyncio.run(quiz_turn(None, [], "Quiz me with two questions", {}, model))
    before = deepcopy(state)
    _, state, _ = asyncio.run(quiz_turn(None, [], "Return to the quiz", state, object(), activity_action="resume"))
    assert state == before


def test_completed_quiz_remains_followup_context_without_full_bank(tmp_path):
    class ConversationModel:
        async def structured_plan(self, messages, schema):
            return json.dumps({"route": "conversation", "mode": "chat", "activity_action": "keep",
                               "reasoning": "Recall the last quiz question", "query": ""})

        async def chat(self, messages):
            prompt = json.dumps(messages)
            assert "What does entropy measure?" in prompt
            assert "private_future_marker" not in prompt
            return "The last question asked what entropy measures."

    store = ConversationStore(tmp_path / "conversations")
    cid = store.create_id()
    state = {"version": 2, "active": False, "phase": "complete", "cursor": 1, "total": 2,
             "pending_question": "What does entropy measure?", "results": [],
             "prepared_questions": [{"private_future_marker": True}]}
    store.save(cid, [], document_ids=[], quiz=state)
    asyncio.run(ChatAgent(ConversationModel(), store).reply("What was the last quiz question?", cid,
                                                         materials_root=tmp_path, document_ids=[]))
    assert store.quiz(cid) == state


def test_preparation_progress_is_request_local():
    with activity.track("quiz-preparation-test"):
        with activity.preparing_question(3, 5):
            activity.report("quiz choices")
            assert activity.active["quiz-preparation-test"] == "Preparing quiz question 3 of 5"
        activity.report("choice feedback")
        assert activity.active["quiz-preparation-test"] == "Explaining your answer"
    assert "quiz-preparation-test" not in activity.active
