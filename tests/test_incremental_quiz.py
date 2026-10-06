import asyncio
import json
from dataclasses import replace

import pytest

from app.agents import context_budget
from app.agents.chat_agent import ChatAgent
from app.agents.quiz import (choice_question_problem, coverage_windows, repeated_question_problem,
                             requested_count, quiz_turn, windows, select_windows)
from app.agents.tasks import task_for
from app.rag.library import write_json
from app.storage.conversation_store import ConversationStore


class Model:
    def __init__(self):
        self.calls = []
        self.verdict = "incorrect"
        self.question_count = 0

    async def structured_plan(self, messages, schema):
        self.calls.append(messages)
        payload = json.loads(messages[-1]["content"])
        if schema["title"] == "ChoiceQuality":
            return json.dumps({"valid": True, "stem_answered": True, "distractors_answer_stem": True, "issue": ""})
        if "message" in payload:
            return json.dumps({"action": "answer", "format": payload["format"], "guidelines": "", "acknowledgement": ""})
        if "request" in payload:
            return json.dumps({"count": 5, "focus": ""})
        if "student_answer" in payload or "result" in payload:
            return json.dumps({"verdict": self.verdict, "explanation": "Recall measures actual positives found.", "correction": "Precision instead concerns predicted positives.", "example": "Finding 8 of 10 actual positives means recall is 80%."})
        self.question_count += 1
        question = "How is recall measured?" if self.question_count == 1 else "What does precision measure?"
        expected = "The fraction of actual positives found." if self.question_count == 1 else "The fraction of predicted positives that are correct."
        return json.dumps({"summary": "Recall measures positives identified.", "question": question,
                           "options": ["Actual positives found", "All predicted positives", "True negatives", "All predictions"],
                           "correct_answer": "Actual positives found",
                           "expected_answer": expected,
                           "chunk_ids": [payload["sources"][0]["chunk_id"]] if payload["sources"] else []})


def book(root, count=830):
    identifier = "a" * 32
    write_json(root / (identifier + ".json"), {"id": identifier, "name": "Large book", "status": "Ready"})
    write_json(root / identifier / "chunks.json", [
        {"id": i, "text": "Recall measures actual positives found. " * 20,
         "location": f"Page {i + 1}", "page": i + 1, "chapter": f"Chapter {i // 40}"} for i in range(count)])
    return identifier


@pytest.mark.parametrize("message,count", [
    ("Quiz me one question at a time", None),
    ("Quiz me, one question at a time. 10 total questions", 10),
    ("Ask me seven questions", 7), ("Quiz me with 3 questions", 3),
    ("ten questions, one at a time", 10), ("questions: 12", 12),
    ("five total", 5), ("Quiz on chapter 10", None),
])
def test_count_phrasing(message, count):
    assert requested_count(message) == count


def test_invalid_counts():
    for text in ("0 questions", "51 questions"):
        with pytest.raises(ValueError):
            requested_count(text)


@pytest.mark.parametrize("message", ["Give me a ten-question quiz", "Ask me seven questions", "I want a quiz with 12 questions"])
def test_natural_quiz_requests(message):
    assert task_for(message, "auto", {}) == "quiz"


def test_large_book_first_question_is_two_bounded_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(context_budget, "settings", replace(context_budget.settings, context_window=4096, response_tokens=1200))
    identifier = book(tmp_path)
    model = Model()
    text, state, sources = asyncio.run(quiz_turn(tmp_path, [identifier], "Quiz me one question at a time", {}, model))
    assert "Question 1 of 5" in text
    assert len(model.calls) == 3
    assert len(state["window_reviews"]) == 1
    assert state["available_windows"] == 415
    assert len(state["window_plan"]) == 5
    assert sources[0]["page"] and sources[0]["document_id"] == identifier
    text, state, _ = asyncio.run(quiz_turn(tmp_path, [identifier], "All predicted positives", state, model))
    assert text.startswith("**Incorrect**") and len(state["results"]) == 1
    assert all(context_budget.estimate(call) <= context_budget.input_limit() for call in model.calls)
    assert "fraction" not in text


