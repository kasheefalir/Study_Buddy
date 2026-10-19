import asyncio
import json

import pytest

from app.agents.grounded_answer import GroundedAnswer
from scripts.evaluate_summary_verification import batched, single, verdict_metrics, coverage


def test_score_distinguishes_false_acceptance_from_format_failure():
    assert verdict_metrics([True, False], [False, True]) == {
        "format_error": False, "correct": 0, "false_accepts": 1, "false_rejects": 1}
    assert verdict_metrics([True, False], None)["false_accepts"] is None


def test_missing_batch_slot_is_not_accepted():
    class Model:
        model = "gemma4:31b-cloud"
        async def structured_plan(self, messages, schema):
            assert schema["properties"]["checks"]["required"] == ["0", "1"]
            return json.dumps({"checks": {"0": {"supported": True}}})
    answer = GroundedAnswer(points=[{"explanation": "Fact", "evidence": [{"label": "S1"}]}] * 2)
    with pytest.raises(ValueError, match="Incomplete"):
        asyncio.run(batched(Model(), answer, [{"label": "S1", "text": "Fact"}]))


def test_lexical_screen_is_not_a_truth_judge():
    # Mentioning a concept is not proof that the summary explains it correctly.
    assert coverage({"summary": "Overfitting guarantees generalization."})["overfitting"]


def test_single_baseline_remains_per_point_for_gemma():
    class Model:
        model = "gemma4:31b-cloud"
        calls = 0

        async def structured_plan(self, messages, schema):
            self.calls += 1
            assert schema["properties"]["checks"]["required"] == ["0"]
            return json.dumps({"checks": {"0": {"supported": True, "reason": "Supported"}}})

    model = Model()
    answer = GroundedAnswer(points=[{"explanation": "Fact", "evidence": [{"label": "S1"}]}] * 4)
    checks = asyncio.run(single(model, answer, [{"label": "S1", "text": "Fact"}]))
    assert model.calls == 4
    assert [check.index for check in checks] == [0, 1, 2, 3]
