import asyncio
import json

import pytest

from app.agents.small_models import quoted_trial as trial
from tests.test_small_grouped import Model


EVIDENCE = [{"passage_id": "PASSAGE_001", "passage_text": "Fare increases by 7.5 cents per mile.", "kind": "original"}]


def supported(quote="7.5 cents per mile", passage="PASSAGE_001"):
    return {"status": "supported", "claims": [{"claim": "Fare increases by 7.5 cents per mile.",
            "passage_id": passage, "quote": quote}]}


def test_exact_quotes_and_claim_requirements():
    assert not trial.validate_claims(supported(), EVIDENCE)
    for quote in ("7.5 cents/mile", "SOURCE_001", "", " "):
        assert trial.validate_claims(supported(quote), EVIDENCE)
    assert trial.validate_claims(supported(passage="PASSAGE_002"), EVIDENCE)
    assert trial.validate_claims({"status": "supported", "claims": []}, EVIDENCE)
    result = supported()
    del result["claims"][0]["quote"]
    assert trial.validate_claims(result, EVIDENCE)
    assert not trial.validate_claims({"status": "insufficient_evidence", "claims": []}, EVIDENCE)


def test_verbatim_match_does_not_certify_semantic_support():
    result = supported()
    result["claims"][0]["claim"] = "The author's laptop has 32 GB RAM."
    # An exact but irrelevant quote passes provenance, not semantic review.
    assert not trial.validate_claims(result, EVIDENCE)


def test_focus_preserves_original_wording_and_source_metadata():
    model = Model({"parts": [{"focus": "Southwest routes", "query": "Southwest fare effect", "source": "SOURCE_001"}]})
    books = [({"id": "opaque", "name": "Slides"}, [])]
    parts, _ = asyncio.run(trial.plan(model, "Compare Southwest routes and other routes", [], books))
    assert parts[0]["focus"] == "Southwest routes"
    payload = json.loads(model.messages[1]["content"])
    assert "materials" in payload["control_metadata"]
    model.result["parts"][0]["focus"] = "Southwest fare per mile"
    with pytest.raises(ValueError, match="exact span"):
        asyncio.run(trial.plan(model, "Compare Southwest routes and other routes", [], books))
    model.result["parts"][0].update(focus="Southwest routes", query="SOURCE_001")
    with pytest.raises(ValueError, match="control metadata"):
        asyncio.run(trial.plan(model, "Compare Southwest routes and other routes", [], books))


def test_independent_calls_and_deterministic_combination():
    class Recorder(Model):
        def __init__(self):
            super().__init__(supported())
            self.calls = []

        async def structured_plan(self, messages, schema):
            self.calls.append(json.loads(messages[1]["content"]))
            return await super().structured_plan(messages, schema)

    model = Recorder()
    groups = [{"part": {"focus": focus, "source": "SOURCE_001", "query": "private-query"},
               "evidence": EVIDENCE, "coverage": []} for focus in ("per mile", "Southwest")]
    result = asyncio.run(trial.answer(model, "per mile and Southwest", groups, {"PASSAGE_001": {"text": EVIDENCE[0]["passage_text"]}}))
    assert len(model.calls) == 2
    assert all(call["request"]["original_question"] == "per mile and Southwest" for call in model.calls)
    assert "SOURCE_001" not in json.dumps(model.calls)
    assert "private-query" not in json.dumps(model.calls)
    assert result["combined_answer"].count("Fare increases") == 2
    assert 'Evidence (PASSAGE_001): "7.5 cents per mile"' in result["combined_answer"]
    model.result = supported("A fabricated quote")
    invalid = asyncio.run(trial.answer(model, "per mile", groups[:1], {}))
    assert invalid["sections"][0]["validation_errors"]
    assert not invalid["sections"][0]["claims"]
    assert "Fare increases" not in invalid["combined_answer"]
