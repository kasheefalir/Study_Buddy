import asyncio
import json

import pytest

from app.agents.grounded_answer import answer_from_sources, render_answer, parse_checks, check_schema_for

SOURCES = [{"label": "S1", "text": "The nearest points are not much closer than average."}]


def response(label="S1"):
    return json.dumps({"points": [{"evidence": [{"label": label}],
                                  "explanation": "The nearest points offer little distance advantage."}]})


def test_writer_and_repair_keep_evidence_status_and_metadata():
    status = {"omitted_for_budget": 2, "preparing_overviews": [{"status": "preparing"}]}
    sources = [{**SOURCES[0], "variant": "generated_summary", "location": "Generated overview: Chapter 1"}]

    class Model:
        drafts = 0

        async def structured_plan(self, messages, schema):
            if schema["title"] == "GroundingCheck":
                return json.dumps({"checks": {"0": {"supported": False}}})
            self.drafts += 1
            payload = json.loads(messages[-1]["content"])
            assert payload["evidence_status"] == status
            assert payload["evidence"][0]["variant"] == "generated_summary"
            assert payload["evidence"][0]["location"] == sources[0]["location"]
            return response()

    model = Model()
    asyncio.run(answer_from_sources(model, [{"role": "system", "content": "Explain evidence."},
        {"role": "user", "content": "Summarize"}], sources, evidence_status=status))
    assert model.drafts == 2


def test_verified_citations_are_rendered():
    assert render_answer(response(), SOURCES).endswith("[S1]")


def test_fenced_writer_and_checker_keep_validation():
    assert render_answer("```json\n" + response() + "\n```", SOURCES).endswith("[S1]")
    assert not parse_checks('```json\n{"checks":{"0":{"supported":false}}}\n```', 1)[0].supported
    with pytest.raises(ValueError):
        parse_checks('```json\n{"checks":{"0":{"supported":true},"0":{"supported":false}}}\n```', 1)


def test_string_citation_ids_are_lossless_but_unknown_ids_still_fail():
    data = json.loads(response())
    data["points"][0]["evidence"] = ["S1"]
    assert render_answer(json.dumps(data), SOURCES) == render_answer(response(), SOURCES)
    data["points"][0]["evidence"] = ["S99"]
    with pytest.raises(ValueError, match="source label"):
        render_answer(json.dumps(data), SOURCES)


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


def test_verbose_check_reason_preserves_verdict():
    import json
    from app.agents.grounded_answer import parse_checks
    for supported in (True, False):
        result = parse_checks(json.dumps({"checks": {"0": {
            "supported": supported, "reason": "evidence " * 100}}}), 1)
        assert result[0].supported is supported
        assert len(result[0].reason) == 300


@pytest.mark.parametrize("model_name", ["gpt-oss:20b", "gemma4:31b-cloud"])
def test_checker_schema_prompt_is_model_scoped(model_name):
    from app.agents.grounded_answer import GroundedAnswer, verify_points

    class Model:
        model = model_name

        async def structured_plan(self, messages, schema):
            assert "JSON schema:" not in messages[0]["content"]
            assert schema == check_schema_for(1)
            return '{"checks":{"0":{"supported":true,"reason":"Same meaning"}}}'

    checks = asyncio.run(verify_points(Model(), GroundedAnswer.model_validate_json(response()), SOURCES))
    assert checks[0].supported


@pytest.mark.parametrize("model_name", ["gpt-oss:20b", "gemma4:31b-cloud"])
def test_writer_schema_prompt_is_model_scoped(model_name):
    class Model:
        model = model_name

        async def structured_plan(self, messages, schema):
            if schema["title"] == "GroundingCheck":
                return '{"checks":{"0":{"supported":true,"reason":"Same meaning"}}}'
            assert ("JSON instance matching this schema" in messages[0]["content"]) == (model_name != "gpt-oss:20b")
            return response()

    answer = asyncio.run(answer_from_sources(Model(), [
        {"role": "system", "content": "Explain the material."},
        {"role": "user", "content": "Explain distances."}], SOURCES))
    assert "distance advantage" in answer


