"""Budgeted document views and compact current-session awareness."""
import json
import re
from pathlib import Path

from app.agents.context_budget import estimate, data_message


def current_study_session(root: Path, identifiers: list[str]) -> dict:
    """Return bounded orientation data, not substitute source evidence."""
    from app.rag.overview import cached, status

    materials = []
    for index, identifier in enumerate(dict.fromkeys(identifiers)):
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{32}", identifier):
            continue
        try:
            item = json.loads((root / f"{identifier}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        card = {
            "id": identifier,
            "title": (item.get("page_title") or item.get("name") or "Untitled material")[:160],
            "kind": item.get("kind", "file"),
            "status": item.get("status", "Unknown"),
            "import_stage": item.get("import_stage", ""),
            "overview": status(root, identifier),
        }
        # A compact overview gives the tutor an accurate sense of the session,
        # while complete source passages remain a separate retrieval concern.
        if index < 3 and card["overview"].get("status") == "ready":
            try:
                chunks = json.loads((root / identifier / "chunks.json").read_text(encoding="utf-8"))
                data = cached(root, identifier, chunks)
                top = data.get("nodes", {}).get(data.get("root"), {})
                if top:
                    card["orientation"] = top.get("summary", "")[:360]
                    card["main_concepts"] = [str(value)[:120] for value in top.get("concepts", [])[:5]]
            except (OSError, ValueError, TypeError):
                pass
        materials.append(card)
    return {
        "selected_material_count": len(materials),
        "materials": materials,
        "guidance": "Use this to identify the active study batch and answer session-awareness questions. "
                    "It is orientation data, not sufficient evidence for detailed claims about a source.",
    }


def document_view(root, item, chunks, budget):
    from app.agents.study_tools import passages, coherent_passages
    from app.rag.overview import cached
    primary = [c for c in chunks if c.get("variant") == "clean"] or chunks
    full = passages(item, primary)
    cost = lambda values: estimate([data_message("Reviewed session materials", values)])
    if cost(full) <= budget:
        return full, "full_text"
    cache = cached(root, item["id"], chunks)
    nodes = cache.get("nodes", {})
    top = nodes.get(cache.get("root"))
    if cache.get("status") == "ready" and top:
        def source(node):
            ids = set(node["chunk_ids"])
            first = next((c for c in primary if c["id"] in ids), {})
            return {"document_id": item["id"], "name": item.get("page_title") or item["name"],
                    "location": "Generated overview: " + node["heading"],
                    "text": node["summary"] + "\nMain ideas: " + "; ".join(node.get("concepts", [])),
                    "variant": "generated_summary", "covered_chunk_ids": node["chunk_ids"],
                    "page": first.get("page"), "label": "Overview"}
        # Expand the complete tree frontier only when ALL children fit. Never sample
        # chapters and mistake their summaries for a complete document overview.
        frontier = [top]
        while True:
            expanded = False
            for index, node in enumerate(frontier):
                children = [nodes[k] for k in node.get("children", []) if k in nodes]
                if not children:
                    continue
                proposed = frontier[:index] + children + frontier[index + 1:]
                if cost([source(n) for n in proposed]) <= budget:
                    frontier = proposed
                    expanded = True
                    break
            if not expanded:
                break
        result = [source(n) for n in frontier]
        if cost(result) <= budget:
            return result, "complete_hierarchy"
    result = []
    for passage in passages(item, coherent_passages(primary, 12)):
        if cost(result + [passage]) <= budget:
            result.append(passage)
    return result, "partial_text"


def coverage_report(books, sources):
    report = []
    for item, chunks in books:
        primary = [c for c in chunks if c.get("variant") == "clean"] or chunks
        expected = {c["id"] for c in primary}
        originals, represented = set(), set()
        for source in sources:
            if source["document_id"] != item["id"]:
                continue
            if source.get("variant") == "generated_summary":
                represented.update(source.get("covered_chunk_ids", []))
            elif "chunk_id" in source:
                originals.add(source["chunk_id"])
        represented.update(originals)
        report.append({"document_id": item["id"], "total_passages": len(expected),
                       "original_passages": len(expected & originals),
                       "represented_passages": len(expected & represented),
                       "complete": bool(expected) and expected <= represented,
                       "summary_only_coverage": bool(represented - originals)})
    return report
