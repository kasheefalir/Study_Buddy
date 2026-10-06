import asyncio
import json

from app.rag import html_content, library, semantic
from app.rag.sources import chunks


HTML = b'''<html><head><title>Statistics notes</title></head><body><nav>Home Contact</nav>
<article><h1>Regularization</h1><p>Regularization reduces overfitting by penalizing model complexity. This allows the model to generalize to unseen examples.</p>
<h2>Ridge and Lasso</h2><p>Ridge penalizes squared weights. Lasso uses absolute weights and can eliminate coefficients. Both methods encourage simpler models.</p></article>
<aside>Office hours are Tuesday.</aside></body></html>'''


def test_clean_and_full_sections_are_preserved(tmp_path, monkeypatch):
    url = "https://example.org/lesson"
    monkeypatch.setattr(library, "fetch_page", lambda _: (HTML, {"content_type": "text/html", "final_url": url}))
    item = {"id": "a" * 32, "name": url, "url": url, "kind": "url"}
    result = library.process(tmp_path, item)
    assert result["status"] == "Ready"
    archive = tmp_path / item["id"]
    clean = json.loads((archive / "clean_content.json").read_text())
    full = json.loads((archive / "full_content.json").read_text())
    assert any(p["location"] == "Ridge and Lasso" for p in clean)
    assert "Office hours" not in str(clean) and "Office hours" in str(full)
    assert all(p["url"] == url for p in clean + full)
    indexed = json.loads((archive / "chunks.json").read_text())
    selected = asyncio.run(semantic.retrieve(tmp_path, item, indexed, "Office hours", 3))
    assert selected and selected[0]["variant"] == "full"
    library.process(tmp_path, item)
    assert list((archive / "versions").glob("*/full_content.json"))


def test_cleaner_failure_retains_full_text(monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("Malformed page")
    monkeypatch.setattr(html_content.trafilatura, "extract", fail)
    _, clean, full = html_content.extract_versions(HTML, "https://example.org")
    assert not clean and "Regularization" in str(full)


def test_semantic_match_without_shared_words_and_stale_index(tmp_path, monkeypatch):
    item = {"id": "b" * 32}
    indexed = [{"id": 1, "location": "Models", "text": "Regularization penalizes complexity.", "variant": "clean"},
               {"id": 2, "location": "Office", "text": "Meet Tuesday.", "variant": "full"}]
    library.write_json(tmp_path / item["id"] / "embeddings.json", {"model": semantic.settings.embedding_model,
        "fingerprint": semantic.fingerprint(indexed), "vectors": [[1., 0.], [0., 1.]]})
    async def fake_embed(texts, prefix):
        return [[1., 0.]]
    monkeypatch.setattr(semantic, "embed", fake_embed)
    result = asyncio.run(semantic.retrieve(tmp_path, item, indexed, "avoid memorizing training examples", 3))
    assert result[0]["id"] == 1
    indexed[0]["text"] = "Replaced content"
    assert not asyncio.run(semantic.retrieve(tmp_path, item, indexed, "avoid memorizing training examples", 3))


def test_html_chunk_boundaries_keep_words_and_sections():
    text = "concept " * 400
    result = chunks([{"location": "Section", "text": text, "variant": "clean", "url": "https://example.org"}])
    assert len(result) > 1
    assert all(len(c["text"]) <= 900 and set(c["text"].split()) == {"concept"} for c in result)
