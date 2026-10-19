import asyncio
import json
import random

import pytest

from app.agents.local_study import workflows as w
from app.agents.local_study.runtime import LocalRuntime


class Client:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.messages = []

    async def structured_plan(self, messages, schema):
        self.messages.append(messages)
        return json.dumps(self.outputs.pop(0))


SOURCE = {"document_id": "opaque-file-id", "chunk_id": 4, "label": "S1", "name": "Slides",
          "text": "Holding other variables constant, fare increases by 7.5 cents per mile.", "location": "Slide 4"}


def test_partition_keeps_spans_and_does_not_free_rewrite():
    question = "Compare degree centrality and betweenness centrality according to this book."
    parts = w.partition(question, "comparison")
    assert parts == ["degree centrality", "betweenness centrality"]
    assert all(part in question for part in parts)
    question = "How much per mile and for Southwest, holding other things constant?"
    assert " and ".join(w.partition(question, "multipart")) == question
    assert not w.partition("Explain all of it", "advanced")


def test_metadata_validation_distinguishes_source_terms():
    assert not w.no_metadata("The laptop is M1", [SOURCE])
    assert not w.no_metadata("SOURCE_001 says so", [SOURCE])
    assert not w.no_metadata("opaque-file-id", [SOURCE])
    assert w.no_metadata("M1", [{**SOURCE, "text": "The laptop has an M1 chip."}])


def test_qa_has_no_model_selected_citations_and_rejects_unsupported():
    client = Client([
        {"status": "answer", "direct_answer": "7.5 cents more per mile.", "explanation": "Holding other variables constant."},
        {"supported": True, "answers_question": True, "reason": "Explicit coefficient"},
    ])
    result = asyncio.run(w.answer_part(client, "How much per mile?", "per mile", [SOURCE]))
    assert result["status"] == "answer"
    assert result["context_sources"] == [SOURCE]
    assert all("opaque-file-id" not in json.dumps(call) and '"S1"' not in json.dumps(call) for call in client.messages)
    client = Client([
        {"status": "answer", "direct_answer": "The laptop has 32 GB RAM.", "explanation": ""},
        {"supported": False, "answers_question": False, "reason": "Not in passage"},
    ])
    result = asyncio.run(w.answer_part(client, "Which laptop?", "laptop", [SOURCE]))
    assert result["status"] == "rejected"
    assert result["text"] == w.MISSING
    assert "32 GB" not in result["text"]


def test_followup_references_are_resolved_against_current_material(monkeypatch, tmp_path):
    client = Client([{"kind": "single"}, {"status": "not_found", "direct_answer": "", "explanation": ""}])
    books = [({"id": "book", "name": "Book"}, [{"id": 7, "text": "Current text", "location": "Page 1"}])]
    result = asyncio.run(w.qa(client, tmp_path, books, "Explain that more simply", {
        "previous_question": "What is a vector?", "sources": [{"document_id": "book", "chunk_id": 7, "text": "Stale"}]}))
    assert result["sections"][0]["context_sources"][0]["text"] == "Current text"
    assert "Stale" not in json.dumps(client.messages)
    assert "What is a vector?" in json.dumps(client.messages)


def test_retrieval_rejects_unknown_chunks(monkeypatch, tmp_path):
    async def retrieve(*args):
        return [{"id": 99, "text": "Invented"}]
    monkeypatch.setattr(w, "retrieve", retrieve)
    with pytest.raises(ValueError, match="unknown source"):
        asyncio.run(w.search(tmp_path, [({"id": "book"}, [{"id": 1, "text": "Known"}])], "Question"))


