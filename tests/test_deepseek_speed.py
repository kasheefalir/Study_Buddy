import asyncio
import json

import pytest

from app.agents.deepseek.cache import ReadCache
from app.agents.deepseek.planning import CombinedRoute, Read
from app.agents.deepseek.agent import DeepSeekAgent
from app.agents.deepseek.verification import verify_batch
from app.agents.grounded_answer import GroundedAnswer
from app.storage.conversation_store import ConversationStore


def test_cache_versions_scope_and_defensive_copies(tmp_path):
    cache = ReadCache(capacity=1)
    item = {"id": "book", "name": "Title"}
    chunks = [{"id": 1, "text": "before"}]
    read = Read(tool="search", document_id="book", query="subject")
    key = cache.key(tmp_path, item, chunks, read)
    cache.put(key, [{"text": "before"}])
    result = cache.get(key)
    result[0]["text"] = "changed"
    assert cache.get(key)[0]["text"] == "before"
    assert cache.key(tmp_path, item, [{"id": 1, "text": "after"}], read) != key
    assert cache.key(tmp_path, item, chunks, read.model_copy(update={"query": "different"})) != key
    assert cache.key(tmp_path / "other", item, chunks, read) != key
    (tmp_path / "book").mkdir()
    (tmp_path / "book" / "embeddings.json").write_text('{}')
    assert cache.key(tmp_path, item, chunks, read) != key
    cache.put("second", [])
    assert cache.get(key) is None
    cache.ttl = -1
    assert cache.get("second") is None


def test_supplied_plan_skips_planning_and_cache_skips_retrieval(tmp_path, monkeypatch):
    import importlib
    module = importlib.import_module("app.agents.deepseek.search")
    item = {"id": "book", "name": "Book"}
    chunks = [{"id": 1, "text": "fact", "location": "p1"}]
    monkeypatch.setattr(module, "library", lambda *args: [(item, chunks)])
    calls = []

    async def retrieve(*args):
        calls.append(args)
        return chunks

    monkeypatch.setattr(module, "retrieve", retrieve)
    cache = ReadCache()
    reads = [Read(tool="search", document_id="book", query="fact")]
    first = asyncio.run(module.search(object(), tmp_path, ["book"], "fact", initial_reads=reads, cache=cache, max_rounds=1))
    second = asyncio.run(module.search(object(), tmp_path, ["book"], "fact", initial_reads=reads, cache=cache, max_rounds=1))
    assert first == second and len(calls) == 1 and cache.hits == 1


def test_combined_conversation_cannot_request_tools(tmp_path):
    class Fake:
        async def structured_plan(self, *args):
            return CombinedRoute(route="conversation", question="hi", action="keep", clarification="",
                                 reads=[Read(tool="search", document_id="book", query="fact")]).model_dump_json()

    store = ConversationStore(tmp_path)
    with pytest.raises(ValueError, match="non-retrieval"):
        asyncio.run(DeepSeekAgent(Fake(), store, combined=True).reply("hi", document_ids=[]))
    assert store.list_sessions() == []


def test_combined_success_needs_no_second_planner(tmp_path, monkeypatch):
    import app.agents.deepseek.agent as module
    monkeypatch.setattr(module, "library", lambda *args: [({"id": "book", "name": "Book"}, [])])
    calls = []

    class Fake:
        async def structured_plan(self, *args):
            calls.append("intent")
            return CombinedRoute(route="retrieve", question="fact", action="keep", clarification="",
                reads=[Read(tool="search", document_id="book", query="fact")]).model_dump_json()

    async def search(*args, **kwargs):
        assert kwargs["max_rounds"] == 1
        assert kwargs["initial_reads"][0].query == "fact"
        calls.append("search")
        return [{"label": "S1", "text": "fact"}], [], ""

    async def answer(*args, **kwargs):
        calls.append("writer")
        return "Fact [S1]"

    monkeypatch.setattr(module, "search", search)
    monkeypatch.setattr(module, "answer_from_sources", answer)
    asyncio.run(DeepSeekAgent(Fake(), ConversationStore(tmp_path), combined=True).reply("fact", materials_root=tmp_path, document_ids=["book"]))
    assert calls == ["intent", "search", "writer"]


def test_batch_missing_verdict_rejected():
    class Fake:
        async def structured_plan(self, *args):
            return json.dumps({"checks": {"0": {"supported": True, "reason": "yes"}}})

    answer = GroundedAnswer.model_validate({"points": [{"evidence": [{"label": "S1"}], "explanation": "fact"}] * 2})
    with pytest.raises(ValueError, match="Incomplete"):
        asyncio.run(verify_batch(Fake(), answer, [{"label": "S1", "text": "fact"}]))


@pytest.mark.parametrize("initial", [[], [{"label": "S1", "text": "irrelevant"}]])
def test_combined_recovers_once_without_forcing_an_answer(tmp_path, monkeypatch, initial):
    import app.agents.deepseek.agent as module
    monkeypatch.setattr(module, "library", lambda *args: [({"id": "book", "name": "Book"}, [])])
    reads = []
    writes = []

    class Fake:
        async def structured_plan(self, *args):
            return CombinedRoute(route="retrieve", question="fact", action="keep", clarification="",
                reads=[Read(tool="search", document_id="book", query="fact")]).model_dump_json()

    async def search(*args, **kwargs):
        reads.append(kwargs)
        return (initial if len(reads) == 1 else [{"label": "S1", "text": "still insufficient"}]), [], ""

    async def answer(*args, **kwargs):
        writes.append(args)
        return module.EVIDENCE_GAP

    monkeypatch.setattr(module, "search", search)
    monkeypatch.setattr(module, "answer_from_sources", answer)
    _, reply = asyncio.run(DeepSeekAgent(Fake(), ConversationStore(tmp_path), combined=True).reply(
        "fact", materials_root=tmp_path, document_ids=["book"]))
    assert reply == module.EVIDENCE_GAP
    assert len(reads) == 2 and len(writes) == (2 if initial else 1)
    assert "initial_reads" not in reads[1]
