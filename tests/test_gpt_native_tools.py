import asyncio
import copy

import httpx
import pytest

from scripts import evaluate_gpt_tools as trial_module


def test_native_transcript_and_unknown_citations(tmp_path, monkeypatch):
    monkeypatch.setattr(trial_module, "library", lambda *args: [])
    trial = trial_module.ToolTrial(tmp_path, [])
    requests = []
    assistant = {"role": "assistant", "content": "", "thinking": "Search the material.",
                 "tool_calls": [{"id": "call-1", "function": {
                     "name": "search_materials", "arguments": {"query": "centrality", "document_id": "book"}}}]}

    async def post(self, url, json):
        requests.append(copy.deepcopy(json))
        message = assistant if len(requests) == 1 else {
            "role": "assistant", "content": "Answer [S99]."}
        return httpx.Response(200, request=httpx.Request("POST", url),
                              json={"done": True, "done_reason": "stop", "message": message})

    async def execute(*args):
        return []

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    monkeypatch.setattr(trial, "execute", execute)
    result = asyncio.run(trial.turn("What is centrality?"))
    assert requests[1]["messages"][-2] == assistant
    assert requests[1]["messages"][-1]["tool_call_id"] == "call-1"
    assert result["unknown_citations"] == ["S99"]


def test_search_scope_and_unknown_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(trial_module, "library", lambda *args: [])
    trial = trial_module.ToolTrial(tmp_path, [])
    with pytest.raises(ValueError, match="outside selected scope"):
        asyncio.run(trial.execute("search_materials", {"query": "test", "document_id": "other"}))
    with pytest.raises(ValueError, match="Unknown tool"):
        asyncio.run(trial.execute("delete", {}))


def test_truncated_response_is_not_an_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(trial_module, "library", lambda *args: [])

    async def post(self, url, json):
        return httpx.Response(200, request=httpx.Request("POST", url),
                              json={"done": True, "done_reason": "length"})

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    with pytest.raises(ValueError, match="Incomplete"):
        asyncio.run(trial_module.ToolTrial(tmp_path, []).turn("Hello"))


def test_lexical_rescue_preserves_missing_hit(tmp_path, monkeypatch):
    chunks = [{"id": i, "text": f"passage {i}", "location": str(i)} for i in range(4)]
    monkeypatch.setattr(trial_module, "library", lambda *args: [({"id": "book", "name": "Book"}, chunks)])
    monkeypatch.setattr(trial_module, "candidates", lambda *args: [chunks[3]])

    async def retrieve(*args):
        return chunks[:3]

    monkeypatch.setattr(trial_module, "retrieve", retrieve)
    trial = trial_module.ToolTrial(tmp_path, ["book"], lexical_rescue=True)
    sources = asyncio.run(trial.execute("search_materials", {"document_id": "book", "query": "term"}))
    assert {s["chunk_id"] for s in sources} == {0, 1, 2, 3}


def test_bm25_query_is_data():
    from scripts.evaluate_bm25 import bm25_hits
    chunks = [{"id": 1, "text": "degree centrality counts friends"}]
    assert bm25_hits(chunks, "") == []
    assert bm25_hits(chunks, 'degree " OR centrality')[0]["id"] == 1
