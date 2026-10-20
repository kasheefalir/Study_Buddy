from fastapi.testclient import TestClient
import asyncio

from app import main
from app.storage.conversation_store import ConversationStore


def test_preload_success_and_failure_release_lock(monkeypatch):
    monkeypatch.setattr(main, "model_load_lock", asyncio.Lock())
    original = main.llm.model
    seen = []

    async def health(self):
        return {"connected": True, "model_available": True}

    async def preload(self):
        assert main.model_load_lock.locked()
        seen.append(self.model)
        if self.model == "llama3.2:3b":
            raise main.OllamaError("Loading failed")

    monkeypatch.setattr(main.OllamaClient, "health", health)
    monkeypatch.setattr(main.OllamaClient, "preload", preload)
    client = TestClient(main.app)
    result = client.post("/api/models/load", json={"model": "phi4-mini:latest"})
    assert result.json() == {"model": "phi4-mini:latest", "loaded": True}
    assert not main.model_load_lock.locked()
    assert client.post("/api/models/load", json={"model": "llama3.2:3b"}).status_code == 503
    assert not main.model_load_lock.locked()
    assert client.post("/api/models/load", json={"model": "invalid model"}).status_code == 422
    assert main.llm.model == original
    assert seen == ["phi4-mini:latest", "llama3.2:3b"]


def test_preload_and_chat_exclude_each_other(monkeypatch):
    lock = asyncio.Lock()
    monkeypatch.setattr(main, "model_load_lock", lock)
    client = TestClient(main.app)
    asyncio.run(lock.acquire())
    try:
        assert client.post("/api/models/load", json={"model": "phi4-mini:latest"}).status_code == 409
        assert client.post("/api/chat", json={"message": "hello"}).status_code == 409
    finally:
        lock.release()
    with main.activity.track("test-switch-busy"):
        assert client.post("/api/models/load", json={"model": "phi4-mini:latest"}).status_code == 409


def test_preload_missing_model(monkeypatch):
    async def health(self):
        return {"connected": True, "model_available": False}

    monkeypatch.setattr(main.OllamaClient, "health", health)
    assert TestClient(main.app).post("/api/models/load", json={"model": "phi4-mini:latest"}).status_code == 503
    assert not main.model_load_lock.locked()


def test_next_action_rejects_stale_question_and_forwards_current(tmp_path, monkeypatch):
    store = ConversationStore(tmp_path / "conversations")
    monkeypatch.setattr(main, "store", store)
    cid = store.create_id()
    store.save(cid, [], quiz={"question_id": "q1", "phase": "review"})

    class Agent:
        async def reply(self, message, conversation_id, *args, **kwargs):
            assert kwargs["next_question_id"] == "q1"
            store.save(conversation_id, [{"role": "assistant", "content": "Question 2"}])
            return conversation_id, "Question 2"

    monkeypatch.setattr(main, "agent", Agent())
    client = TestClient(main.app)
    payload = {"conversation_id": cid, "message": "Next question", "next_question_id": "old"}
    assert client.post("/api/chat", json=payload).status_code == 409
    assert store.load(cid) == []
    payload["next_question_id"] = "q1"
    assert client.post("/api/chat", json=payload).status_code == 200


def test_switch_models_keeps_history_and_shared_client(tmp_path, monkeypatch):
    store = ConversationStore(tmp_path / "conversations")
    monkeypatch.setattr(main, "store", store)
    original = main.llm.model
    seen = []

    async def health(self):
        return {"connected": True, "model_available": True, "model": self.model}

    async def reply(self, message, cid, *args, **kwargs):
        seen.append(self.llm.model)
        messages = self.conversations.load(cid)
        messages.extend([{"role": "user", "content": message},
                         {"role": "assistant", "content": self.llm.model}])
        self.conversations.save(cid, messages)
        return cid, self.llm.model

    monkeypatch.setattr(main.OllamaClient, "health", health)
    monkeypatch.setattr(main.ChatAgent, "reply", reply)
    from app.agents.deepseek.agent import DeepSeekAgent
    monkeypatch.setattr(DeepSeekAgent, "reply", reply)
    client = TestClient(main.app)
    cid = client.post("/api/conversations", json={}).json()["conversation_id"]
    for model in ("phi4-mini:latest", "llama3.2:3b", "gpt-oss:20b", "gemma4:31b-cloud"):
        result = client.post("/api/chat", json={"message": "Hello", "conversation_id": cid, "model": model})
        assert result.status_code == 200
        assert result.json()["message"] == model
        assert client.get("/api/health", params={"model": model}).json()["ollama"]["model"] == model
    assert seen == ["phi4-mini:latest", "llama3.2:3b", "gpt-oss:20b", "gemma4:31b-cloud"]
    assert len(store.load(cid)) == 8
    assert main.llm.model == original


def test_invalid_or_unavailable_model_does_not_start_chat(tmp_path, monkeypatch):
    store = ConversationStore(tmp_path / "conversations")
    monkeypatch.setattr(main, "store", store)

    async def unavailable(self):
        return {"connected": True, "model_available": False}

    monkeypatch.setattr(main.OllamaClient, "health", unavailable)
    client = TestClient(main.app)
    cid = client.post("/api/conversations", json={}).json()["conversation_id"]
    assert client.post("/api/chat", json={"message": "Hello", "model": "unknown"}).status_code == 503
    assert client.get("/api/health", params={"model": "invalid model"}).status_code == 422
    assert client.post("/api/chat", json={"message": "Hello", "conversation_id": cid,
                                         "model": "phi4-mini:latest"}).status_code == 503
    assert store.load(cid) == []
    assert cid not in main.activity.active


def test_omitted_model_uses_existing_agent(tmp_path, monkeypatch):
    store = ConversationStore(tmp_path / "conversations")
    monkeypatch.setattr(main, "store", store)

    class DefaultAgent:
        async def reply(self, message, cid, *args, **kwargs):
            store.save(cid, [{"role": "assistant", "content": "default"}])
            return cid, "default"

    monkeypatch.setattr(main, "agent", DefaultAgent())
    result = TestClient(main.app).post("/api/chat", json={"message": "Hello"})
    assert result.status_code == 200
    assert result.json()["message"] == "default"


def test_discovered_model_is_selectable(monkeypatch):
    async def health(self):
        return {"connected": True, "model_available": True}

    async def preload(self):
        assert self.model == "new-model:4b"

    monkeypatch.setattr(main.OllamaClient, "health", health)
    monkeypatch.setattr(main.OllamaClient, "preload", preload)
    client = TestClient(main.app)
    assert client.post("/api/models/load", json={"model": "new-model:4b"}).status_code == 200


def test_ui_assets_revalidate_after_updates():
    client = TestClient(main.app)
    for path in ("/", "/static/app.js?v=cloud-status-36"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"
    assert "app.js?v=cloud-status-36" in client.get("/").text


def test_cloud_can_be_loaded_without_sending_conversation(monkeypatch):
    async def health(self):
        return {"connected": True, "model_available": True}

    async def preload(self):
        assert self.model == "gemma4:31b-cloud"

    monkeypatch.setattr(main.OllamaClient, "health", health)
    monkeypatch.setattr(main.OllamaClient, "preload", preload)
    result = TestClient(main.app).post("/api/models/load", json={"model": "gemma4:31b-cloud"})
    assert result.status_code == 200
