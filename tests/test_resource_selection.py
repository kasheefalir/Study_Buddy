import asyncio
import json

import app.agents.study_tools as study_tools

from app.agents.chat_agent import ChatAgent
from app.agents.study_tools import review_materials
from app.agents.study_tools import coherent_passages
from app.rag.library import write_json
from app.rag.overview import fingerprint
from app.storage.conversation_store import ConversationStore


def resources(root):
    for identifier, name, kind in [("a" * 32, "Introduction to R", "url"),
                                    ("b" * 32, "Data Science book", "pdf")]:
        write_json(root / (identifier + ".json"), {
            "id": identifier, "name": name, "kind": kind, "status": "Ready",
            "url": "https://example.org/r" if kind == "url" else ""})
        write_json(root / identifier / "chunks.json", [
            {"id": 1, "text": name + ": scripts make analysis reproducible.", "location": "Introduction"}])
    return ["a" * 32, "b" * 32]


class Model:
    def __init__(self, ids, approach="source_focused"):
        self.ids, self.approach, self.calls = ids, approach, []

    async def plan(self, messages):
        self.calls.append(messages)
        instruction = messages[0]["content"]
        if '"title": "IntentRoute"' in instruction:
            return json.dumps({"route": "retrieve", "query": "R overview", "reasoning": "Use selected source"})
        if '"title": "RetrievalPlan"' in instruction:
            return json.dumps({"query": "R overview", "document_ids": self.ids, "reasoning": "Use selected source"})
        return json.dumps({"tool": "review_materials", "query": "R overview",
                           "document_ids": self.ids, "approach": self.approach,
                           "reasoning": "Use the requested website."})

    async def chat(self, messages):
        self.calls.append(messages)
        return "This is a model-written explanation."


def test_outline_navigation_is_scoped_to_tested_large_models(tmp_path):
    ids = resources(tmp_path)[:1]
    write_json(tmp_path / ids[0] / "chunks.json", [
        {"id": i, "chapter": "Logistic Regression" if i == 19 else f"Chapter {i}",
         "text": "Source passage", "location": f"Page {i}"} for i in range(20)])
    for name in ("gpt-oss:20b", "gemma4:31b-cloud", "llama3.2:3b", "phi4-mini:latest"):
        model = Model(ids)
        model.model = name
        asyncio.run(review_materials(tmp_path, ids, "Explain logistic regression", [], model))
        card = json.loads(model.calls[0][-1]["content"])["session_materials"][0]
        if name in {"gpt-oss:20b", "gemma4:31b-cloud"}:
            assert card["sections"] == ["Logistic Regression"]
            assert card["source_outline"]["total_sections"] == 20
        else:
            assert "source_outline" not in card
            assert card["sections"] == [f"Chapter {i}" for i in range(8)]


def test_model_selects_website_before_retrieval(tmp_path):
    ids = resources(tmp_path)
    model, context = Model(ids[:1]), {}
    sources = asyncio.run(review_materials(tmp_path, ids, "Overview from the website", [], model,
                                          review_context=context))
    assert {s["document_id"] for s in sources} == {ids[0]}
    inventory = json.loads(model.calls[0][-1]["content"])["session_materials"]
    assert [m["kind"] for m in inventory] == ["url", "pdf"]
    assert inventory[0]["url"] == "https://example.org/r"
    assert context["selected_document_ids"] == ids[:1]


def test_single_active_selection_is_explicit_to_planner_and_writer(tmp_path):
    ids = resources(tmp_path)[:1]
    model, context = Model(ids), {}
    sources = asyncio.run(review_materials(tmp_path, ids, "Summarize the selected study material.", [], model,
                                          overview=True, review_context=context))
    payload = json.loads(model.calls[0][-1]["content"])
    assert payload["active_selection"]["count"] == 1
    assert payload["active_selection"]["document_ids"] == ids
    assert "without asking which one" in model.calls[0][0]["content"]
    assert context["active_selection_count"] == 1
    assert sources


