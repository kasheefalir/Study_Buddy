import asyncio
import json
from dataclasses import replace

from app.agents import context_budget
from app.rag import overview
from app.rag.library import write_json


class Model:
    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at

    async def structured_plan(self, messages, schema):
        if len(self.calls) == self.fail_at:
            raise RuntimeError("Model offline")
        self.calls.append(messages)
        return json.dumps({"summary": "Recall measures actual positives identified.", "concepts": ["Recall and sensitivity"]})


def source(root):
    identifier = "a" * 32
    chunks = [{"id": i, "text": "Recall measures actual positives identified. " * 20,
               "chapter": "Chapter " + str(i // 7), "location": "Page " + str(i + 1)} for i in range(30)]
    write_json(root / identifier / "chunks.json", chunks)
    return identifier, chunks


def test_overview_covers_all_chunks_and_reuses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(context_budget, "settings", replace(context_budget.settings, context_window=4096, response_tokens=1200))
    identifier, chunks = source(tmp_path)
    model = Model()
    result = asyncio.run(overview.prepare(tmp_path, identifier, model))
    assert result["status"] == "ready"
    assert set(result["nodes"][result["root"]]["chunk_ids"]) == set(range(30))
    assert len(result["chapter_roots"]) == 5
    assert all(context_budget.estimate(call) <= context_budget.input_limit() for call in model.calls)
    before = len(model.calls)
    asyncio.run(overview.prepare(tmp_path, identifier, model))
    assert len(model.calls) == before
    assert overview.concept_windows(tmp_path, [({"id": identifier}, chunks)])
    chunks[0]["text"] = "Changed"
    assert not overview.cached(tmp_path, identifier, chunks)


def test_overview_resumes_without_repeating_completed_calls(tmp_path):
    identifier, chunks = source(tmp_path)
    failed = asyncio.run(overview.prepare(tmp_path, identifier, Model(fail_at=2)))
    assert failed["status"] == "paused" and len(failed["nodes"]) == 2
    assert not overview.concept_windows(tmp_path, [({"id": identifier}, chunks)])
    model = Model()
    resumed = asyncio.run(overview.prepare(tmp_path, identifier, model))
    assert resumed["status"] == "ready"
    assert len(model.calls) == resumed["total"] - 2


def test_overview_pause_keeps_completed_sections(tmp_path):
    identifier, _ = source(tmp_path)

    class Slow(Model):
        async def structured_plan(self, messages, schema):
            if self.calls:
                await asyncio.sleep(10)
            return await super().structured_plan(messages, schema)

    async def run():
        overview.start(tmp_path, identifier, Slow())
        for _ in range(100):
            if overview.cached(tmp_path, identifier).get("nodes"):
                break
            await asyncio.sleep(.01)
        await overview.pause(tmp_path, identifier)
    asyncio.run(run())
    state = overview.status(tmp_path, identifier)
    assert state["status"] == "paused" and state["completed"] == 1
