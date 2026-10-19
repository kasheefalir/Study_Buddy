import asyncio
import json

import pytest

from app.agents import query_plan_trial as trial


class Model:
    def __init__(self, value):
        self.value = value

    async def structured_plan(self, *args):
        return json.dumps(self.value)


def test_plan_rejects_out_of_scope_and_blank_queries():
    data = {"selected_materials": [{"id": "selected"}]}
    for ids, queries in [(["other"], ["concept"]), (["selected"], [" "])]:
        model = Model({"standalone_question": "Explain concept", "queries": queries, "document_ids": ids})
        with pytest.raises(ValueError):
            asyncio.run(trial.plan_queries(model, data))


def test_multi_query_keeps_both_concepts(monkeypatch, tmp_path):
    chunks = [{"id": i, "text": str(i), "location": str(i)} for i in range(6)]

    async def retrieve(root, item, chunks, query, limit):
        return chunks[:3] if query == "A" else chunks[3:]

    monkeypatch.setattr(trial, "retrieve", retrieve)
    sources, traces, _ = asyncio.run(trial.collect(tmp_path, [({"id": "book", "name": "Book"}, chunks)], ["A", "B"]))
    assert {0, 1, 3, 4} <= {s["chunk_id"] for s in sources}
    assert len(traces) == 2
    assert len({s["label"] for s in sources}) == len(sources)


def test_summary_uses_coverage_not_vector_search(tmp_path, monkeypatch):
    async def retrieve(*args):
        raise AssertionError("Summary must not run nearest-vector search")

    monkeypatch.setattr(trial, "retrieve", retrieve)
    chunks = [{"id": 1, "text": "Complete short material", "location": "Section"}]
    sources, traces, coverage = asyncio.run(trial.collect(tmp_path, [({"id": "book", "name": "Book"}, chunks)], ["summary"], overview=True))
    assert traces[0]["strategy"] == "full_text"
    assert coverage[0]["complete"]
    assert sources[0]["text"] == chunks[0]["text"]


def test_explanation_labels_extras_without_suppressing_answer():
    source = {"label": "S1", "text": "Original text", "variant": "original"}
    model = Model({"source_based": "A paraphrase [S1]", "source_ids": ["S1", "S99"],
                   "additional_context": "An outside example"})
    result = asyncio.run(trial.explain(model, "Question", [source], []))
    assert result["source_based"] == "A paraphrase [S1]"
    assert result["additional_context_label"] == "Additional context - not verified against your material"
    assert result["unknown_source_ids"] == ["S99"]
    assert result["supporting_passages"] == [source]
    assert "not independently verified" in result["support_status"]
