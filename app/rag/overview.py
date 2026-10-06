"""Resumable, content-addressed section/chapter/book study overviews."""
import asyncio
import hashlib
import json
from collections import OrderedDict

from pydantic import BaseModel, Field

from app.agents.context_budget import estimate, input_limit
from app.agents.study_tools import OUTPUTS, structured, structured_messages
from app.rag.library import write_json
from app.llm.usage import track_usage, summarize


class Overview(BaseModel):
    summary: str = Field(min_length=1, max_length=1000)
    concepts: list[str] = Field(min_length=1, max_length=5)


OUTPUTS["material overview"] = Overview
PROMPT = ("Create a compact academic study summary and up to five main concepts from the supplied "
          "source or section summaries. Preserve important qualifications. Exclude author jokes, "
          "publishing details and incidental dataset trivia. Concepts should be transferable ideas, "
          "not questions or answer keys. Do not invent missing information. Each concept under 120 characters.")
jobs = {}
worker = asyncio.Semaphore(1)


def fingerprint(chunks):
    return hashlib.sha256(json.dumps(chunks, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def cached(root, identifier, chunks=None):
    path = root / identifier / "overview.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if chunks is not None and data.get("fingerprint") != fingerprint(chunks):
        return {}
    return data


def status(root, identifier):
    data = cached(root, identifier)
    state = data.get("status", "not_started")
    if (str(root), identifier) in jobs and state not in {"preparing", "ready"}:
        state = "queued"
    if state in {"queued", "preparing"} and (str(root), identifier) not in jobs:
        state = "paused"
    return {"status": state, "completed": len(data.get("nodes", {})),
            "total": data.get("total", 0), "error": data.get("error", "")}


def plan(chunks):
    primary = [c for c in chunks if c.get("variant") == "clean"] or chunks
    groups, group, chapter = [], [], None
    for c in primary:
        heading = c.get("chapter") or c.get("heading") or "Material"
        proposed = {"heading": heading, "text": "\n".join(x["text"] for x in group + [c])}
        if group and (heading != chapter or estimate(structured_messages("material overview", PROMPT, proposed)) > min(input_limit(), 2400)):
            groups.append((chapter, group)); group = []
        group.append(c); chapter = heading
    if group:
        groups.append((chapter, group))
    nodes, chapters = [], OrderedDict()
    for i, (heading, group) in enumerate(groups):
        node = {"id": f"section-{i}", "heading": heading, "kind": "section", "chunk_ids": [c["id"] for c in group]}
        nodes.append(node); chapters.setdefault(heading, []).append(node["id"])

    def combine(ids, heading, kind):
        while len(ids) > 1:
            next_ids = []
            for start in range(0, len(ids), 3):
                children = ids[start:start + 3]
                if len(children) == 1:
                    next_ids.extend(children); continue
                node = {"id": f"merge-{len(nodes)}", "heading": heading, "kind": kind, "children": children}
                nodes.append(node); next_ids.append(node["id"])
            ids = next_ids
        return ids[0]

    roots = [combine(ids, heading, "chapter") for heading, ids in chapters.items()]
    return nodes, combine(roots, "Book overview", "book") if roots else None, roots


async def prepare(root, identifier, llm):
    chunks = json.loads((root / identifier / "chunks.json").read_text())
    digest = fingerprint(chunks)
    nodes, top, chapter_roots = plan(chunks)
    state = cached(root, identifier, chunks) or {"fingerprint": digest, "nodes": {}}
    path = root / identifier / "overview.json"
    state.update(status="preparing", total=len(nodes), root=top, chapter_roots=chapter_roots, error="")
    write_json(path, state)
    lookup = {c["id"]: c for c in chunks}
    try:
        for node in nodes:
            if node["id"] in state["nodes"]:
                continue
            from app.agents.activity import active
            while active:
                await asyncio.sleep(.5)
            if node["kind"] == "section":
                ids = node["chunk_ids"]
                payload = {"heading": node["heading"], "text": "\n".join(lookup[i]["text"] for i in ids)}
            else:
                children = [state["nodes"][i] for i in node["children"]]
                ids = list(dict.fromkeys(i for child in children for i in child["chunk_ids"]))
                payload = {"heading": node["heading"], "sections": [
                    {"summary": child["summary"][:750], "concepts": [c[:120] for c in child["concepts"][:3]]} for child in children]}
            if estimate(structured_messages("material overview", PROMPT, payload)) > input_limit():
                raise ValueError("A section exceeds the context budget. Increase CONTEXT_WINDOW and resume.")
            with track_usage() as calls:
                result = await structured(llm, "material overview", PROMPT, payload)
            state["nodes"][node["id"]] = {**node, **result, "chunk_ids": ids, "usage": summarize(calls)}
            write_json(path, state)
            await asyncio.sleep(.1)
        state["status"] = "ready" if top else "unavailable"
    except asyncio.CancelledError:
        state["status"] = "paused"
        raise
    except Exception as exc:
        state.update(status="paused", error=str(exc)[:300])
    finally:
        write_json(path, state)
    return state


def start(root, identifier, llm):
    key = (str(root), identifier)
    if key in jobs:
        return
    async def run():
        try:
            async with worker:
                await prepare(root, identifier, llm)
        finally:
            jobs.pop(key, None)
    task = asyncio.create_task(run())
    jobs[key] = task


async def pause(root, identifier):
    task = jobs.get((str(root), identifier))
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def concept_windows(root, books, focus=""):
    terms = set(focus.lower().split())
    windows = []
    for item, chunks in books:
        data = cached(root, item["id"], chunks)
        # Use a complete document map, not a partial scan masquerading as coverage.
        if data.get("status") != "ready":
            return []
        for node_id in data.get("chapter_roots", []):
            node = data["nodes"][node_id]
            for concept in node["concepts"]:
                score = sum(term in concept.lower() for term in terms)
                windows.append({"document_id": item["id"], "chunk_ids": node["chunk_ids"],
                                "concept": concept[:200], "score": score})
    matched = [w for w in windows if w["score"]]
    return matched or windows
