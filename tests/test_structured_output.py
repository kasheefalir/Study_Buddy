import json

import pytest

from app.agents.quiz import ChoiceQuality
from app.llm.structured_output import validated_output
import asyncio
from app.agents.study_tools import structured


REJECTED = {"valid": False, "stem_answered": True, "distractors_answer_stem": False, "issue": "Wrong distractors"}


@pytest.mark.parametrize("fenced", [False, True])
@pytest.mark.parametrize("wrapped", [False, True])
def test_envelope_cleanup_preserves_negative_verdict(fenced, wrapped):
    value = REJECTED
    if wrapped:
        schema = ChoiceQuality.model_json_schema()
        value = {"properties": value, "required": schema["required"], "title": schema["title"]}
    raw = json.dumps(value)
    if fenced:
        raw = "```json\n" + raw + "\n```"
    assert validated_output(raw, ChoiceQuality).model_dump() == REJECTED


@pytest.mark.parametrize("raw", [
    'Here is your answer: {"valid": true}',
    '```json\n{"valid": true}\n```',
    json.dumps({"properties": REJECTED, "unexpected_answer": "discard me"}),
    json.dumps({"properties": REJECTED, "title": "Wrong schema"}),
    json.dumps({"properties": REJECTED, "required": []}),
    '```json\n{}\n```\nAdditional prose',
])
def test_cleanup_does_not_fill_fields_or_discard_extra_content(raw):
    with pytest.raises(ValueError):
        validated_output(raw, ChoiceQuality)


def test_fenced_intent_preserves_model_retrieval_decision():
    class Model:
        async def structured_plan(self, messages, schema):
            return '```json\n{"route":"retrieve","reasoning":"Read the book","query":"logistic regression"}\n```'
    result = asyncio.run(structured(Model(), "intent route", "Route", {}))
    assert result["route"] == "retrieve"
    assert result["query"] == "logistic regression"


def test_fenced_invalid_intent_is_still_rejected():
    class Model:
        async def structured_plan(self, messages, schema):
            return '```json\n{"route":"invented","reasoning":"Read","query":"trees"}\n```'
    with pytest.raises(ValueError):
        asyncio.run(structured(Model(), "intent route", "Route", {}))
