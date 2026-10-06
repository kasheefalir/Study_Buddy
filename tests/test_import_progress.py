import pytest

from app import materials


@pytest.mark.parametrize("status,kind,error,stage", [
    ("Ready", "pptx", None, "ready"),
    ("Processing", "txt", None, "interrupted"),
    ("Saved locally · not indexed", "pdf", None, "stored"),
    ("Saved locally · not indexed", "txt", None, "stored"),
    ("Import failed", "txt", "No text", "failed"),
])
def test_inactive_import_states(status, kind, error, stage):
    result = materials.import_state({"id": "a" * 32, "status": status, "kind": kind, "error": error})
    assert result["import_stage"] == stage
    assert not result["importing"]


def test_active_stages_distinguish_searchable_text_from_facts(monkeypatch):
    identifier = "b" * 32
    monkeypatch.setattr(materials, "processing", {identifier})
    for stage in ["extracting", "indexing"]:
        result = materials.import_state({"id": identifier, "status": "Processing", "import_stage": stage})
        assert result["importing"] and result["import_stage"] == stage
    result = materials.import_state({"id": identifier, "status": "Ready"})
    assert result["importing"] and result["import_stage"] == "facts"
