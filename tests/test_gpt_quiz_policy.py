import asyncio
import json
from pathlib import Path

import pytest

from app.agents import quiz
from app.agents.gpt.quiz_policy import QUALITY_PROMPT, distinguishing_answer
from scripts.evaluate_quiz_overlap_holdouts import QUALITY_TRIAL_PROMPT, variants
from scripts.evaluate_quiz_overlap import distinguishing_answer as trial_distinguishing


def test_promoted_policy_matches_evaluated_candidate():
    assert QUALITY_PROMPT == QUALITY_TRIAL_PROMPT
    for case in json.loads(Path("tests/fixtures/quiz_overlap_holdouts.json").read_text()):
        for _, data, _, _ in variants(case):
            assert distinguishing_answer(data) == trial_distinguishing(data)


@pytest.mark.parametrize("model", [None, "llama3.2:3b", "phi4-mini:latest", "gemma4:31b-cloud", "deepseek-r1:8b", "gpt-oss:20b"])
@pytest.mark.parametrize("source_backed", [True, False])
def test_overlap_exception_is_only_source_backed_gpt(model, source_backed):
    case = json.loads(Path("tests/fixtures/quiz_overlap_holdouts.json").read_text())[0]
    data = variants(case)[0][1]
    result = quiz.choice_question_problem(data, model=model, source_backed=source_backed)
    assert bool(result) == (model != "gpt-oss:20b" or not source_backed)
    duplicate = dict(data, options=[data["correct_answer"]] * 4)
    assert quiz.choice_question_problem(duplicate, model=model, source_backed=source_backed)


@pytest.mark.parametrize("model", ["llama3.2:3b", "phi4-mini:latest", "gemma4:31b-cloud", "deepseek-r1:8b", "gpt-oss:20b"])
@pytest.mark.parametrize("source_backed", [True, False])
def test_quality_prompt_is_scoped_and_rejection_is_preserved(monkeypatch, model, source_backed):
    captured = []

    async def bounded(llm, stage, prompt, data, sources):
        captured.append(prompt)
        return {"valid": False, "stem_answered": False, "distractors_answer_stem": True,
                "issue": "Wrong key"}, sources

    monkeypatch.setattr(quiz, "bounded", bounded)
    client = type("Client", (), {"model": model})()
    data = dict(question="Which?", options=["A", "B", "C", "D"], correct_answer="B", expected_answer="B")
    issue = asyncio.run(quiz.choice_quality_problem(client, data, [{"text": "Evidence"}] if source_backed else []))
    assert issue == "Wrong key"
    assert len(captured) == 1
    assert captured[0] == (QUALITY_PROMPT if model == "gpt-oss:20b" and source_backed else quiz.CHOICE_QUALITY_PROMPT)
