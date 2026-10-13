import json

import pytest

from scripts.evaluate_evidence_chain import verify_selection, selected_sources, render_excerpts
from scripts.evaluate_evidence_refinements import citation_entity_flags, expand_neighbors, verify_mapping

SOURCES = [{"label": "S1", "text": "Points are\nnot much closer. Exception: structured data."},
           {"label": "S2", "text": "Different topic."}]


def selection(excerpt, source_id="S1"):
    return json.dumps({"status": "supported", "evidence": [{"source_id": source_id, "excerpt": excerpt}],
                       "missing_information": ""})


def test_whitespace_matches_restore_original_and_exclude_other_sources():
    _, verified = verify_selection(selection("Points are not much closer."), SOURCES)
    assert verified[0]["excerpt"] == "Points are\nnot much closer."
    assert selected_sources(verified, SOURCES) == SOURCES[:1]
    assert render_excerpts(verified).endswith("[S1]")


@pytest.mark.parametrize("excerpt,source_id", [
    ("Points are much closer.", "S1"), ("Points are not much closer.", "S2"),
    ("Points are not much closer.", "S99"), ("   ", "S1"),
])
def test_invented_excerpt_or_wrong_source_is_rejected(excerpt, source_id):
    with pytest.raises(ValueError):
        verify_selection(selection(excerpt, source_id), SOURCES)


def test_abstention_cannot_carry_answer_evidence():
    raw = json.loads(selection("Points are not much closer."))
    raw["status"] = "insufficient_evidence"
    with pytest.raises(ValueError):
        verify_selection(json.dumps(raw), SOURCES)


def test_comparison_citation_entity_mismatch_is_flagged():
    sources = [{"label": "S1", "text": "Low-dimensional points are closer."},
               {"label": "S2", "text": "Average distances increase."}]
    assert citation_entity_flags("Low-dimensional points are closer. [S2]", sources,
                                 ["low-dimensional"])
    assert not citation_entity_flags("Low-dimensional points are closer. [S1]", sources,
                                     ["low-dimensional"])
    # A reversed claim with the same entity passes: this is not semantic verification.
    assert not citation_entity_flags("Low-dimensional points are NOT closer. [S1]", sources,
                                     ["low-dimensional"])
    assert citation_entity_flags("Points are closer. [S99]", sources, [])


def test_neighbors_are_bounded_deduplicated_and_keep_labels():
    chunks = [{"id": i, "chapter": "other" if i == 0 else "same", "text": str(i)}
              for i in range(4)]
    sources = [{**chunks[i], "label": f"S{i}", "name": "Book"} for i in (1, 2)]
    expanded = expand_neighbors(chunks, sources)
    assert [s["id"] for s in expanded] == [1, 2, 3]
    assert [s["label"] for s in expanded] == ["S1", "S2", "N3"]


def test_mapping_checks_pdf_page_and_exact_quote():
    sources = [{"label": "S1", "page": 12, "text": "Points are closer."}]
    mapping = {"concepts": [{"concept": "Points", "source_id": "S1", "page": 12,
                              "excerpt": "Points are closer."}], "difference": ""}
    assert verify_mapping(json.dumps(mapping), sources)
    mapping["concepts"][0]["page"] = 13
    with pytest.raises(ValueError, match="page"):
        verify_mapping(json.dumps(mapping), sources)


def test_mapping_ids_check_metadata_without_requiring_quote_copy():
    sources = [{"label": "S1", "page": 12, "text": "Points are closer."}]
    raw = {"concepts": [{"concept": "Points", "source_id": "S1", "page": 12}], "difference": ""}
    assert verify_mapping(json.dumps(raw), sources, quotes=False)
    raw["concepts"][0]["source_id"] = "S9"
    with pytest.raises(ValueError):
        verify_mapping(json.dumps(raw), sources, quotes=False)
