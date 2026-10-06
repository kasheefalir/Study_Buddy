import asyncio
import json

import pytest

from app.agents.study_tools import review_materials, library
from app.agents.quiz import quiz_turn
from app.rag.library import write_json
from app.storage.conversation_store import ConversationStore


def material(root, identifier, name):
    write_json(root / (identifier + ".json"), {"id": identifier, "name": name, "status": "Ready"})
    write_json(root / identifier / "chunks.json", [
        {"id": 1, "text": "Recall is the proportion of actual positives identified correctly.", "location": "Slide 1"},
        {"id": 2, "text": "Regularization discourages excessive model complexity.", "location": "Slide 2"},
    ])


class Model:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.calls = []

    async def plan(self, messages):
        self.calls.append(messages)
        payload = json.loads(messages[-1]["content"])
        if "message" in payload:
            return json.dumps({"action": "answer", "format": payload["format"], "guidelines": "", "acknowledgement": ""})
        return json.dumps(next(self.answers))


def test_batches_are_independent_and_legacy_migrates(tmp_path):
    store = ConversationStore(tmp_path)
    first, second = store.create_id(), store.create_id()
    store.save(first, [], document_id="a" * 32, title="Statistics")
    store.save(second, [], document_ids=[], title="Biology")
    assert store.documents(first) == ["a" * 32]
    assert store.documents(second) == []
    store.save(first, [], memory="Review recall")
    assert store.documents(first) == ["a" * 32]
    assert len(store.list_sessions()) == 2


def test_review_tool_cannot_access_other_batches(tmp_path):
    allowed, other = "a" * 32, "b" * 32
    material(tmp_path, allowed, "Current course")
    material(tmp_path, other, "Other course")
    model = Model([{"tool": "review_materials", "query": "overview", "document_ids": [other],
                    "approach": "source_focused", "reasoning": "Review source"}])
    with pytest.raises(ValueError, match="unavailable material"):
        asyncio.run(review_materials(tmp_path, [allowed], "review", [], model))
    assert "Other course" not in str(model.calls)


def test_quiz_coverage_feedback_and_next_step(tmp_path):
    identifier = "a" * 32
    material(tmp_path, identifier, "Statistics")
    model = Model([
        {"count": 2, "focus": "", "format": "short_answer"},
        {"summary": "Recall measures sensitivity.", "chunk_ids": [1], "question": "How is recall measured?", "expected_answer": "True positives divided by actual positives"},
        {"verdict": "correct", "explanation": "Yes. Sensitivity and recall mean the same thing.", "correction": "Recall measures actual positives found.", "example": "8 of 10 gives 80%."},
        {"summary": "Regularization reduces overfitting.", "chunk_ids": [2], "question": "Why use regularization?", "expected_answer": "To reduce overfitting"},
        {"verdict": "incorrect", "explanation": "Regularization is not a measure of accuracy.", "correction": "It penalizes complexity to reduce overfitting.", "example": "Shrinking weights can prevent fitting noise."},
    ])
    text, state, _ = asyncio.run(quiz_turn(tmp_path, [identifier], "Quiz me with two questions", {}, model))
    assert "Question 1 of 2" in text and "divided" not in text
    text, state, _ = asyncio.run(quiz_turn(tmp_path, [identifier], "Sensitivity", state, model))
    assert text.startswith("**Correct**") and state["phase"] == "review"
    assert state["cursor"] == 0
    text, state, _ = asyncio.run(quiz_turn(tmp_path, [identifier], "next", state, model))
    assert "Question 2 of 2" in text
    text, state, _ = asyncio.run(quiz_turn(tmp_path, [identifier], "To measure accuracy", state, model))
    assert text.startswith("**Incorrect**") and "penalizes" in text
    text, state, _ = asyncio.run(quiz_turn(tmp_path, [identifier], "next", state, model))
    assert not state["active"] and "1 of 2 correct" in text
    text, state, sources = asyncio.run(quiz_turn(tmp_path, [identifier], "Review missed answers", state, model))
    assert "To measure accuracy" in text and "penalizes" in text and sources
    assert len(model.calls) == 7


def test_invalid_coverage_and_unready_files_fail_explicitly(tmp_path):
    identifier = "a" * 32
    material(tmp_path, identifier, "Stats")
    with pytest.raises(ValueError, match="valid study response"):
        asyncio.run(quiz_turn(tmp_path, [identifier], "quiz", {}, Model([
            {"count": 5, "focus": ""}, {"summary": "Fake", "question": "", "expected_answer": "Unknown source explanation"}])))
    write_json(tmp_path / (identifier + ".json"), {"id": identifier, "name": "Stats", "status": "Processing"})
    with pytest.raises(ValueError, match="not ready"):
        library(tmp_path, [identifier])


def test_consolidation_preserves_omitted_concepts(tmp_path):
    from app.agents.study_tools import coverage
    identifier = "e" * 32
    material(tmp_path, identifier, "Course")
    write_json(tmp_path / identifier / "chunks.json", [
        {"id": i, "text": f"Concept {i}", "location": f"Slide {i}"} for i in range(15)])
    answers = [{"topics": [{"title": f"Concept {i}", "chunk_ids": [i]} for i in range(start, start + 3)]}
               for start in range(0, 15, 3)]
    answers.append({"topics": [{"title": "Combined concept", "learning_goal": "Understand it", "topic_indices": [0, 1]}]})
    topics = asyncio.run(coverage(tmp_path, [identifier], Model(answers)))
    assert len(topics) == 14
    assert {i for topic in topics for ref in topic.get("source_refs", [topic]) for i in ref["chunk_ids"]} == set(range(15))


def test_docx_body_and_table_text_ingestion(tmp_path):
    import zipfile
    from app.rag.library import process
    path = tmp_path / "proposal.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Project proposal requirements</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Use a public dataset</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
    item = {"id": "c" * 32, "name": "Proposal", "filename": path.name, "kind": "docx"}
    result = process(tmp_path, item)
    assert result["status"] == "Ready"
    assert result["chunk_count"] == 2
    extracted = (tmp_path / item["id"] / "extracted.json").read_text()
    assert "public dataset" in extracted


def test_session_api_persists_batches_and_hides_answer_keys(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main, materials
    root = tmp_path / "documents"
    root.mkdir()
    identifier = "d" * 32
    material(root, identifier, "Course")
    store = ConversationStore(tmp_path / "conversations")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(materials, "root", root)
    client = TestClient(main.app)
    response = client.post("/api/conversations", json={"title": "Course A", "document_ids": [identifier]})
    assert response.status_code == 201
    session = response.json()["conversation_id"]
    store.save(session, [], quiz={"active": True, "expected_answer": "secret", "topics": [{"title": "Recall"}], "cursor": 0})
    detail = client.get("/api/conversations/" + session).json()
    assert detail["document_ids"] == [identifier]
    assert "expected_answer" not in detail["quiz"]
    assert detail["quiz"]["concept_count"] == 1
    other = client.post("/api/conversations", json={"title": "Course B"}).json()["conversation_id"]
    assert client.get("/api/conversations/" + other).json()["document_ids"] == []
    assert client.put("/api/conversations/" + session + "/materials", json={"document_ids": []}).status_code == 200
    assert store.quiz(session) == {}
    assert client.put("/api/conversations/" + other + "/materials", json={"document_ids": ["bad"]}).status_code == 404