def test_duplicate_multiple_choice_options_are_repaired_before_display():
    class DuplicateChoiceModel(Model):
        def __init__(self):
            super().__init__()
            self.question_attempts = 0

        async def structured_plan(self, messages, schema):
            self.calls.append(messages)
            payload = json.loads(messages[-1]["content"])
            if schema["title"] == "ChoiceQuality":
                return json.dumps({"valid": True, "stem_answered": True, "distractors_answer_stem": True, "issue": ""})
            if "request" in payload:
                return json.dumps({"count": 5, "focus": ""})
            self.question_attempts += 1
            options = (["A reusable named block", "A reusable named block", "A table of values", "A chart"]
                       if self.question_attempts == 1 else
                       ["A reusable named block", "A table of values", "A chart", "A single stored value"])
            return json.dumps({"summary": "Functions package a reusable operation.",
                               "question": "What is a function in programming?", "options": options,
                               "correct_answer": "A reusable named block",
                               "expected_answer": "A function is a named reusable block of instructions."})

    model = DuplicateChoiceModel()
    text, state, _ = asyncio.run(quiz_turn(None, [], "Quiz me on programming", {}, model))
    assert "**Question 1 of 5**" in text
    assert state["options"] == ["A reusable named block", "A table of values", "A chart", "A single stored value"]
    assert state["correct_index"] == 0
    assert model.question_attempts == 2


def test_repeated_multiple_choice_question_is_regenerated():
    class RepeatingQuestionModel:
        def __init__(self):
            self.question_attempts = 0

        async def structured_plan(self, messages, schema):
            if schema["title"] == "ChoiceQuality":
                return json.dumps({"valid": True, "stem_answered": True, "distractors_answer_stem": True, "issue": ""})
            self.question_attempts += 1
            question = ("What is a function in programming?" if self.question_attempts == 1
                        else "Why might a program use a function more than once?")
            return json.dumps({"summary": "Functions package reusable behavior.", "question": question,
                               "options": ["To reuse a named operation", "To erase all variables", "To draw a chart", "To rename a file"],
                               "correct_answer": "To reuse a named operation",
                               "expected_answer": "Functions let a program reuse a named operation."})

    state = {"version": 2, "active": True, "document_ids": [], "total": 10, "cursor": 1,
             "results": [{"question": "What is a function in programming?"}], "phase": "question",
             "pending_question": "", "focus": "", "format": "multiple_choice", "guidelines": "",
             "window_plan": [], "window_reviews": [], "turns": 1}
    model = RepeatingQuestionModel()
    text, updated, _ = asyncio.run(quiz_turn(None, [], "Next question", state, model))
    assert "Why might a program use a function more than once?" in text
    assert updated["pending_question"] != state["results"][0]["question"]
    assert model.question_attempts == 2


def test_semantically_misaligned_choices_are_regenerated():
    class QualityCheckingModel:
        def __init__(self):
            self.drafts = 0

        async def structured_plan(self, messages, schema):
            if schema["title"] == "QuizRequest":
                return json.dumps({"count": 1, "focus": "", "format": "multiple_choice", "guidelines": ""})
            if schema["title"] == "ChoiceQuality":
                return json.dumps({"valid": self.drafts > 1, "stem_answered": self.drafts > 1,
                                   "distractors_answer_stem": self.drafts > 1,
                                   "issue": "The choices restate the premise instead of answering why it matters."})
            self.drafts += 1
            if self.drafts == 1:
                return json.dumps({"summary": "Assignment stores a value.",
                                   "question": "Why does R conventionally use <- for assignment?",
                                   "options": ["<- assigns values", "= assigns values", "<- is another symbol", "<- opens help"],
                                   "correct_answer": "<- assigns values",
                                   "expected_answer": "The left arrow is R's conventional assignment operator."})
            return json.dumps({"summary": "Assignment stores a value.",
                               "question": "Which operator conventionally assigns a value to a name in R?",
                               "options": ["<-", "#", "$", "[ ]"], "correct_answer": "<-",
                               "expected_answer": "The left arrow assigns a value to a name in R."})

    text, state, _ = asyncio.run(quiz_turn(None, [], "Quiz me on R", {}, QualityCheckingModel()))
    assert "Which operator conventionally assigns" in text
    assert state["options"] == ["<-", "#", "$", "[ ]"]


def test_correct_option_must_add_an_answer_beyond_the_stem():
    assert choice_question_problem({
        "question": "What is the purpose of using the left-arrow symbol for variable assignment in R?",
        "options": ["The left-arrow symbol is used for variable assignment in R.", "It opens help.", "It prints a plot.", "It adds a package."],
        "correct_answer": "The left-arrow symbol is used for variable assignment in R.",
    })