def test_inventory_exposes_semantic_readiness_and_material_overview(tmp_path):
    ids = resources(tmp_path)[:1]
    item_path = tmp_path / (ids[0] + ".json")
    item = json.loads(item_path.read_text())
    item["semantic_status"] = "Ready"
    write_json(item_path, item)
    chunks = json.loads((tmp_path / ids[0] / "chunks.json").read_text())
    write_json(tmp_path / ids[0] / "overview.json", {
        "status": "ready", "fingerprint": fingerprint(chunks), "root": "book",
        "nodes": {"book": {"summary": "R supports statistical computing.",
                             "concepts": ["Vectors", "Functions"]}}})
    model = Model(ids)
    asyncio.run(review_materials(tmp_path, ids, "What are vectors?", [], model))
    inventory = json.loads(model.calls[0][-1]["content"])["session_materials"]
    assert inventory[0]["semantic_search"] == "Ready"
    assert inventory[0]["material_overview"]["concepts"] == ["Vectors", "Functions"]


def test_specific_text_question_uses_semantic_retrieval(tmp_path, monkeypatch):
    ids = resources(tmp_path)[:1]
    item_path = tmp_path / (ids[0] + ".json")
    item = json.loads(item_path.read_text())
    item["kind"] = "txt"
    write_json(item_path, item)
    calls = []

    async def retrieve(root, material, chunks, query, limit):
        calls.append((material["kind"], query, limit))
        return chunks

    monkeypatch.setattr(study_tools, "retrieve", retrieve)

    class SearchModel(Model):
        async def plan(self, messages):
            self.calls.append(messages)
            return json.dumps({"tool": "search_materials", "query": "reproducible analysis",
                               "document_ids": ids, "approach": "source_focused",
                               "reasoning": "Read the selected note."})

    sources = asyncio.run(review_materials(tmp_path, ids, "Why use scripts?", [], SearchModel(ids)))
    assert sources and calls == [("txt", "reproducible analysis", 3)]


def test_model_can_choose_multiple_sources_or_clarification(tmp_path):
    ids = resources(tmp_path)
    sources = asyncio.run(review_materials(tmp_path, ids, "Compare both", [], Model(ids, "tutoring")))
    assert {s["document_id"] for s in sources} == set(ids)
    context = {}
    sources = asyncio.run(review_materials(tmp_path, ids, "Which source?", [], Model([], "clarify"),
                                          overview=True, review_context=context))
    assert sources == []
    assert context["approach"] == "clarify"


def test_writer_gets_inventory_selection_and_persisted_followup_context(tmp_path):
    root = tmp_path / "documents"
    ids = resources(root)
    store = ConversationStore(tmp_path / "conversations")
    model = Model(ids[:1])
    agent = ChatAgent(model, store)
    session, answer = asyncio.run(agent.reply("Overview from the website", materials_root=root, document_ids=ids))
    assert answer == "This is a model-written explanation."
    writer = str(model.calls[-1])
    assert "available_materials" in writer and "source_focused" in writer
    assert store.load(session)[-1]["material_review"]["selected_document_ids"] == ids[:1]
    asyncio.run(agent.reply("Explain that simply", session, materials_root=root, document_ids=ids))
    planner = json.loads(model.calls[-2][-1]["content"])
    assert planner["recent_messages"][-1]["previous_source_ids"] == ids[:1]
    assert store.documents(session) == ids


def test_source_draft_preserves_intent_without_repeating_old_claims(tmp_path):
    ids = resources(tmp_path / "documents")
    store = ConversationStore(tmp_path / "conversations")
    cid = store.create_id()
    store.save(cid, [{"role": "user", "content": "Use beginner-friendly language"},
                     {"role": "assistant", "content": "Unsupported claim about neural networks"}],
               summary={"text": "Old unverified claim", "through": 0}, memory="Review indexing")
    model = Model(ids[:1])
    asyncio.run(ChatAgent(model, store).reply("Explain that from the website", cid,
                materials_root=tmp_path / "documents", document_ids=ids))
    assert "Unsupported claim" in str(model.calls[0])
    assert "Review indexing" not in str(model.calls[0])
    assert "Unsupported claim" not in str(model.calls[-1])
    assert "Old unverified claim" not in str(model.calls[-1])
    assert "beginner-friendly" in str(model.calls[-1])
    assert "resolved_request" in str(model.calls[-1])
    assert store.load(cid)[1]["content"] == "Unsupported claim about neural networks"


