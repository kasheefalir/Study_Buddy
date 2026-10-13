from app.agents.retrieval_context import reusable_evidence
from app.rag.library import write_json


def test_reuse_requires_unchanged_selected_original_passages(tmp_path):
    identifier = "a" * 32
    write_json(tmp_path / identifier / "chunks.json", [{"id": 1, "text": "Original passage"}])
    source = {"document_id": identifier, "chunk_id": 1, "text": "Original passage", "label": "S1"}
    history = [{"role": "assistant", "sources": [source]}]
    assert reusable_evidence(tmp_path, [identifier], history) == [source]
    assert reusable_evidence(tmp_path, [], history) == []
    write_json(tmp_path / identifier / "chunks.json", [{"id": 1, "text": "Changed passage"}])
    assert reusable_evidence(tmp_path, [identifier], history) == []


def test_generated_overviews_are_not_reused_as_original_evidence(tmp_path):
    source = {"document_id": "a" * 32, "variant": "generated_summary"}
    assert reusable_evidence(tmp_path, ["a" * 32], [{"sources": [source]}]) == []
