import asyncio
import json

from app.agents.chat_agent import ChatAgent
from app.rag.library import write_json
from app.storage.conversation_store import ConversationStore
from app.agents import chat_agent


class RouterModel:
    def __init__(self, route):
        self.route = route
        self.calls = []

    async def structured_plan(self, messages, schema):
        self.calls.append(messages)
        if schema["title"] == "IntentRoute":
            payload = json.loads(messages[-1]["content"])
            return json.dumps({"route": self.route, "reasoning": "Latest message decides", "query": payload["latest_message"],
                               "pause_activity": self.route == "conversation"})
        if schema["title"] == "ToolChoice":
            return json.dumps({"approach": "source_focused", "reasoning": "Selected source", "tool": "search_materials",
                               "query": "R", "document_ids": ["a" * 32]})
        if schema["title"] == "RetrievalCheck":
            return json.dumps({"action": "answer", "gap": "", "query": "", "document_ids": ["a" * 32]})
        if schema["title"] == "GroundedAnswer":
            return json.dumps({"points": [{"evidence": [{"label": "S1"}],
                                           "explanation": "R is used for statistics."}]})
        if schema["title"] == "GroundingCheck":
            return json.dumps({"checks": {"0": {"supported": True}}})
        return json.dumps({"summary": "Source context", "question": "What is R?", "expected_answer": "A language for statistics."})

    async def chat(self, messages):
        self.calls.append(messages)
        return "Hello. What would you like to study?"


def source(root):
    identifier = "a" * 32
    write_json(root / (identifier + ".json"), {"id": identifier, "name": "R notes", "kind": "url", "status": "Ready"})
    write_json(root / identifier / "chunks.json", [{"id": 1, "text": "R is used for statistics.", "location": "Intro"}])
    return identifier


def test_greeting_bypasses_material_retrieval_and_pauses_old_activity(tmp_path):
    identifier = source(tmp_path / "documents")
    store = ConversationStore(tmp_path / "conversations")
    cid = store.create_id()
    store.save(cid, [{"role": "user", "content": "Quiz me on R"}], document_ids=[identifier],
               quiz={"active": True, "version": 2, "pending_question": "What is R?", "total": 5})
    model = RouterModel("conversation")
    asyncio.run(ChatAgent(model, store).reply("Hey Professor", cid, materials_root=tmp_path / "documents", document_ids=[identifier]))
    assert not any("session_materials" in str(call) for call in model.calls if call and call[0].get("role") == "system")
    assert store.quiz(cid)["active"] is False and store.quiz(cid)["paused"] is True
    payload = json.loads(model.calls[0][-1]["content"])
    assert "study_session" not in payload
    assert "conversation_memory" not in payload
    assert "saved_learning_notes" not in payload
    assert "This turn is conversational" in model.calls[-1][0]["content"]


def test_retrieval_router_keeps_source_workflow(tmp_path):
    identifier = source(tmp_path / "documents")
    model = RouterModel("retrieve")
    store = ConversationStore(tmp_path / "conversations")
    cid, reply = asyncio.run(ChatAgent(model, store).reply(
        "What does the selected source say about R?", materials_root=tmp_path / "documents", document_ids=[identifier]))
    assert reply == "R is used for statistics. [S1]"
    assert store.load(cid)[-1]["sources"][0]["label"] == "S1"
    assert any("session_materials" in str(call) for call in model.calls)


def test_missing_evidence_retries_once_without_unverified_writer(tmp_path, monkeypatch):
    identifier = source(tmp_path / "documents")
    attempts = []

    async def empty(*args, **kwargs):
        attempts.append(kwargs)
        kwargs["review_context"].update(approach="tutoring")
        return []

    monkeypatch.setattr(chat_agent, "review_materials", empty)
    model = RouterModel("retrieve")
    store = ConversationStore(tmp_path / "conversations")
    cid, reply = asyncio.run(ChatAgent(model, store).reply(
        "What does the book say?", materials_root=tmp_path / "documents", document_ids=[identifier]))
    assert reply == chat_agent.MISSING_EVIDENCE
    assert len(attempts) == 2 and "no passages" in attempts[1]["feedback"]
    assert len(model.calls) == 2  # Only intent passes, no unsupported answer generation.
    assert store.load(cid)[-1]["material_review"]["empty_evidence_retry"]["recovered"] is False


