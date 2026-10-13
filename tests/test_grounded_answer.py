import asyncio
import json

import pytest

from app.agents.grounded_answer import answer_from_sources, render_answer, parse_checks, check_schema_for

SOURCES = [{"label": "S1", "text": "The nearest points are not much closer than average."}]


def response(label="S1"):
    return json.dumps({"points": [{"evidence": [{"label": label}],
                                  "explanation": "The nearest points offer little distance advantage."}]})


def test_verified_citations_are_rendered():
    assert render_answer(response(), SOURCES).endswith("[S1]")


@pytest.mark.parametrize("raw", [response(label="S99"), response(label="Invented source")])
def test_fabricated_evidence_is_rejected(raw):
    with pytest.raises(ValueError, match="does not match"):
        render_answer(raw, SOURCES)


def test_invalid_source_reference_can_be_repaired_once():
    class Model:
        calls = 0
        async def structured_plan(self, messages, schema):
            self.calls += 1
            if schema["title"] == "GroundingCheck":
                return json.dumps({"checks": {"0": {"supported": True}}})
            return response(label="S99") if self.calls == 1 else response()
    model = Model()
    result = asyncio.run(answer_from_sources(model, [{"role": "system", "content": "Explain evidence."}], SOURCES))
    assert result.endswith("[S1]") and model.calls == 3


def test_invalid_evidence_never_becomes_visible_answer():
    class Model:
        async def structured_plan(self, messages, schema):
            return response(label="Invented source")
    result = asyncio.run(answer_from_sources(Model(), [{"role": "system", "content": "Explain evidence."}], SOURCES))
    assert "couldn't support an explanation" in result
    assert "distance advantage" not in result


def test_valid_source_reference_does_not_excuse_unsupported_explanation():
    class Model:
        async def structured_plan(self, messages, schema):
            if schema["title"] == "GroundingCheck":
                payload = json.loads(messages[-1]["content"])
                assert payload["passage"]["S1"] == SOURCES[0]["text"]
                assert list(payload["passage"]) == ["S1"]
                assert payload["citations"]["0"] == ["S1"]
                assert list(payload["claims"]) == ["0"]
                return json.dumps({"checks": {"0": {
                    "supported": "Regularization" not in payload["claims"]["0"]}}})
            answer = json.loads(response())
            answer["points"].append({"evidence": [{"label": "S1"}],
                                     "explanation": "Regularization will fix this."})
            return json.dumps(answer)
    result = asyncio.run(answer_from_sources(Model(), [{"role": "system", "content": "Explain evidence."}], SOURCES))
    assert "Regularization" not in result
    assert result.endswith("[S1]")


def test_rejected_explanations_acknowledge_evidence_gap():
    class Model:
        async def structured_plan(self, messages, schema):
            if schema["title"] == "GroundingCheck":
                return json.dumps({"checks": {"0": {"supported": False}}})
            return response()
    result = asyncio.run(answer_from_sources(Model(), [{"role": "system", "content": "Explain evidence."}], SOURCES))
    assert "couldn't support an explanation" in result
    assert "little distance advantage" not in result
    assert "[S1]" not in result


def test_targeted_repair_receives_feedback_and_keeps_supported_point():
    class Model:
        calls = 0
        async def structured_plan(self, messages, schema):
            self.calls += 1
            if self.calls == 1:
                payload = json.loads(messages[-1]["content"])
                assert "irrelevant history" not in str(payload)
                return json.dumps({"points": [json.loads(response())["points"][0],
                    {"evidence": [{"label": "S1"}], "explanation": "Regularization fixes this."}]})
            if self.calls == 2:
                return json.dumps({"checks": {"0": {"supported": True}}})
            if self.calls == 3:
                return json.dumps({"checks": {"0": {
                    "supported": False, "reason": "Regularization is not mentioned."}}})
            if self.calls == 4:
                payload = json.loads(messages[-1]["content"])
                assert payload["repair_only"][0]["problem"] == "Regularization is not mentioned."
                assert len(payload["already_supported"]) == 1
                return response()
            return json.dumps({"checks": {"0": {"supported": True}}})
    model = Model()
    result = asyncio.run(answer_from_sources(model, [
        {"role": "system", "content": "Explain evidence."},
        {"role": "assistant", "content": "irrelevant history"},
        {"role": "user", "content": "Explain simply"}], SOURCES, "Explain nearest point distances"))
    assert model.calls == 5
    assert result.count("distance advantage") == 1
    assert "Regularization" not in result


@pytest.mark.parametrize("raw", [
    '{"checks":{"0":{"supported":true},"0":{"supported":false}}}',
    '{"checks":{}}',
    '{"checks":{"1":{"supported":true}}}',
    '{"checks":[{"index":0,"supported":true}]}',
    '[]',
])
def test_ambiguous_or_missing_checks_fail_closed(raw):
    with pytest.raises(ValueError):
        parse_checks(raw, 1)


def test_checker_has_one_required_slot_per_point():
    schema = check_schema_for(2)["properties"]["checks"]
    assert schema["required"] == ["0", "1"]
    assert not schema["additionalProperties"]
    checks = parse_checks('{"checks":{"1":{"supported":false},"0":{"supported":true}}}', 2)
    assert [(c.index, c.supported) for c in checks] == [(0, True), (1, False)]
