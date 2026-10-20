import asyncio
import json

import pytest

from scripts import evaluate_quiz_comparison as evaluation


class Model:
    def __init__(self, model):
        self.model = model
        self.calls = []
        self.number = 0

    async def structured_plan(self, messages, schema):
        self.calls.append({"schema": schema["title"]})
        if schema["title"] == "ChoiceQuality":
            return json.dumps(dict(valid=True, stem_answered=True, distractors_answer_stem=True, issue=""))
        if schema["title"] == "ChoiceFeedback":
            return json.dumps(dict(explanation="This is the concept in the passage.",
                                   correction="Compare the definition in the source.", example="Consider a hypothetical dataset."))
        assert schema["title"] == "ChoiceQuestion"
        questions = ["What is the median?", "Why is correlation insufficient for causation?",
                     "How can overfitting affect generalization?", "Which observations are used to calculate precision?",
                     "Where should preprocessing statistics be fitted?"]
        question = questions[self.number]
        self.number += 1
        return json.dumps(dict(summary="A concept from the source.", question=question,
                               options=["First answer", "Second answer", "Third answer", "Fourth answer"],
                               correct_answer="First answer", expected_answer="The source supports the first answer."))


@pytest.mark.parametrize("prepared", [False, True])
def test_full_protocol_and_persisted_review(tmp_path, monkeypatch, prepared):
    monkeypatch.setattr(evaluation, "TraceClient", Model)
    result = asyncio.run(evaluation.sequence(tmp_path, evaluation.fixture(tmp_path), "fake", prepared))
    assert result["mechanics_passed"], result.get("error")
    assert result["completed_answers"] == 5
    assert len(result["calls"]) == 15
    assert result["turns"][-1]["model_calls"] == 0
    next_turns = [t for t in result["turns"] if t["name"].startswith("next_")]
    assert all(t["model_calls"] == (0 if prepared else 2) for t in next_turns)
    assert result["final_state"]["pending_question"] == "Where should preprocessing statistics be fitted?"


def test_two_question_batches_preserve_playback_and_final_state(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, "TraceClient", Model)
    result = asyncio.run(evaluation.sequence(tmp_path, evaluation.fixture(tmp_path), "fake", True, batch_size=2))
    assert result["mechanics_passed"], result.get("error")
    turns = {t["name"]: t for t in result["turns"]}
    assert [turns[name]["model_calls"] for name in ("start", "next_2", "next_3", "next_4", "next_5")] == [4, 0, 4, 0, 2]
    assert len(result["final_state"]["results"]) == 5
    assert len(result["calls"]) == 15


def test_failed_second_batch_preserves_answered_first_batch(tmp_path, monkeypatch):
    class FailingModel(Model):
        async def structured_plan(self, messages, schema):
            if schema["title"] == "ChoiceQuestion" and self.number == 3:
                raise RuntimeError("Synthetic generation failure")
            return await super().structured_plan(messages, schema)
    monkeypatch.setattr(evaluation, "TraceClient", FailingModel)
    result = asyncio.run(evaluation.sequence(tmp_path, evaluation.fixture(tmp_path), "fake", True, batch_size=2))
    assert not result["mechanics_passed"]
    assert result["completed_answers"] == 2
    assert result["turns"][-1]["input_state_preserved"]
    assert result["final_state"]["cursor"] == 1
    assert result["final_state"]["phase"] == "review"


def test_failed_generation_is_reported_without_progress_loss(tmp_path, monkeypatch):
    class Broken(Model):
        async def structured_plan(self, messages, schema):
            raise RuntimeError("Unavailable")

    monkeypatch.setattr(evaluation, "TraceClient", Broken)
    result = asyncio.run(evaluation.sequence(tmp_path, evaluation.fixture(tmp_path), "fake", False))
    assert not result["mechanics_passed"]
    assert result["completed_answers"] == 0
    assert result["turns"][0]["input_state_preserved"]


