import asyncio
import json
from dataclasses import replace

from app.agents import context_budget
from app.agents.retrieval_context import document_view, coverage_report
from app.agents.study_tools import review_materials
from app.agents.quiz import public_question, QuizRequest
from app.rag.overview import fingerprint
from app.rag.library import write_json


def material(root, count=3):
    item = {"id": "a" * 32, "name": "R introduction", "status": "Ready"}
    chunks = [{"id": i, "location": f"Section {i}", "text": f"Topic {i}: R uses vectors. " * 20} for i in range(count)]
    write_json(root / (item["id"] + ".json"), item)
    write_json(root / item["id"] / "chunks.json", chunks)
    return item, chunks


def test_short_document_full_text_and_original_citations(tmp_path):
    item, chunks = material(tmp_path)
    sources, strategy = document_view(tmp_path, item, chunks, 2500)
    assert strategy == "full_text"
    assert [s["chunk_id"] for s in sources] == [c["id"] for c in chunks]
    assert coverage_report([(item, chunks)], sources)[0]["complete"]


def test_complete_tree_frontier_not_chapter_sampling(tmp_path):
    item, chunks = material(tmp_path, 60)
    nodes = {"root": {"heading": "Book", "summary": "Two main topics", "concepts": [],
                      "children": ["a", "b"], "chunk_ids": list(range(60))},
             "a": {"heading": "First half", "summary": "Vectors", "concepts": [], "chunk_ids": list(range(30))},
             "b": {"heading": "Second half", "summary": "Functions", "concepts": [], "chunk_ids": list(range(30, 60))}}
    write_json(tmp_path / item["id"] / "overview.json", {
        "status": "ready", "fingerprint": fingerprint(chunks), "root": "root", "nodes": nodes})
    sources, strategy = document_view(tmp_path, item, chunks, 900)
    assert strategy == "complete_hierarchy"
    assert len(sources) == 2
    report = coverage_report([(item, chunks)], sources)[0]
    assert report["complete"] and report["original_passages"] == 0
    assert report["represented_passages"] == 60


def test_partial_cache_never_claims_full_coverage(tmp_path):
    item, chunks = material(tmp_path, 60)
    sources, strategy = document_view(tmp_path, item, chunks, 700)
    assert strategy == "partial_text"
    assert not coverage_report([(item, chunks)], sources)[0]["complete"]


def test_one_model_directed_recovery_and_usage_bounded(tmp_path):
    item, chunks = material(tmp_path)
    class Model:
        calls = []
        async def structured_plan(self, messages, schema):
            self.calls.append(messages)
            if schema["title"] == "ToolChoice":
                return json.dumps({"approach": "source_focused", "reasoning": "Use selected source", "tool": "search_materials",
                                   "query": "vectors", "document_ids": [item["id"]]})
            return json.dumps({"action": "review_materials", "gap": "Need the whole source", "query": "overview", "document_ids": [item["id"]]})
    model, details = Model(), {}
    result = asyncio.run(review_materials(tmp_path, [item["id"]], "Explain the main ideas", [], model, review_context=details))
    assert len(model.calls) == 2
    assert details["retrieval_limit_reached"]
    assert details["coverage"][0]["complete"]
    assert all(context_budget.estimate(m) <= context_budget.input_limit() for m in model.calls)
    assert len({s["label"] for s in result}) == len(result)


def test_packed_limits_and_no_stale_coverage_at_4096(monkeypatch):
    monkeypatch.setattr(context_budget, "settings", replace(context_budget.settings, context_window=4096, response_tokens=512))
    sources = [{"text": "Reference fact. " * 100, "label": str(i)} for i in range(20)]
    messages, included, report = context_budget.pack("Tutor", "Summarize", [],
        {"material_review": {"coverage": [{"complete": True}]}}, sources, 16)
    assert report["estimated_input_tokens"] <= report["input_budget"]
    assert len(included) < len(sources)
    assert '"complete": true' not in str(messages)
    assert "omitted_for_budget" in str(messages)


def test_public_choices_hide_key_until_graded():
    assert QuizRequest().count == 10
    assert QuizRequest().format == "multiple_choice"
    q = {"question_id": "q1", "pending_question": "Which?", "options": ["A", "B", "C", "D"],
         "answer_key": "C", "correct_index": 2, "cursor": 0, "total": 5, "results": []}
    public = public_question(q)
    assert "answer_key" not in public and "correct_index" not in public
    q["results"] = [{"question_id": "q1", "selected_index": 0, "correct_index": 2, "verdict": "incorrect"}]
    public = public_question(q)
    assert public["answered"] and public["selected_index"] == 0 and public["correct_index"] == 2
