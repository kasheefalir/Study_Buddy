"""Local persisted vectors plus keyword ranking; no external embedding service."""
import hashlib
import json
import math

import httpx

from app.config import settings
from app.rag.library import candidates, tokens, write_json


def fingerprint(chunks):
    return hashlib.sha256(json.dumps(chunks, sort_keys=True).encode()).hexdigest()


async def embed(texts, prefix):
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(settings.ollama_url + "/api/embed", json={
            "model": settings.embedding_model, "input": [prefix + text for text in texts], "truncate": False})
        response.raise_for_status()
        vectors = response.json()["embeddings"]
    if len(vectors) != len(texts) or not vectors or not vectors[0]:
        raise ValueError("Invalid embedding response")
    if any(len(v) != len(vectors[0]) or any(not math.isfinite(x) for x in v) for v in vectors):
        raise ValueError("Invalid embedding dimensions")
    return vectors


async def prepare_index(root, item):
    path = root / item["id"]
    indexed = json.loads((path / "chunks.json").read_text())
    item.update(import_stage="embedding", semantic_status="Preparing", import_completed=0, import_total=len(indexed))
    write_json(root / (item["id"] + ".json"), item)
    try:
        async with httpx.AsyncClient(timeout=900) as client:
            tags = await client.get(settings.ollama_url + "/api/tags")
            tags.raise_for_status()
            names = {m["name"] for m in tags.json()["models"]}
            if settings.embedding_model not in names and settings.embedding_model + ":latest" not in names:
                result = await client.post(settings.ollama_url + "/api/pull", json={"model": settings.embedding_model, "stream": False})
                result.raise_for_status()
                if result.json().get("error"):
                    raise ValueError("Embedding model download failed")
        vectors = []
        for start in range(0, len(indexed), 16):
            vectors.extend(await embed([c["location"] + "\n" + c["text"] for c in indexed[start:start + 16]], "search_document: "))
            item["import_completed"] = len(vectors)
            write_json(root / (item["id"] + ".json"), item)
        write_json(path / "embeddings.json", {"model": settings.embedding_model, "fingerprint": fingerprint(indexed), "vectors": vectors})
        item["semantic_status"] = "Ready"
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        item["semantic_status"] = "Unavailable"
        item["warning"] = (item.get("warning", "") + " Semantic search unavailable; keyword search remains available.").strip()
    item["import_stage"] = "ready"
    write_json(root / (item["id"] + ".json"), item)
    return item


async def retrieve(root, item, chunks, query, limit):
    lexical = [c for c in candidates(chunks, query, limit=len(chunks)) if set(tokens(query)) & set(tokens(c["text"]))]
    rankings = [lexical]
    path = root / item["id"] / "embeddings.json"
    if path.exists():
        try:
            index = json.loads(path.read_text())
            if index["model"] == settings.embedding_model and index["fingerprint"] == fingerprint(chunks):
                vector = (await embed([query], "search_query: "))[0]
                def cosine(v):
                    if len(v) != len(vector):
                        raise ValueError("Embedding dimensions changed")
                    return sum(a*b for a,b in zip(v, vector)) / max(1e-12, math.sqrt(sum(x*x for x in v) * sum(x*x for x in vector)))
                if len(index["vectors"]) != len(chunks):
                    raise ValueError("Incomplete index")
                ordered = sorted(zip(chunks, index["vectors"]), key=lambda pair: cosine(pair[1]), reverse=True)
                rankings.append([c for c, v in ordered if cosine(v) > 0.2])
        except (OSError, ValueError, KeyError, TypeError, httpx.HTTPError):
            pass
    scores = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking[:30]):
            scores[chunk["id"]] = scores.get(chunk["id"], 0) + 1 / (60 + rank)
    ordered = sorted([c for c in chunks if c["id"] in scores], key=lambda c: (scores[c["id"]], c.get("variant") == "clean"), reverse=True)
    selected, seen = [], set()
    for chunk in ordered:
        key = " ".join(chunk["text"].split()).casefold()
        if key not in seen:
            seen.add(key); selected.append(chunk)
        if len(selected) == limit:
            break
    return selected
