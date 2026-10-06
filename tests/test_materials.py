from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import materials


def test_local_material_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(materials, "root", tmp_path)
    app = FastAPI()
    app.include_router(materials.router)
    client = TestClient(app)
    upload = client.post("/api/materials/upload?name=lesson.txt", content=b"Class notes")
    assert upload.status_code == 201
    item = upload.json()
    assert client.get("/api/materials").json() == [{**item, "importing": False, "import_stage": "stored", "overview": {"status": "not_started", "completed": 0, "total": 0, "error": ""}}]
    assert client.get(f"/api/materials/{item['id']}/download").content == b"Class notes"
    assert client.delete(f"/api/materials/{item['id']}").status_code == 204
    assert client.get("/api/materials").json() == []
    assert list(tmp_path.iterdir()) == []


def test_rejects_empty_files_and_unsafe_links(tmp_path, monkeypatch):
    monkeypatch.setattr(materials, "root", tmp_path)
    app = FastAPI()
    app.include_router(materials.router)
    client = TestClient(app)
    assert client.post("/api/materials/upload?name=empty.pdf", content=b"").status_code == 400
    assert client.post("/api/materials/upload?name=script.html", content=b"x").status_code == 400
    assert client.post("/api/materials/url", json={"url": "javascript:alert(1)"}).status_code == 400
    saved = client.post("/api/materials/url", json={"url": "https://example.com/lesson"})
    assert saved.status_code == 201
    assert saved.json()["status"] == "Link saved · not imported"


def test_text_materials_are_semantically_indexed_after_extraction(tmp_path, monkeypatch):
    monkeypatch.setattr(materials, "root", tmp_path)
    indexed = []

    async def prepare_index(root, item):
        indexed.append(item["kind"])
        item["semantic_status"] = "Ready"
        return item

    async def prepare_facts(root, item, llm):
        return item

    monkeypatch.setattr(materials, "prepare_index", prepare_index)
    monkeypatch.setattr(materials, "prepare_facts", prepare_facts)
    monkeypatch.setattr(materials.overview, "start", lambda *args: None)
    app = FastAPI()
    app.include_router(materials.router)
    client = TestClient(app)
    item = client.post("/api/materials/upload?name=lesson.txt", content=b"Vectors hold related values.").json()
    result = client.post(f"/api/materials/{item['id']}/process")
    assert result.status_code == 200
    assert indexed == ["txt"]
    assert result.json()["semantic_status"] == "Ready"
