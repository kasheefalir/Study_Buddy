"""Compare neighbor policies on identical retrieved hits; no user state changes."""
import asyncio
import json
import time
from pathlib import Path

from app.config import settings
from app.agents.study_tools import library, coherent_passages
from app.rag.semantic import retrieve


def previous_selection(chunks, quota, hits):
    primary = [c for c in chunks if c.get("variant") == "clean"] or chunks
    groups = []
    for chunk in primary:
        key = (chunk.get("chapter"), chunk.get("location"), chunk.get("variant"))
        if not groups or groups[-1][0] != key:
            groups.append((key, []))
        groups[-1][1].append(chunk)
    result, seen = [], set()
    for hit in hits:
        group = next((g for _, g in groups if any(c["id"] == hit["id"] for c in g)), [hit])
        index = next(i for i, c in enumerate(group) if c["id"] == hit["id"])
        for chunk in group[max(0, index - 1):index + 2]:
            if len(result) < quota and chunk["id"] not in seen:
                result.append(chunk)
                seen.add(chunk["id"])
    return result


async def main():
    root = settings.data_dir / "documents"
    item, chunks = library(root, ["3a4c66034f8a4b6cba7320b89e254ff5"])[0]
    rows = []
    # Gold IDs refer to manually inspected definition passages in this private book.
    for query, gold in [("degree centrality", {86}),
                        ("betweenness centrality measure", {675}),
                        ("degree centrality number of friends", {86})]:
        start = time.monotonic()
        hits = await retrieve(root, item, chunks, query, 3)
        row = {"query": query, "retrieval_seconds": round(time.monotonic() - start, 3),
               "primary_ids": [c["id"] for c in hits]}
        for name, select in [("previous", previous_selection), ("reserved", coherent_passages)]:
            selected = select(chunks, 4, hits)
            ids = {c["id"] for c in selected}
            row[name] = {"ids": [c["id"] for c in selected],
                         "primary_retained": len(ids & {c["id"] for c in hits}),
                         "gold_hit": bool(ids & gold)}
        rows.append(row)
    path = Path("data/study-reviews/neighbor-selection.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2))
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
