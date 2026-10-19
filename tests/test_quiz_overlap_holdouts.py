import json
from pathlib import Path

from app.agents.quiz import choice_question_problem
from scripts.evaluate_quiz_overlap import candidate_problem
from scripts.evaluate_quiz_overlap_holdouts import variants, scorecard


def test_holdouts_probe_newly_admitted_answers_and_preserve_input():
    cases = json.loads(Path("tests/fixtures/quiz_overlap_holdouts.json").read_text())
    for case in cases:
        before = json.dumps(case)
        rows = variants(case)
        assert json.dumps(case) == before
        assert [row[3] for row in rows] == [True, False, False, False]
        for kind, data, source, expected in rows:
            assert len(set(data["options"])) == 4
            assert data["correct_answer"] in data["options"]
            if case["id"] == "data_structure":
                # This subject is an unchanged-path control: the existing rule
                # already allows it because the answer adds two lexical tokens.
                assert candidate_problem(data) == choice_question_problem(data)
            elif kind != "overlapping":
                assert choice_question_problem(data)
                assert not candidate_problem(data)
            else:
                assert choice_question_problem(data)
                assert candidate_problem(data)
        assert rows[0][1] == rows[3][1]
        assert rows[0][2] != rows[3][2]


def test_scorecard_separates_regressions_from_existing_failures_and_errors():
    base = {"model": "test", "expected_accept": False, "accepted": True,
            "old_issue": "blocked", "candidate_issue": ""}
    rows = [base, dict(base, old_issue=""), dict(base, accepted=None),
            dict(base, accepted=False)]
    result = scorecard(rows)["test"]
    assert result == {"completed_checks": 4, "correct_decisions": 1, "false_accepts": 2,
                      "newly_admitted_false_accepts": 1, "errors": 1}
