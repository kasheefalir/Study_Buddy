import asyncio
import json

import httpx

from app.agents.gpt import evidence_trial as evidence
from scripts.evaluate_gpt_evidence import EvidenceTrial


def test_quotes_and_citation_ranges_are_checked():
    sources = [{"label": "S1", "text": "Counts direct\nconnections."}]
    assert evidence.literal_issues('"Counts direct connections." [S1]', sources) == []
    assert evidence.literal_issues('“Counts all friends.” [S1]', sources)
    assert evidence.literal_issues("A claim [S1-S9]", sources)
    assert evidence.literal_issues("A claim [S99]", sources)
    assert evidence.literal_issues("A paraphrase [S1]", sources) == []


def test_independent_channels_keep_lexical_hit(tmp_path, monkeypatch):
    chunks = [{"id": i, "text": text} for i, text in enumerate(
        ["exact keyword", "near concept", "related concept", "keyword detail"])]
    folder = tmp_path / "book"
    folder.mkdir()
    (folder / "embeddings.json").write_text(json.dumps({
        "model": evidence.settings.embedding_model, "fingerprint": evidence.fingerprint(chunks),
        "vectors": [[0, 1], [1, 0], [.9, .1], [0, 1]]}))

    async def embed(*args):
        return [[1, 0]]

    monkeypatch.setattr(evidence, "embed", embed)
    hits, trace = asyncio.run(evidence.independent_candidates(tmp_path, {"id": "book"}, chunks, "keyword"))
    assert {c["id"] for c in hits} == {0, 1, 2, 3}
    assert trace["semantic_status"] == "used"
    (folder / "embeddings.json").unlink()
    hits, trace = asyncio.run(evidence.independent_candidates(tmp_path, {"id": "book"}, chunks, "keyword"))
    assert {c["id"] for c in hits} == {0, 3}
    assert trace["semantic_status"].startswith("fallback:")


def test_auditor_cannot_invent_supporting_excerpt(monkeypatch):
    async def post(self, url, json):
        audit = {"acceptable": True, "claims": [{"claim": "Made up", "supported": True,
                 "source_ids": ["S1"], "excerpts": ["Invented evidence"]}],
                 "missing_comparison_sides": [], "issues": []}
        return httpx.Response(200, request=httpx.Request("POST", url), json={"done": True,
            "done_reason": "stop", "message": {"content": __import__("json").dumps(audit)}})

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    result = asyncio.run(evidence.audit_answer("Question", "Made up [S1]", [{"label": "S1", "text": "Actual"}]))
    assert "Invalid audit excerpt: S1" in result["errors"]


def test_failed_repair_abstains_and_preserves_attempts(tmp_path, monkeypatch):
    from scripts import evaluate_gpt_tools, evaluate_gpt_evidence
    monkeypatch.setattr(evaluate_gpt_tools, "library", lambda *args: [])
    trial = EvidenceTrial(tmp_path, [])
    calls = []

    async def turn(question):
        calls.append(question)
        trial.messages.append({"role": "assistant", "content": "Unverified"})
        return {"answer": "Unverified", "sources": []}

    async def audit(*args):
        return {"errors": ["Unsupported"]}

    monkeypatch.setattr(trial, "turn", turn)
    monkeypatch.setattr(evaluate_gpt_evidence, "audit_answer", audit)
    result = asyncio.run(trial.checked_turn("Question"))
    assert result["forced_abstention"]
    assert len(calls) == len(result["attempts"]) == 2
    assert trial.messages[-1]["content"] == result["answer"]
