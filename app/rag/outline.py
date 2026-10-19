"""Source-linked navigation built from extracted metadata, never model guesses."""
import re


def build(chunks):
    primary = [c for c in chunks if c.get("variant") == "clean"] or chunks
    sections = []
    for chunk in primary:
        heading = chunk.get("chapter") or chunk.get("heading") or "Untitled section"
        if not sections or sections[-1]["heading"] != heading:
            sections.append({"section_id": f"SECTION_{len(sections) + 1:04d}",
                "heading": heading, "chunk_ids": [], "locations": []})
        section = sections[-1]
        section["chunk_ids"].append(chunk["id"])
        location = chunk.get("location", "")
        if location and location not in section["locations"]:
            section["locations"].append(location)
    return sections


def navigation(chunks, query="", limit=8):
    sections = build(chunks)
    terms = set(re.findall(r"\w+", query.casefold())) - {
        "what", "does", "the", "material", "say", "about", "explain", "summarize", "this", "and", "of", "in"}
    # Heading matches identify destinations, not proof of an answer's support.
    scored = [(len(terms & set(re.findall(r"\w+", s["heading"].casefold()))), i, s)
              for i, s in enumerate(sections)]
    matched = sorted((x for x in scored if x[0]), key=lambda x: (-x[0], x[1]))
    if matched:
        chosen = [s for _, _, s in matched[:limit]]
    else:
        chosen = [sections[i] for i in spread(len(sections), limit)]
    return {"total_sections": len(sections), "shown_sections": len(chosen),
            "omitted_sections": len(sections) - len(chosen), "matched_headings": bool(matched),
            "guidance": "Navigation metadata only, not supporting evidence. Missing heading matches do not mean a topic is absent.",
            "sections": [{"section_id": s["section_id"], "heading": s["heading"][:160],
                "first_chunk_id": s["chunk_ids"][0], "last_chunk_id": s["chunk_ids"][-1],
                "start": s["locations"][0] if s["locations"] else ""} for s in chosen]}


def spread(count, limit):
    if count <= 0 or limit <= 0:
        return []
    if count <= limit:
        return list(range(count))
    if limit == 1:
        return [0]
    return [round(i * (count - 1) / (limit - 1)) for i in range(limit)]
