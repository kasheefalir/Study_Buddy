import json

import pytest

from scripts.evaluate_span_selection import (
    Explanation, SpanSelection, make_spans, resolve_ids, span_sources, render_bound, quote_spans, quote_fallback,
)
from scripts.evaluate_writer import FALLBACK


SOURCES = [{"label": "S3", "text": "Nearby points differ.\nExceptions matter (in structured data)."}]


def test_spans_are_exact_and_reconstruct_original():
    spans = make_spans(SOURCES)
    assert "".join(s["text"] for s in spans) == SOURCES[0]["text"]
    assert len(spans) == 2
    for span in spans:
        assert SOURCES[0]["text"][span["start"]:span["end"]] == span["text"]
    selected = resolve_ids(["S3:P2"], spans)
    assert span_sources(selected, SOURCES)[0]["text"].endswith("(in structured data).")
    assert quote_spans(selected).endswith("[S3]")


@pytest.mark.parametrize("ids", [["S9:P1"], ["S3:P1", "S3:P1"]])
def test_unknown_or_duplicate_ids_rejected(ids):
    with pytest.raises(ValueError):
        resolve_ids(ids, make_spans(SOURCES))


@pytest.mark.parametrize("status,ids", [("supported", []), ("insufficient_evidence", ["S3:P1"])])
def test_selection_status_consistency(status, ids):
    with pytest.raises(ValueError):
        SpanSelection(status=status, span_ids=ids)


def test_code_attaches_source_and_writer_cannot_choose_citation():
    raw = json.dumps({"status": "answered", "explanation": "Exceptions matter."})
    assert render_bound(raw, SOURCES[0]) == "Exceptions matter. [S3]"
    with pytest.raises(ValueError):
        Explanation(status="answered", explanation="Exceptions matter. [S1]")
    assert render_bound(json.dumps({"status": "insufficient_evidence", "explanation": ""}), SOURCES[0]) == FALLBACK


def test_empty_selection_never_fabricates_source_text():
    assert span_sources([], SOURCES) == []
    assert quote_spans([]) == FALLBACK


def test_quote_fallback_requires_verified_relevance_not_just_valid_ids():
    selected = resolve_ids(["S3:P2"], make_spans(SOURCES))
    assert quote_fallback(FALLBACK, selected, relevance_verified=False) == FALLBACK
    assert quote_fallback(FALLBACK, selected, relevance_verified=True) == quote_spans(selected)
    assert quote_fallback(FALLBACK, [], relevance_verified=True) == FALLBACK
    assert quote_fallback("Existing answer", selected, relevance_verified=True) == "Existing answer"