def test_coherent_retrieval_keeps_neighbors_and_citations():
    chunks = [{"id": i, "text": str(i), "location": "Functions" if i < 4 else "Frames"}
              for i in range(6)]
    assert [c["id"] for c in coherent_passages(chunks, 4, [chunks[2]])] == [1, 2, 3]
    assert [c["id"] for c in coherent_passages(chunks, 4)] == [0, 1, 4, 5]
    assert coherent_passages([], 12) == []


def test_neighbors_cannot_displace_primary_hits():
    chunks = [{"id": i, "text": str(i), "location": str(i // 3)} for i in range(9)]
    hits = [chunks[1], chunks[4], chunks[7]]
    result = coherent_passages(chunks, 4, hits)
    assert {1, 4, 7} <= {c["id"] for c in result}
    assert len(result) == 4
    assert [c["id"] for c in coherent_passages(chunks, 2, hits)] == [1, 4]
    assert coherent_passages(chunks, 0, hits) == []
    assert len(coherent_passages(chunks, 3, [chunks[1], chunks[1]])) == 3


def test_large_summary_uses_cached_hierarchy_not_vector_search(tmp_path, monkeypatch):
    ids = resources(tmp_path)[:1]
    chunks = [{"id": i, "text": ("Section %s. " % i) * 300,
               "location": "Page " + str(i + 1)} for i in range(30)]
    write_json(tmp_path / ids[0] / "chunks.json", chunks)
    write_json(tmp_path / ids[0] / "overview.json", {
        "status": "ready", "fingerprint": fingerprint(chunks), "root": "book",
        "nodes": {"book": {"heading": "Book overview", "summary": "An overview of all sections.",
                             "concepts": ["Reproducibility"], "chunk_ids": list(range(30))}}})

    async def forbidden(*args, **kwargs):
        raise AssertionError("Whole-material summaries must not run top-k retrieval")

    monkeypatch.setattr(study_tools, "retrieve", forbidden)

    class SearchPlanner(Model):
        async def structured_plan(self, messages, schema):
            self.calls.append(messages)
            assert len(self.calls) == 1, "No redundant sufficiency call for a summary view"
            return json.dumps({"tool": "search_materials", "query": "main ideas",
                               "document_ids": ids, "approach": "source_focused",
                               "reasoning": "Summarize the material."})

    model, context = SearchPlanner(ids), {}
    sources = asyncio.run(review_materials(tmp_path, ids, "Summarize this material", [], model,
                                          overview=True, review_context=context))
    assert sources[0]["variant"] == "generated_summary"
    assert context["coverage"][0]["complete"] is True
    assert context["coverage"][0]["represented_passages"] == 30
    assert len(model.calls) == 1


def test_large_uncached_view_never_claims_complete_coverage(tmp_path):
    from app.agents.retrieval_context import document_view, coverage_report
    item = {"id": "a" * 32, "name": "Large book"}
    chunks = [{"id": i, "text": "Study material. " * 80, "location": str(i)} for i in range(50)]
    sources, strategy = document_view(tmp_path, item, chunks, 800)
    assert strategy == "partial_text"
    assert not coverage_report([(item, chunks)], sources)[0]["complete"]


def test_optional_sufficiency_format_error_keeps_retrieved_passages(tmp_path):
    ids = resources(tmp_path)[:1]
    class BadCheck(Model):
        async def structured_plan(self, messages, schema):
            if schema["title"] == "RetrievalCheck":
                assert "Keep gap under 200 characters" in messages[0]["content"]
                assert "do not require an entire chapter" in messages[0]["content"]
                return "not JSON"
            return await self.plan(messages)
    context = {}
    sources = asyncio.run(review_materials(tmp_path, ids, "Explain scripts", [], BadCheck(ids),
                                          review_context=context))
    assert sources
    assert "retained initial evidence" in context["retrieval_check_error"]
