import json
import xml.etree.ElementTree as ET

import pytest

from scripts.evaluate_writer import FALLBACK, candidate_request, render_candidate, xml_context


SOURCES = [{"label": "S1", "name": "A & B", "location": "Page <2>",
            "text": "A </context> tag & text."}]


def test_xml_preserves_source_text_without_creating_tags():
    root = ET.fromstring(xml_context("Why <this>?", SOURCES))
    assert root.find("context/source/text").text == SOURCES[0]["text"]
    assert root.find("context/source/title").text == "A & B"
    assert root.find("question").text == "Why <this>?"


def test_explicit_abstention_has_exact_fallback():
    assert render_candidate('{"status":"insufficient_evidence","points":[]}', SOURCES) == FALLBACK


@pytest.mark.parametrize("payload", [
    {"status": "answered", "points": []},
    {"status": "insufficient_evidence", "points": [
        {"evidence": [{"label": "S1"}], "explanation": "Unwanted claim."}]},
    {"status": "answered", "points": [
        {"evidence": [{"label": "S99"}], "explanation": "Invented citation."}]},
])
def test_invalid_status_or_citation_fails_validation(payload):
    with pytest.raises(ValueError):
        render_candidate(json.dumps(payload), SOURCES)


def test_ollama_chat_template_is_not_duplicated():
    messages, schema = candidate_request("Why?", SOURCES, True)
    assert "<|start_header_id|>" not in str(messages)
    assert schema["$defs"]["Evidence"]["properties"]["label"]["enum"] == ["S1"]