def test_guide_is_bounded_traced_and_deduplicated():
    chunks = [{"id": i, "text": "A vector is an ordered collection.", "location": f"Slide {i}"} for i in (1, 2)]
    note = {"items": [{"category": "Terms and definitions", "content": "A vector is an ordered collection."}]}
    check = {"supported": True, "answers_question": True, "reason": "Paraphrase allowed"}
    client = Client([note, check, note, check])
    guide = asyncio.run(w.study_guide(client, {"id": "book", "name": "Book"}, chunks))
    assert len(guide["categories"]["Terms and definitions"]) == 1
    assert len(guide["categories"]["Terms and definitions"][0]["context_sources"]) == 2
    assert guide["provided_chunk_ids"] == [1, 2]
    oversized = [{"id": 1, "text": "x" * 12000, "location": "Long section"}]
    batches = list(w.section_batches(oversized))
    assert all(sum(len(c["text"]) for c in batch) <= 4500 for _, batch in batches)
    assert sum(len(c["text"]) for _, batch in batches for c in batch) == 12000


QUIZ = {"question": "What is the fare increase per mile?", "choices": ["7.5 cents", "2 cents", "4 cents", "10 cents"],
        "correct_index": 0, "explanation": "Fare increases by 7.5 cents per mile, holding other variables constant."}


def test_quiz_verifier_is_blind_and_code_owns_provenance():
    client = Client([QUIZ, {"defensible_answers": [0], "clear_question": True, "reason": "Only one matches"},
                     {"supported": True, "answers_question": True, "reason": "Directly stated"}])
    result = asyncio.run(w.make_quiz(client, [SOURCE]))
    assert result["status"] == "accepted"
    assert result["question"]["choices"][result["question"]["correct_index"]] == "7.5 cents"
    assert result["source_chunk"] == 4
    blind = json.loads(client.messages[1][1]["content"])
    assert "correct_index" not in blind and "explanation" not in blind
    assert "opaque-file-id" not in json.dumps(client.messages)


def test_quiz_rejects_multiple_answers_and_bad_choices():
    client = Client([QUIZ, {"defensible_answers": [0, 2], "clear_question": False, "reason": "Ambiguous"},
                     {"supported": True, "answers_question": True, "reason": "Stated"}])
    assert asyncio.run(w.make_quiz(client, [SOURCE], attempts=1))["status"] == "discarded"
    for choices in (["A", "A", "B", "C"], ["A", "B", "C", "All of the above"]):
        with pytest.raises(ValueError):
            w.validate_quiz(w.Quiz(**{**QUIZ, "choices": choices}), [SOURCE])
    positions = {w.shuffle_quiz(w.Quiz(**QUIZ), random.Random(seed))["correct_index"] for seed in range(30)}
    assert positions == {0, 1, 2, 3}


def test_runtime_rejects_large_input_and_unapproved_models():
    with pytest.raises(ValueError, match="two small"):
        LocalRuntime("gpt-oss:20b")
    with pytest.raises(ValueError, match="context budget"):
        asyncio.run(LocalRuntime("llama3.2:3b").chat([
            {"role": "user", "content": "x" * 10001}]))


def test_runtime_unloads_other_generators_and_rejects_truncation(monkeypatch):
    from app.agents.local_study import runtime
    posts = []
    resident = [{"name": "llama3.2:3b"}, {"name": "phi4-mini:latest"},
                {"name": runtime.settings.embedding_model}]

    class Response:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    class HTTP:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url):
            return Response({"models": resident})

        async def post(self, url, json):
            posts.append((url, json))
            return Response({"done": True, "done_reason": "length", "message": {"content": "partial"}})

    monkeypatch.setattr(runtime.httpx, "AsyncClient", HTTP)
    client = LocalRuntime("llama3.2:3b")
    asyncio.run(client.exclusive())
    assert len(posts) == 1
    assert posts[0][1] == {"model": "phi4-mini:latest", "keep_alive": 0}
    with pytest.raises(RuntimeError, match="Another generation model"):
        asyncio.run(client.chat([{"role": "user", "content": "Hi"}]))
    resident[:] = [{"name": "llama3.2:3b"}]
    with pytest.raises(ValueError, match="output budget"):
        asyncio.run(client.chat([{"role": "user", "content": "Hi"}]))
    assert posts[-1][1]["options"] == {"num_ctx": 4096, "num_predict": 700, "temperature": 0.1}
