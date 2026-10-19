import json

import pytest

from app.agents.local_study.bounded_tutor import TutoringAnswer, attach_references, messages


SOURCE = {"document_id": "private-id", "chunk_id": 2, "location": "Page 3", "text": "The median is the middle value."}


def answer(**changes):
    return TutoringAnswer(**{**dict(status="answered", material_answer="The median is the middle value.",
        anchor_quote=SOURCE["text"], additional_explanation="For example, the median of 1, 2, 9 is 2.", limitation=""), **changes})


def test_code_owns_references_and_labels_explanation():
    result = attach_references(answer(), [SOURCE])
    assert result["sections"][0]["references"][0]["chunk_id"] == 2
    assert result["sections"][1]["label"].startswith("Additional explanation")
    assert "Concept anchor only" in result["sections"][1]["reference_role"]
    assert "private-id" not in str(messages("Explain median", [SOURCE]))


def test_fabricated_anchor_and_missing_partial_boundary_rejected():
    with pytest.raises(ValueError, match="exact excerpt"):
        attach_references(answer(anchor_quote="The median is always best."), [SOURCE])
    with pytest.raises(ValueError, match="missing part"):
        attach_references(answer(status="partial"), [SOURCE])


def test_absence_requires_complete_material_not_just_retrieval():
    assert "retrieved_excerpts" in messages("Explain", [SOURCE])[1]["content"]
    assert "complete_material" in messages("Explain", [SOURCE], True)[1]["content"]
    with pytest.raises(ValueError, match="substantive"):
        attach_references(answer(status="outside_material"), [SOURCE])


def test_schema_is_in_prompt_for_all_providers():
    prompt = messages("Explain", [SOURCE])[0]["content"]
    assert '"required"' in prompt and '"additional_explanation"' in prompt
    assert "No Markdown fences" in prompt


def test_matching_quote_is_not_claim_verification():
    result = attach_references(answer(material_answer="The median is always best."), [SOURCE])
    assert "not verified" in result["validation"]


def test_followup_preserves_original_question_and_separates_resolution():
    request = messages("Explain that more simply.", [SOURCE], resolved_question="Explain median simply.")
    payload = json.loads(request[1]["content"])
    assert payload["question"] == "Explain that more simply."
    assert payload["resolved_question"] == "Explain median simply."
    assert payload["passages"] == [SOURCE["text"]]
    assert "resolved_question" not in json.loads(messages("Explain", [SOURCE])[1]["content"])
