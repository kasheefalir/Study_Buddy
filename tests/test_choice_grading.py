import asyncio
import json

import pytest

from app.agents.quiz import quiz_turn, answer_index, missed_review


class Explainer:
    async def structured_plan(self, messages, schema):
        assert schema["title"] == "ChoiceFeedback"
        data = json.loads(messages[-1]["content"])
        assert "correct_option" not in data
        assert data["correct_answer"] == {"letter": "D", "text": "Update specific fields"}
        # An unsolicited model verdict cannot override the code's decision.
        return json.dumps({"verdict": "incorrect" if data["result"] == "correct" else "correct",
                           "explanation": "UPDATE changes existing fields.",
                           "correction": "It does not insert or delete rows.", "example": "Change a student's email."})


def quiz():
    return {"version": 2, "active": True, "document_ids": [], "total": 1,
            "cursor": 0, "results": [], "phase": "question", "pending_question": "What does UPDATE do?",
            "expected_answer": "Update specific fields", "correct_index": 0,
            "options": ["Update data", "Delete rows", "Insert rows", "Update specific fields"],
            "sources": [], "focus": "SQL", "window_plan": [], "window_reviews": [], "turns": 0}


@pytest.mark.parametrize("answer,verdict", [("D", "Correct"), ("d", "Correct"), ("Option D", "Correct"),
                                         ("D)", "Correct"), ("Update specific fields", "Correct"), ("B", "Incorrect")])
def test_letter_text_and_legacy_key_mismatch(answer, verdict):
    text, state, _ = asyncio.run(quiz_turn(None, [], answer, quiz(), Explainer()))
    assert text.startswith(f"**{verdict}**")
    assert state["results"][0]["verdict"] == verdict.lower()
    assert state["results"][0]["correct_index"] == 3


def test_new_text_key_must_match_option():
    state = quiz()
    state["answer_key"] = "Invented option"
    with pytest.raises(ValueError, match="does not match"):
        answer_index(state)


def test_choice_feedback_that_asks_a_question_is_repaired():
    class RepairingExplainer:
        def __init__(self):
            self.calls = 0

        async def structured_plan(self, messages, schema):
            self.calls += 1
            assert schema["title"] == "ChoiceFeedback"
            explanation = "What should you try next?" if self.calls == 1 else "UPDATE changes existing fields in a table."
            return json.dumps({"explanation": explanation,
                               "correction": "It does not insert or delete rows.",
                               "example": "Change a student's email address."})

    text, _, _ = asyncio.run(quiz_turn(None, [], "B", quiz(), RepairingExplainer()))
    assert text.startswith("**Incorrect**")
    assert "What should you try next?" not in text


def test_missed_review_uses_saved_verdicts_not_model_interpretation():
    text, _ = missed_review({"results": [
        {"number": 1, "question": "Missed concept", "student_answer": "B", "verdict": "incorrect", "review": "Review it."},
        {"number": 2, "question": "Correct concept", "student_answer": "A", "verdict": "correct", "review": "Do not show this."},
    ]})
    assert "Missed concept" in text
    assert "Correct concept" not in text