@pytest.mark.parametrize("malformed", [False, True])
@pytest.mark.parametrize("model_name", ["gpt-oss:20b", "gemma4:31b-cloud"])
def test_batch_preserves_rejections_and_falls_back(malformed, model_name):
    from app.agents.grounded_answer import GroundedAnswer, verify_points

    class Model:
        model = model_name
        calls = 0

        async def structured_plan(self, messages, schema):
            self.calls += 1
            assert "JSON schema:" not in messages[0]["content"]
            if self.calls == 1:
                return ('{"checks":{"0":{"supported":true}}}' if malformed else
                        '{"checks":{"0":{"supported":true},"1":{"supported":false}}}')
            return json.dumps({"checks": {"0": {"supported": self.calls == 2}}})

    answer = GroundedAnswer.model_validate_json(response())
    answer.points.append(answer.points[0].model_copy(update={"explanation": "Unsupported claim"}))
    model = Model()
    checks = asyncio.run(verify_points(model, answer, SOURCES))
    assert [check.supported for check in checks] == [True, False]
    assert [check.index for check in checks] == [0, 1]
    assert model.calls == (3 if malformed else 1)


@pytest.mark.parametrize("repair_supported", [False, True])
def test_gpt_batch_writer_repair_integration(repair_supported):
    class Model:
        model = "gpt-oss:20b"
        drafts = 0
        checks = 0

        async def structured_plan(self, messages, schema):
            payload = json.loads(messages[-1]["content"])
            if schema["title"] == "GroundingCheck":
                self.checks += 1
                assert "JSON schema:" not in messages[0]["content"]
                if self.checks == 1:
                    assert len(payload["claims"]) == 2
                    return json.dumps({"checks": {"0": {"supported": True},
                        "1": {"supported": False, "reason": "No support for regularization"}}})
                assert len(payload["claims"]) == 1
                return json.dumps({"checks": {"0": {"supported": repair_supported}}})
            self.drafts += 1
            if self.drafts == 1:
                draft = json.loads(response())
                draft["points"].append({"evidence": [{"label": "S1"}],
                    "explanation": "Regularization fixes the problem."})
                return json.dumps(draft)
            assert len(payload["repair_only"]) == 1
            assert payload["already_supported"] == ["The nearest points offer little distance advantage."]
            return json.dumps({"points": [{"evidence": [{"label": "S1"}],
                "explanation": "Nearest and average distances are similar."}]})

    model = Model()
    result = asyncio.run(answer_from_sources(model, [
        {"role": "system", "content": "Explain the material."},
        {"role": "user", "content": "Explain distances."}], SOURCES))
    assert model.drafts == model.checks == 2
    assert result.count("distance advantage") == 1
    assert "Regularization" not in result
    assert ("Nearest and average" in result) == repair_supported
    assert ("only part" in result) != repair_supported


@pytest.mark.parametrize("model_name", ["llama3.2:3b", "phi4-mini:latest"])
def test_small_models_keep_individual_verification(model_name):
    from app.agents.grounded_answer import GroundedAnswer, verify_points

    class Model:
        model = model_name
        calls = 0

        async def structured_plan(self, messages, schema):
            self.calls += 1
            assert len(json.loads(messages[-1]["content"])["claims"]) == 1
            return '{"checks":{"0":{"supported":true}}}'

    model = Model()
    answer = GroundedAnswer.model_validate_json(response())
    answer.points *= 4
    assert len(asyncio.run(verify_points(model, answer, SOURCES))) == 4
    assert model.calls == 4


def test_gpt_oversized_batch_falls_back(monkeypatch):
    from app.agents import grounded_answer as module
    monkeypatch.setattr(module, "estimate", lambda messages:
        200 if len(json.loads(messages[-1]["content"])["claims"]) > 1 else 50)
    monkeypatch.setattr(module, "input_limit", lambda: 100)

    class Model:
        model = "gpt-oss:20b"
        calls = 0

        async def structured_plan(self, messages, schema):
            self.calls += 1
            assert schema == check_schema_for(1)
            return '{"checks":{"0":{"supported":true}}}'

    model = Model()
    answer = module.GroundedAnswer.model_validate_json(response())
    answer.points *= 2
    assert len(asyncio.run(module.verify_points(model, answer, SOURCES))) == 2
    assert model.calls == 2
