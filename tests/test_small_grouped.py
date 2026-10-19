import asyncio
import json

import pytest

from app.agents.small_models import workflow as w


class Model:
    def __init__(self, result):
        self.result = result
        self.schema = None
        self.messages = None

    async def structured_plan(self, messages, schema):
        self.schema, self.messages = schema, messages
        return json.dumps(self.result)


def test_short_material_enum_and_unknown_rejection():
    books = [({"id": "opaque", "name": "Book"}, [])]
    model = Model({"parts": [{"question": "What is A?", "query": "A", "material": "M1"}]})
    parts, mapping = asyncio.run(w.plan(model, "A?", [], books))
    assert parts[0]["id"] == "Q1"
    assert mapping["M1"] == books[0]
    assert "opaque" not in json.dumps(model.messages)
    assert model.schema["properties"]["parts"]["items"]["properties"]["material"]["enum"] == ["M1"]
    model.result["parts"][0]["material"] = "M2"
    with pytest.raises(ValueError, match="Unknown material"):
        asyncio.run(w.plan(model, "A?", [], books))


def test_answer_requires_all_parts_and_local_sources():
    groups = [{"part": {"id": f"Q{i}"}, "evidence": [{"id": f"S{i}"}]} for i in (1, 2)]
    model = Model({"Q1": {"answer": "A", "source_ids": ["S1"], "additional_context": ""}})
    with pytest.raises(ValueError, match="Missing"):
        asyncio.run(w.answer(model, "Compare", groups, {}))
    model.result["Q2"] = {"answer": "B", "source_ids": ["S1"], "additional_context": ""}
    with pytest.raises(ValueError, match="outside"):
        asyncio.run(w.answer(model, "Compare", groups, {"S1": {}}))
    model.result["Q2"]["source_ids"] = ["S2"]
    registry = {"S1": {"text": "Original A"}, "S2": {"text": "Original B"}}
    result = asyncio.run(w.answer(model, "Compare", groups, registry))
    assert result["Q2"]["sources"] == [registry["S2"]]
    assert "not independently verified" in result["Q1"]["support_note"]


def test_grouped_evidence_preserves_part_and_hides_storage_ids(monkeypatch, tmp_path):
    async def collect(root, books, queries, overview=False):
        return ([{"text": queries[0], "document_id": "opaque", "chunk_id": 12}], [], [])

    monkeypatch.setattr(w, "collect", collect)
    parts = [{"id": f"Q{i}", "query": f"concept{i}", "material": "M1"} for i in (1, 2)]
    groups, registry = asyncio.run(w.gather(tmp_path, parts, {"M1": ({}, [])}))
    assert groups[0]["evidence"][0]["id"] == "S1"
    assert groups[1]["evidence"][0]["id"] == "S2"
    assert "opaque" not in json.dumps(groups)
    assert registry["S2"]["document_id"] == "opaque"