def test_count_override_persistence_feedback_review_and_completion(tmp_path):
    identifier = book(tmp_path / "documents", 6)
    store = ConversationStore(tmp_path / "conversations")
    model = Model()
    agent = ChatAgent(model, store)
    session, text = asyncio.run(agent.reply("Quiz me with two questions", document_ids=[identifier], materials_root=tmp_path / "documents"))
    assert "1 of 2" in text
    agent = ChatAgent(model, ConversationStore(tmp_path / "conversations"))
    _, text = asyncio.run(agent.reply("A hint please", session, document_ids=[identifier], materials_root=tmp_path / "documents"))
    assert text.startswith("**Hint**") and not store.quiz(session)["results"]
    _, text = asyncio.run(agent.reply("All predicted positives", session, document_ids=[identifier], materials_root=tmp_path / "documents"))
    assert text.startswith("**Incorrect**")
    saved = store.quiz(session)
    assert saved["results"][0]["student_answer"] == "All predicted positives"
    calls = len(model.calls)
    _, text = asyncio.run(agent.reply("Review my missed answers", session, document_ids=[identifier], materials_root=tmp_path / "documents"))
    assert "All predicted positives" in text and len(model.calls) == calls
    _, text = asyncio.run(agent.reply("Stop the quiz and review what I got wrong", session,
                                      document_ids=[identifier], materials_root=tmp_path / "documents"))
    assert "All predicted positives" in text
    assert store.quiz(session)["results"][0]["verdict"] == "incorrect"
    _, text = asyncio.run(agent.reply("Next question", session, document_ids=[identifier], materials_root=tmp_path / "documents"))
    assert "2 of 2" in text and len(model.calls) == calls + 2
    model.verdict = "correct"
    _, text = asyncio.run(agent.reply("Actual positives found", session, document_ids=[identifier], materials_root=tmp_path / "documents"))
    assert text.startswith("**Correct**") and "1 of 2 correct" in text
    calls = len(model.calls)
    _, text = asyncio.run(agent.reply("Next question", session, document_ids=[identifier], materials_root=tmp_path / "documents"))
    assert "Quiz complete" in text and len(model.calls) == calls
    assert len(store.quiz(session)["window_reviews"]) == 2
    assert task_for("Review missed answers", "auto", store.quiz(session)) == "quiz"


def test_failed_next_question_does_not_mutate_progress(tmp_path):
    identifier = book(tmp_path, 6)
    model = Model()
    _, state, _ = asyncio.run(quiz_turn(tmp_path, [identifier], "Quiz me", {}, model))
    _, state, _ = asyncio.run(quiz_turn(tmp_path, [identifier], "Wrong", state, model))
    original = json.dumps(state)

    class Failure(Model):
        async def structured_plan(self, messages, schema):
            raise RuntimeError("timeout")

    with pytest.raises(RuntimeError):
        asyncio.run(quiz_turn(tmp_path, [identifier], "next", state, Failure()))
    assert json.dumps(state) == original


def test_general_quiz_is_counted_and_reviewable(tmp_path):
    model = Model()
    store = ConversationStore(tmp_path)
    agent = ChatAgent(model, store)
    session, text = asyncio.run(agent.reply("Quiz me on statistics with one question", document_ids=[]))
    assert "1 of 1" in text
    _, text = asyncio.run(agent.reply("Wrong answer", session, document_ids=[]))
    assert "Incorrect" in text and "Quiz complete" in text
    _, text = asyncio.run(agent.reply("Review my missed answers", session, document_ids=[]))
    assert "Wrong answer" in text


def test_windows_overlap_and_sample_documents():
    chunks = [{"id": i, "text": "Learning topic", "chapter": "Chapter"} for i in range(10)]
    available = windows([({"id": "a"}, chunks), ({"id": "b"}, chunks)])
    assert set(available[0]["chunk_ids"]) & set(available[1]["chunk_ids"]) == {2}
    assert {w["document_id"] for w in select_windows(available, 5)} == {"a", "b"}


def test_quiz_coverage_uses_distinct_bounded_windows(tmp_path):
    identifier = book(tmp_path, 30)
    from app.agents.study_tools import library
    available = coverage_windows(tmp_path, library(tmp_path, [identifier]))
    plan = select_windows(available, 10)
    signatures = {(window["document_id"], tuple(window["chunk_ids"])) for window in plan}
    assert len(plan) == 10
    assert len(signatures) == 10
    assert all(len(window["chunk_ids"]) <= 3 for window in plan)


def test_similar_question_stems_do_not_hide_a_new_concept():
    assert not repeated_question_problem(
        "What is the primary purpose of comments in R?",
        ["What is the primary purpose of a script in R?"])
    assert repeated_question_problem(
        "What is the purpose of comments in R code?",
        ["What purpose do comments serve in R code?"])