@pytest.mark.parametrize("broken", ["fenced", "long"])
def test_format_repair_is_bounded_and_preserves_original_request(monkeypatch, broken):
    valid = dict(summary="A short summary.", question="What does precision measure?",
                 options=["True positives among predicted positives", "Recall", "Mean", "Median"],
                 correct_answer="True positives among predicted positives",
                 expected_answer="Precision measures true positives among positive predictions.")
    invalid = "```json\n" + json.dumps({"properties": valid}) + "\n```" if broken == "fenced" else json.dumps({**valid, "summary": "x" * 401})
    requests = []

    async def chat(self, messages, **kwargs):
        requests.append(messages)
        return invalid if len(requests) == 1 else json.dumps(valid)

    monkeypatch.setattr(evaluation.TraceClient, "chat", chat)
    messages = [{"role": "system", "content": "Original source-bounded instruction"},
                {"role": "user", "content": "Original sources"}]
    schema = evaluation.OUTPUTS["quiz choices"].model_json_schema()
    output = asyncio.run(evaluation.FormatRepairClient("fake").structured_plan(messages, schema))
    assert json.loads(output) == valid
    assert len(requests) == 2
    assert len(messages) == 2 and requests[1][:2] == messages
    assert requests[1][-2]["content"] == invalid
    assert json.loads(requests[1][-1]["content"])["format_errors"]


def test_repair_failure_does_not_loop(monkeypatch):
    requests = []

    async def chat(self, messages, **kwargs):
        requests.append(messages)
        return "not json"

    monkeypatch.setattr(evaluation.TraceClient, "chat", chat)
    with pytest.raises(ValueError):
        asyncio.run(evaluation.FormatRepairClient("fake").structured_plan([], evaluation.OUTPUTS["quiz choices"].model_json_schema()))
    assert len(requests) == 2


@pytest.mark.parametrize("prepared", [False, True])
@pytest.mark.parametrize("broken_stage", ["ChoiceQuestion", "ChoiceQuality"])
def test_live_quiz_path_recovers_from_late_malformed_output(tmp_path, monkeypatch, prepared, broken_stage):
    class Flaky(Model):
        failed = False

        async def structured_plan(self, messages, schema):
            if not self.failed and self.number >= 3 and schema["title"] == broken_stage:
                self.failed = True
                if broken_stage == "ChoiceQuality":
                    self.number -= 1
                return '```json\n{"properties":{}}\n```\nHere is the question:\n```json\n{}\n```'
            return await super().structured_plan(messages, schema)

    monkeypatch.setattr(evaluation, "TraceClient", Flaky)
    result = asyncio.run(evaluation.sequence(tmp_path, evaluation.fixture(tmp_path), "fake", prepared))
    assert result["mechanics_passed"], result.get("error")
    assert result["completed_answers"] == 5


def test_live_quiz_malformed_output_has_bounded_retries(tmp_path, monkeypatch):
    class Broken(Model):
        count = 0

        async def structured_plan(self, messages, schema):
            Broken.count += 1
            return "schema instead of values"

    monkeypatch.setattr(evaluation, "TraceClient", Broken)
    result = asyncio.run(evaluation.sequence(tmp_path, evaluation.fixture(tmp_path), "fake", False))
    assert not result["mechanics_passed"]
    assert result["turns"][0]["input_state_preserved"]
    assert Broken.count == 3


def test_quiz_quality_rejection_gets_one_scoped_recovery_read(tmp_path, monkeypatch):
    from app.rag import semantic
    reads = []

    async def retrieve(root, item, chunks, query, limit):
        reads.append((item["id"], query, limit))
        return chunks[:limit]

    class Rejected(Model):
        async def structured_plan(self, messages, schema):
            if schema["title"] == "ChoiceQuality":
                return json.dumps(dict(valid=False, stem_answered=False,
                    distractors_answer_stem=True, issue="The source does not support this claim."))
            return await super().structured_plan(messages, schema)

    monkeypatch.setattr(semantic, "retrieve", retrieve)
    monkeypatch.setattr(evaluation, "TraceClient", Rejected)
    result = asyncio.run(evaluation.sequence(tmp_path, evaluation.fixture(tmp_path), "fake", False))
    assert not result["mechanics_passed"]
    assert result["turns"][0]["input_state_preserved"]
    assert len(reads) == 1
    assert reads[0][2] == 3