def test_empty_retrieval_recovers_then_conversation_can_interrupt(tmp_path, monkeypatch):
    identifier = source(tmp_path / "documents")
    attempts = []

    async def recover(*args, **kwargs):
        attempts.append(args[2])
        kwargs["review_context"].update(approach="source_focused")
        return [] if len(attempts) == 1 else [{"label": "S1", "text": "R is used for statistics.",
            "document_id": identifier, "location": "Intro", "name": "R notes", "chunk_id": 1}]

    monkeypatch.setattr(chat_agent, "review_materials", recover)
    model = RouterModel("retrieve")
    store = ConversationStore(tmp_path / "conversations")
    agent = ChatAgent(model, store)
    cid, reply = asyncio.run(agent.reply("What does the book say about R?",
        materials_root=tmp_path / "documents", document_ids=[identifier]))
    assert reply == "R is used for statistics. [S1]"
    check = json.loads(model.calls[-2][-1]["content"])
    assert check["resolved_request"] == "What does the book say about R?"
    model.route = "conversation"
    _, reply = asyncio.run(agent.reply("Thanks, let's take a break", cid,
        materials_root=tmp_path / "documents", document_ids=[identifier]))
    assert len(attempts) == 2
    assert store.load(cid)[-1]["sources"] == []
    assert reply == "Hello. What would you like to study?"
    payload = json.loads(model.calls[-2][-1]["content"])
    assert payload["last_material_request"] == "What does the book say about R?"


def test_retrieval_decision_cannot_erase_selection_with_empty_ids(tmp_path):
    identifier = source(tmp_path / "documents")

    class EmptySelectionModel(RouterModel):
        async def structured_plan(self, messages, schema):
            if schema["title"] == "RetrievalPlan":
                return json.dumps({"reasoning": "Read selected book",
                    "query": "R statistics", "document_ids": []})
            return await super().structured_plan(messages, schema)

    store = ConversationStore(tmp_path / "conversations")
    cid, reply = asyncio.run(ChatAgent(EmptySelectionModel("retrieve"), store).reply(
        "What does the book say about R?", materials_root=tmp_path / "documents", document_ids=[identifier]))
    assert reply == "R is used for statistics. [S1]"
    assert store.documents(cid) == [identifier]


def test_model_can_reuse_verified_evidence_without_retrieval(tmp_path):
    identifier = source(tmp_path / "documents")

    class ReuseModel(RouterModel):
        async def structured_plan(self, messages, schema):
            if schema["title"] == "RetrievalPlan":
                payload = json.loads(messages[-1]["content"])
                assert payload["previous_evidence"][0]["text"] == "R is used for statistics."
                return json.dumps({"reasoning": "Rephrase existing evidence",
                    "query": "Explain R statistics simply", "document_ids": [identifier],
                    "reuse_evidence": True})
            return await super().structured_plan(messages, schema)

    store = ConversationStore(tmp_path / "conversations")
    cid = store.create_id()
    store.save(cid, [{"role": "assistant", "content": "R is used for statistics.",
        "material_review": {"resolved_request": "What is R?"},
        "sources": [{"document_id": identifier, "chunk_id": 1, "location": "Intro",
                     "label": "S1", "name": "R notes", "text": "R is used for statistics."}]}], document_ids=[identifier])
    model = ReuseModel("retrieve")
    _, reply = asyncio.run(ChatAgent(model, store).reply("Explain that simply", cid,
        materials_root=tmp_path / "documents", document_ids=[identifier]))
    assert reply == "R is used for statistics. [S1]"
    assert store.load(cid)[-1]["material_review"]["evidence_reused"] is True
    assert not any("session_materials" in str(call) for call in model.calls)
