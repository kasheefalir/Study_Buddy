import json
from pathlib import Path

from scripts.evaluate_quiz_speed_accuracy import BASELINE, COMPACT, checked_result


def test_checked_cases_have_independent_unambiguous_keys():
    cases = json.loads(Path("tests/fixtures/quiz_accuracy_cases.json").read_text())
    assert len({case["id"] for case in cases}) == len(cases)
    for case in cases:
        assert len(set(case["options"])) == 4
        assert case["options"].count(case["correct_answer"]) == 1
        assert all(checked_result(case, case).values())
        wrong = dict(case, correct_answer=next(x for x in case["options"] if x != case["correct_answer"]))
        assert not checked_result(case, wrong)["key_correct"]
        changed = dict(case, question="An easier unrelated question?")
        assert not checked_result(case, changed)["stem_preserved"]


def test_compact_prompt_removes_playback_work_without_extra_call():
    assert len(COMPACT) < len(BASELINE) / 2
    assert "next question" not in COMPACT
    assert "unsupported absolutes" in COMPACT
