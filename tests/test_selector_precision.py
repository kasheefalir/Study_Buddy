import pytest

from scripts.evaluate_selector_precision import CoverageSelection, selector_request, selection_metrics
from scripts.evaluate_span_selection import make_spans


SOURCES = [{"label": "S1", "text": "A costs ten. B costs twenty."}]


def test_schema_visible_only_in_schema_variant_and_ids_constrained():
    spans = make_spans(SOURCES)
    baseline, schema = selector_request("Compare A and B", SOURCES, spans, "baseline")
    shown, _ = selector_request("Compare A and B", SOURCES, spans, "schema")
    assert "Output schema" not in baseline[0]["content"]
    assert "Output schema" in shown[0]["content"]
    assert schema["properties"]["span_ids"]["items"]["enum"] == [s["id"] for s in spans]


def test_supported_coverage_cannot_omit_part():
    with pytest.raises(ValueError):
        CoverageSelection(status="supported", span_ids=["S1:P1"], requirements=[
            {"question_part": "A", "span_ids": ["S1:P1"]}, {"question_part": "B", "span_ids": []}])


def test_coverage_can_abstain_without_discarding_partial_diagnostic():
    result = CoverageSelection(status="insufficient_evidence", span_ids=[], requirements=[
        {"question_part": "A", "span_ids": ["S1:P1"]}, {"question_part": "B", "span_ids": []}])
    assert result.span_ids == []


def test_metric_separates_coverage_and_precision():
    metrics = selection_metrics(["A", "B", "C"], ["A"], ["A", "B"])
    assert metrics["coverage"] is True
    assert metrics["extra_ids"] == ["C"]
    assert metrics["precision"] == 2 / 3
    assert selection_metrics([], [], [])["correct_abstention"] is True
    assert selection_metrics(["A"], [], [])["correct_abstention"] is False
