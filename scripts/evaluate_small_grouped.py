"""Run the grouped small-model trial on the existing six local-material cases."""
import argparse
import asyncio
import json
import time
from pathlib import Path

from app.agents.study_tools import library
from app.config import settings
from app.llm.ollama_client import OllamaClient
from scripts.evaluate_small_query_plans import CASES


# Diagnostic only: human-specified decomposition, never used by the live planner.
ORACLE_PARTS = {
    "comparison": [("degree centrality", "degree centrality definition"),
                   ("betweenness centrality", "betweenness centrality definition")],
    "followup": [("Can you explain that more simply?", "betweenness centrality definition")],
    "summary": [("Summarize this material's main topics.", "main topics")],
    "fare": [("per additional mile", "fare change per additional mile holding other variables constant"),
             ("for Southwest routes", "fare difference routes served by Southwest versus other routes holding other variables constant")],
    "missing_seed": [("exact random seed", "exact random seed training/test split")],
    "missing_laptop": [("laptop model", "Joel Grus laptop model used writing book"),
                       ("RAM capacity", "Joel Grus RAM capacity used writing book")],
}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quoted", action="store_true", help="Use isolated exact-quote trial")
    parser.add_argument("--oracle-parts", action="store_true", help="Diagnostic human-defined question parts")
    args = parser.parse_args()
    if args.oracle_parts and not args.quoted:
        parser.error("--oracle-parts requires --quoted")
    if args.quoted:
        from app.agents.small_models import quoted_trial as workflow
    else:
        from app.agents.small_models import workflow
    if args.output.exists():
        raise ValueError("Report already exists")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    root = settings.data_dir / "documents"
    rows = []
    for model in ("llama3.2:3b", "phi4-mini:latest"):
        llm = OllamaClient(settings.ollama_url, model, timeout=180)
        for case, doc, question, mode, history, gold in CASES:
            row = {"model": model, "case": case, "question": question,
                   "plan_origin": "human_diagnostic" if args.oracle_parts else "model"}
            start = time.monotonic()
            try:
                if args.oracle_parts:
                    materials = {"SOURCE_001": library(root, [doc])[0]}
                    parts = [{"focus": focus, "query": query, "source": "SOURCE_001", "id": f"PART_{i:03d}"}
                             for i, (focus, query) in enumerate(ORACLE_PARTS[case], 1)]
                    assert all(part["focus"] in question for part in parts)
                else:
                    parts, materials = await workflow.plan(llm, question, history, library(root, [doc]), mode == "summary_material")
                row["parts"] = parts
                groups, registry = await workflow.gather(root, parts, materials, mode == "summary_material")
                if args.quoted:
                    for group in groups:
                        group["recent_dialogue"] = history
                row["groups"] = groups
                row["gold_ids_present"] = sorted({s.get("chunk_id") for s in registry.values()} & set(gold))
                row["answer"] = await workflow.answer(llm, question, groups, registry)
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
            row["seconds"] = round(time.monotonic() - start, 2)
            rows.append(row)
            args.output.write_text(json.dumps(rows, indent=2))
            print(json.dumps({k: v for k, v in row.items() if k not in ("groups", "answer")}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
