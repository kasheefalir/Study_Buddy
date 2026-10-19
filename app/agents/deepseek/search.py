from app.agents.study_tools import library, passages, coherent_passages
from app.agents.retrieval_context import document_view
from app.rag.semantic import retrieve

from .planning import decide, SearchPlan, SEARCHER


async def search(llm, root, identifiers, question, *, initial_reads=None, cache=None, max_rounds=2):
    books = {item["id"]: (item, chunks) for item, chunks in library(root, identifiers)}
    manifest = [{"id": key, "title": item.get("page_title") or item["name"]}
                for key, (item, _) in books.items()]
    sources, executed = [], []
    for turn in range(max_rounds):
        plan = SearchPlan(reads=initial_reads, clarification="") if turn == 0 and initial_reads is not None else await decide(llm, "deepseek search plan", SearchPlan, SEARCHER,
                            {"question": question, "materials": manifest, "pass": turn + 1,
                             "executed": executed, "evidence": sources})
        if plan.clarification:
            return sources, executed, plan.clarification
        if not plan.reads:
            break
        for read in plan.reads:
            if read.document_id not in books:
                raise ValueError("DeepSeek requested a material outside this session. Retry with the selected materials.")
            call = read.model_dump()
            if call in executed:
                continue
            executed.append(call)
            item, chunks = books[read.document_id]
            key = cache.key(root, item, chunks, read) if cache and read.tool == "search" else None
            cached = cache.get(key) if key else None
            if cached is not None:
                extra = cached
            elif read.tool == "overview":
                extra, _ = document_view(root, item, chunks, 1200)
            else:
                hits = await retrieve(root, item, chunks, read.query, 3)
                extra = passages(item, coherent_passages(chunks, 4, hits))
            if key and cached is None:
                cache.put(key, extra)
            for source in extra:
                key = (source["document_id"], source.get("chunk_id"), source["location"])
                if any((s["document_id"], s.get("chunk_id"), s["location"]) == key for s in sources):
                    continue
                # Bound the tool transcript; preserve source identity when excerpting.
                sources.append({**source, "text": source["text"][:1800],
                                "truncated": len(source["text"]) > 1800,
                                "label": f"S{len(sources) + 1}"})
                if len(sources) >= 8:
                    return sources, executed, ""
    return sources, executed, ""
