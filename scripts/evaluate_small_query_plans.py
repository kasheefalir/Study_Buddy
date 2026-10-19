"""Compare single-query and multi-query planning, keeping the writer identical."""
import argparse
import asyncio
import json
import time
from pathlib import Path

from app.agents.query_plan_trial import plan_queries, collect, explain
from app.agents.study_tools import library, structured
from app.llm.ollama_client import OllamaClient
from app.config import settings

BOOK = "3a4c66034f8a4b6cba7320b89e254ff5"
R = "8d9fd23ca9ed45be98ead5736b14d7a7"
SLIDES = "5c1201a526914c8c9fde7a69fc1bfb4c"
CASES = [
    ("comparison", BOOK, "Compare degree centrality and betweenness centrality according to this book.", "chat", [], [86, 675]),
    ("followup", BOOK, "Can you explain that more simply?", "simplify",
     [{"role": "user", "content": "What does betweenness centrality measure?"},
      {"role": "assistant", "content": "It measures how often a node lies on shortest paths between others."}], [675]),
    ("summary", R, "Summarize this material's main topics.", "summary_material", [], []),
    ("fare", SLIDES, "How much does fare change per additional mile and for Southwest routes, holding other variables constant?", "chat", [], [3, 4]),
    ("missing_seed", SLIDES, "What exact random seed was used for the training/test split?", "chat", [], []),
    ("missing_laptop", BOOK, "Which laptop model and RAM capacity did Joel Grus use to write the book?", "chat", [], []),
]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new report path")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    root = settings.data_dir / "documents"
    old_prompt = Path("app/agents/prompts/retrieval_plan.md").read_text()
    rows = []
    for model in ("llama3.2:3b", "phi4-mini:latest"):
        llm = OllamaClient(settings.ollama_url, model, timeout=180)
        for index, (name, doc, question, mode, history, gold) in enumerate(CASES):
            # Alternate order to reduce warm-cache ordering effects.
            for variant in (("single", "multi") if index % 2 == 0 else ("multi", "single")):
                start = time.monotonic()
                row = {"model": model, "case": name, "variant": variant, "question": question}
                try:
                    books = library(root, [doc])
                    data = {"latest_message": question, "recent_dialogue": history,
                            "last_material_request": history[0]["content"] if history else "",
                            "selected_materials": [{"id": doc, "title": books[0][0]["name"]}],
                            "intent": {"route": "retrieve", "mode": mode}, "previous_evidence": []}
                    if variant == "single":
                        plan = await structured(llm, "retrieval plan", old_prompt, data)
                        queries = [plan["query"]]
                        resolved = plan["query"]
                    else:
                        plan = (await plan_queries(llm, data)).model_dump()
                        # Preserve the user wording as an additional search, not a replacement rewrite.
                        queries = list(dict.fromkeys(plan["queries"] + [question]))
                        resolved = plan["standalone_question"]
                    row["plan"] = plan
                    sources, traces, coverage = await collect(root, books, queries, overview=mode == "summary_material")
                    row.update(sources=sources, retrieval=traces, coverage=coverage,
                               gold_ids_present=sorted({s.get("chunk_id") for s in sources} & set(gold)))
                    row["answer"] = await explain(llm, {"original": question, "resolved": resolved}, sources, coverage)
                except Exception as exc:
                    row["error"] = type(exc).__name__ + ": " + str(exc)
                row["seconds"] = round(time.monotonic() - start, 2)
                rows.append(row)
                args.output.write_text(json.dumps(rows, indent=2))
                print(json.dumps({k: row[k] for k in ("model", "case", "variant", "seconds", "error", "plan", "gold_ids_present", "answer") if k in row and k != "answer"}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
