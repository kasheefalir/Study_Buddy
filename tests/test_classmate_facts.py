import asyncio
import json

from app.rag.classmate_facts import prepare_facts
from app.rag.library import process, write_json


class Model:
    def __init__(self, invalid=False):
        self.invalid = invalid
        self.calls = 0

    async def structured_plan(self, messages, schema):
        self.calls += 1
        return json.dumps({"facts": [
            {"text": "Regularization helps prevent overfitting.", "chunk_id": 99 if self.invalid else 0},
            {"text": "Lasso can shrink coefficients to zero.", "chunk_id": 0}]})


def material(root):
    item = {"id": "a" * 32, "name": "Notes", "status": "Ready"}
    write_json(root / item["id"] / "chunks.json", [{"id": 0, "text": "Regularization prevents overfitting. Lasso can shrink coefficients to zero.", "location": "Slide 1"}])
    return item


def test_two_cached_facts_and_source_validation(tmp_path):
    item = material(tmp_path)
    model = Model()
    result = asyncio.run(prepare_facts(tmp_path, item, model))
    assert model.calls == 1 and result["facts_count"] == 2
    saved = json.loads((tmp_path / item["id"] / "facts.json").read_text())
    assert len(saved["facts"]) == 2
    assert all(f["source"] == "Notes · Slide 1" for f in saved["facts"])
    result = asyncio.run(prepare_facts(tmp_path, item, Model(invalid=True)))
    assert result["status"] == "Ready" and result["facts_status"] == "Unavailable"
    assert not (tmp_path / item["id"] / "facts.json").exists()


def test_reimport_invalidates_previous_facts(tmp_path):
    item = material(tmp_path)
    asyncio.run(prepare_facts(tmp_path, item, Model()))
    item.update(kind="pdf", filename="not-readable.pdf")
    process(tmp_path, item)
    assert not (tmp_path / item["id"] / "facts.json").exists()
    assert list((tmp_path / item["id"] / "versions").glob("*/facts.json"))
