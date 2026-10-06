from fastapi.testclient import TestClient

from app import main, materials
from app.storage.conversation_store import ConversationStore
from app.rag.library import write_json


def test_source_titles_and_session_deletion(tmp_path, monkeypatch):
    root = tmp_path / "documents"
    identifier = "a" * 32
    write_json(root / (identifier + ".json"), {
        "id": identifier, "name": "https://example.org/r", "page_title": "Introduction to R", "kind": "url"})
    store = ConversationStore(tmp_path / "conversations")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(materials, "root", root)
    client = TestClient(main.app)
    cid = store.create_id()
    store.save(cid, [{"role": "user", "content": "whats this about"}], document_ids=[identifier])
    assert client.get("/api/conversations").json()[0]["title"] == "Introduction to R"
    assert client.get(f"/api/conversations/{cid}").json()["title"] == "Introduction to R"
    main.activity.active[cid] = "Thinking"
    try:
        assert client.delete(f"/api/conversations/{cid}").status_code == 409
    finally:
        main.activity.active.pop(cid)
    assert client.delete(f"/api/conversations/{cid}").status_code == 200
    assert (root / (identifier + ".json")).exists()
    assert client.get(f"/api/conversations/{cid}").status_code == 404
    assert client.delete(f"/api/conversations/{cid}").status_code == 404
    assert client.post("/api/chat", json={"conversation_id": cid, "message": "Hello"}).status_code == 404
    assert client.delete("/api/conversations/not-a-uuid").status_code == 400


def test_default_and_custom_titles(tmp_path):
    store = ConversationStore(tmp_path / "conversations")
    root = tmp_path / "documents"
    for identifier, name in [("a" * 32, "Data_Science.pdf"), ("b" * 32, "Lecture.pptx")]:
        write_json(root / (identifier + ".json"), {"name": name, "kind": "pdf"})
    payload = {"title": "Study session", "document_ids": ["a" * 32, "b" * 32]}
    assert store.session_title(payload, root) == "Data Science + 1 more"
    assert store.session_title({**payload, "title": "Exam revision"}, root) == "Exam revision"
    assert store.session_title({"messages": [{"role": "user", "content": "Hello"}]}, root) == "Study session"
