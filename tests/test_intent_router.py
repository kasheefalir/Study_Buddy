import asyncio
import json

from app.agents.chat_agent import ChatAgent
from app.rag.library import write_json
from app.storage.conversation_store import ConversationStore


class RouterModel:
    def __init__(self, route):
        self.route = route
        self.calls = []

    async def structured_plan(self, messages, schema):
        self.calls.append(messages)
        payload = json.loads(messages[-1]["content"])
        if schema["title"] == "IntentRoute":
            return json.dumps({"route": self.route, "reasoning": "Latest message decides", "query": payload["latest_message"],
                               "pause_activity": self.route == "conversation"})
        if schema["title"] == "ToolChoice":
            return json.dumps({"approach": "source_focused", "reasoning": "Selected source", "tool": "search_materials",
                               "query": "R", "document_ids": ["a" * 32]})
        if schema["title"] == "RetrievalCheck":
            return json.dumps({"action": "answer", "gap": "", "query": "", "document_ids": ["a" * 32]})
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


def test_retrieval_router_keeps_source_workflow(tmp_path):
    identifier = source(tmp_path / "documents")
    model = RouterModel("retrieve")
    _, reply = asyncio.run(ChatAgent(model, ConversationStore(tmp_path / "conversations")).reply(
        "What does the selected source say about R?", materials_root=tmp_path / "documents", document_ids=[identifier]))
    assert reply == "Hello. What would you like to study?"
    assert any("session_materials" in str(call) for call in model.calls)
