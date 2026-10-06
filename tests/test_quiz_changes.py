import asyncio
import json

from app.agents.chat_agent import ChatAgent
from app.agents.quiz import quiz_turn
from app.storage.conversation_store import ConversationStore


class Model:
    def __init__(self):
        self.stages = []
        self.action = "change"

    async def structured_plan(self, messages, schema):
        self.stages.append(schema["title"])
        if schema["title"] == "ResponseReview":
            return json.dumps({"action": "accept", "issues": [], "repair_request": ""})
        if schema["title"] == "QuizIntent":
            return json.dumps({"action": self.action, "format": "multiple_choice", "guidelines": "Use four options.", "acknowledgement": "Let's switch to multiple choice."})
        if schema["title"] == "ChoiceQuestion":
            return json.dumps({"summary": "Recall is sensitivity.", "question": "Which description defines recall?",
                "options": ["Actual positives found", "Predicted positives correct", "All predictions correct", "Actual negatives found"],
                "correct_answer": "Actual positives found", "expected_answer": "Recall is the proportion of actual positives identified."})
        if schema["title"] == "ChoiceQuality":
            return json.dumps({"valid": True, "stem_answered": True, "distractors_answer_stem": True, "issue": ""})
        if schema["title"] in {"Assessment", "ChoiceFeedback"}:
            return json.dumps({"verdict": "correct", "explanation": "You identified actual positives found.", "correction": "Recall measures sensitivity.", "example": "8 of 10 is 80%."})
        raise AssertionError("A format request must never be graded")

    async def chat(self, messages):
        return "Let's discuss how recall differs from precision."


class DistractingRouterModel(Model):
    """A router that would wrongly divert an answer into ordinary chat."""

    async def structured_plan(self, messages, schema):
        if schema["title"] == "IntentRoute":
            self.stages.append(schema["title"])
            return json.dumps({"route": "conversation", "reasoning": "wrong for this test",
                               "query": "", "pause_activity": True})
        if schema["title"] == "IntentDecision":
            self.stages.append(schema["title"])
            return json.dumps({"route": "conversation", "mode": "chat", "reasoning": "wrong for this test",
                               "query": "", "document_ids": [], "pause_activity": True})
        return await super().structured_plan(messages, schema)


def state():
    return {"version": 2, "active": True, "document_ids": [], "total": 10,
            "cursor": 0, "results": [], "phase": "question", "pending_question": "How is recall measured?",
            "expected_answer": "Actual positives identified", "sources": [], "focus": "Statistics",
            "window_plan": [], "window_reviews": [], "turns": 0}


def test_multiple_choice_request_regenerates_without_grading(tmp_path):
    store = ConversationStore(tmp_path)
    session = store.create_id()
    store.save(session, [], document_ids=[], quiz=state())
    model = Model()
    _, text = asyncio.run(ChatAgent(model, store).reply("make the questions multiple choice", session, document_ids=[]))
    updated = store.quiz(session)
    assert model.stages == ["QuizIntent", "ChoiceQuestion", "ChoiceQuality"]
    assert "Question 1 of 10" in text and "**A.**" in text and "**D.**" in text
    assert not updated["results"] and updated["cursor"] == 0
    assert updated["correct_index"] == 0 and updated["format"] == "multiple_choice"
    assert "Correct" not in text
    model.stages.clear()
    _, response = asyncio.run(ChatAgent(model, ConversationStore(tmp_path)).reply("A", session, document_ids=[]))
    assert response.startswith("**Correct**") and model.stages == ["ChoiceFeedback"]
    assert len(store.quiz(session)["results"]) == 1


def test_clicked_quiz_answer_is_marked_for_compact_transcript(tmp_path):
    store = ConversationStore(tmp_path)
    session = store.create_id()
    saved = state()
    saved["question_id"] = "question-1"
    store.save(session, [], document_ids=[], quiz=saved)

    asyncio.run(ChatAgent(Model(), store).reply("A", session, document_ids=[], quiz_question_id="question-1"))

    answer = store.load(session)[0]
    assert answer["content"] == "A"
    assert answer["quiz_selection_for"] == "question-1"


def test_clicked_answer_bypasses_router_and_updates_quiz_state(tmp_path):
    store = ConversationStore(tmp_path)
    session = store.create_id()
    saved = state()
    saved.update(question_id="question-1", options=["Actual positives found", "Predicted positives correct",
                                                      "All predictions correct", "Actual negatives found"],
                 answer_key="Actual positives found", correct_index=0)
    store.save(session, [], document_ids=[], quiz=saved)
    model = DistractingRouterModel()

    _, response = asyncio.run(ChatAgent(model, store).reply(
        "A", session, materials_root=tmp_path, document_ids=[], quiz_question_id="question-1"))

    updated = store.quiz(session)
    assert response.startswith("**Correct**")
    assert model.stages == ["ChoiceFeedback"]
    assert updated["phase"] == "review"
    assert updated["results"][0]["verdict"] == "correct"


def test_semantic_change_without_keyword_match():
    model = Model()
    text, updated, _ = asyncio.run(quiz_turn(None, [], "Could you give me four alternatives to pick from?", state(), model))
    assert "**D.**" in text and not updated["results"]


def test_discussion_is_not_graded(tmp_path):
    store = ConversationStore(tmp_path)
    session = store.create_id()
    store.save(session, [], document_ids=[], quiz=state())
    model = Model(); model.action = "discuss"
    _, text = asyncio.run(ChatAgent(model, store).reply("What does actual positive mean?", session, document_ids=[]))
    assert "Let's discuss" in text and not store.quiz(session)["results"]
    assert store.quiz(session)["pending_question"] == state()["pending_question"]


def test_old_format_request_score_is_repaired():
    old = state()
    old.update(phase="review", results=[{"student_answer": "make the questions multiple choice", "verdict": "correct"}])
    text, updated, _ = asyncio.run(quiz_turn(None, [], "make the questions multiple choice", old, Model()))
    assert "Question 1 of 10" in text and not updated["results"]
