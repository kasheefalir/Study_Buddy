import json

from app.agents.context_budget import pack
from app.agents.retrieval_context import current_study_session
from app.rag.library import write_json


def test_current_study_session_uses_ready_material_overview(tmp_path):
    root = tmp_path / "documents"
    identifier = "a" * 32
    chunks = [{"id": 1, "text": "R supports statistical computing.", "location": "Introduction"}]
    write_json(root / f"{identifier}.json", {"id": identifier, "name": "R notes", "page_title": "Introduction to R",
                                               "kind": "url", "status": "Ready"})
    write_json(root / identifier / "chunks.json", chunks)
    from app.rag.overview import fingerprint
    write_json(root / identifier / "overview.json", {"fingerprint": fingerprint(chunks), "status": "ready", "root": "book",
        "nodes": {"book": {"summary": "An introduction to R for statistical computing.",
                              "concepts": ["Functions", "Vectors"]}}})

    session = current_study_session(root, [identifier])
    card = session["materials"][0]
    assert card["title"] == "Introduction to R"
    assert card["orientation"] == "An introduction to R for statistical computing."
    assert card["main_concepts"] == ["Functions", "Vectors"]


def test_pack_keeps_study_session_distinct_from_source_evidence():
    messages, _, _ = pack("Professor", "What are we studying?", [],
                           {"study_session": {"selected_material_count": 1, "materials": [{"title": "Introduction to R"}]}}, [], 16)
    assert any(message["content"].startswith("Current study session") for message in messages)
    assert not any(message["content"].startswith("Reviewed session materials") for message in messages)
