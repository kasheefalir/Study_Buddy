"""Isolated controlled-workflow evaluation; all reports contain private material."""
import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

from app.agents.local_study import workflows as w
from app.agents.local_study.runtime import LocalRuntime, MemorySampler
from app.agents.study_tools import library, passages
from app.agents.grounded_answer import answer_from_sources
from app.agents.chat_agent import SYSTEM_PROMPT
from app.config import settings


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a fresh report filename")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cases = json.loads(Path("tests/fixtures/local_study_cases.json").read_text())
    root = settings.data_dir / "documents"
    sampler = MemorySampler()
    monitor = asyncio.create_task(sampler.run())
    report = {"settings": {"context": 4096, "output": 700, "temperature": 0.1, "reranker": "none",
                           "baseline": "existing grounded writer with same runtime settings; not full agent routing",
                           "release": "disabled_pending_human_evaluation_and_8GB_validation"}, "rows": []}

    async def record(model, case, variant, operation, client):
        start, call_start = time.monotonic(), len(client.calls)
        row = {"model": model, "case": case, "variant": variant}
        try:
            row["result"] = await operation()
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        row.update(seconds=round(time.monotonic()-start, 3), memory=sampler.report(start), calls=client.calls[call_start:])
        report["rows"].append(row)
        args.output.write_text(json.dumps(report, indent=2))
        print(json.dumps({k:v for k,v in row.items() if k not in {"result","calls","memory"}}), flush=True)

    try:
        for model in ("llama3.2:3b", "phi4-mini:latest"):
            client = LocalRuntime(model)
            await client.exclusive()
            for case in cases:
                books = library(root, [case["doc"]])
                item, chunks = books[0]
                known = {c["id"]: c for c in chunks}
                oracle = passages(item, [known[i] for i in case["oracle"]])
                state = {"previous_question": case.get("previous_question", ""),
                         "sources": [{"document_id": item["id"], "chunk_id": i} for i in case["oracle"]]} if case.get("previous_question") else {}

                async def baseline():
                    query = case.get("previous_question") or case["question"]
                    sources = await w.search(root, books, query)
                    text = await answer_from_sources(client, [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": case["question"]}], sources, query)
                    found = {s["chunk_id"] for s in sources}
                    return {"text": text, "sources": sources,
                            "retrieval_success": all(set(group) & found for group in case["gold"]) if case["gold"] else None}

                async def candidate():
                    result = await w.qa(client, root, books, case["question"], state)
                    found = {s["chunk_id"] for section in result.get("sections", []) for s in section["context_sources"]}
                    result["retrieval_success"] = all(set(group) & found for group in case["gold"]) if case["gold"] else None
                    return result

                async def oracle_answer():
                    return await w.qa(client, root, books, case["question"], state, oracle=oracle)

                await record(model, case["id"], "baseline", baseline, client)
                await record(model, case["id"], "candidate", candidate, client)
                await record(model, case["id"], "oracle", oracle_answer, client)

            item, chunks = library(root, [cases[0]["doc"]])[0]
            await record(model, "section_summary", "candidate", lambda: w.study_guide(client, item, [c for c in chunks if c["id"] == 4]), client)
            await record(model, "full_study_guide", "candidate", lambda: w.study_guide(client, item, chunks), client)
            for chunk_id in (4, 18):
                evidence = passages(item, [c for c in chunks if c["id"] == chunk_id])
                await record(model, f"quiz_{chunk_id}", "candidate", lambda: w.make_quiz(client, evidence), client)
    finally:
        sampler.stop = True
        await monitor
        report["memory"] = sampler.report()
        report["timings"] = {model: {variant: statistics.median([r["seconds"] for r in report["rows"]
            if r["model"] == model and r["variant"] == variant]) for variant in ("baseline", "candidate", "oracle")
            if any(r["model"] == model and r["variant"] == variant for r in report["rows"])}
            for model in ("llama3.2:3b", "phi4-mini:latest")}
        args.output.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
