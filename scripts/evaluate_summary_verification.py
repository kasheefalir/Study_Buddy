"""Isolated fixed-evidence experiments; never changes live verification policy."""
import argparse
import asyncio
import json
import re
import time
from pathlib import Path

from app.agents.context_budget import estimate, input_limit, model_budget
from app.agents.grounded_answer import GroundedAnswer, evidence_check_request, check_schema_for, parse_checks
from app.agents.gpt.client import GPTClient
from app.agents.study_tools import structured
from app.config import settings
from app.llm.ollama_client import OllamaClient
from app.llm.usage import track_usage, summarize
from app.rag.overview import PROMPT


def fixtures():
    saved = json.loads(Path("data/evaluations/routing-recovery-gemma-diagnostics-repeat.json").read_text())
    logistic = {s["label"]: s for s in saved[0]["response"]["sources"]}
    trees = {s["label"]: s for s in saved[1]["response"]["sources"]}
    sources = [{**logistic["S5"], "label": "S1"}, {**logistic["S4"], "label": "S2"},
               {**trees["S1"], "label": "S3"}, {**trees["S8"], "label": "S4"}]
    # Each verdict is adjudicated against its cited passage, not the whole book.
    cases = [
        [("The logistic function approaches 1 for large positive inputs.", "S1", True),
         ("The example reports precision of 82% and recall of 93%.", "S2", False),
         ("Classification trees produce categorical outputs; regression trees produce numeric outputs.", "S3", True),
         ("An overfitted tree is guaranteed to generalize well to unseen data.", "S4", False)],
        [("The example reports precision of 93% and recall of 82%.", "S1", False),
         ("The example reports precision of 93% and recall of 82%.", "S2", True),
         ("Finding an optimal decision tree is computationally hard.", "S4", True),
         ("Decision trees always outperform logistic regression on test data.", "S3", False)],
    ]
    return sources, cases


async def batched(llm, answer, sources):
    request = evidence_check_request(answer, sources)
    if llm.model == "gpt-oss:20b":
        request[0]["content"] = request[0]["content"].split("\nJSON schema:", 1)[0]
    if estimate(request) > input_limit():
        raise ValueError("Batch exceeds input budget")
    return parse_checks(await llm.structured_plan(request, check_schema_for(len(answer.points))), len(answer.points))


async def single(llm, answer, sources):
    # Freeze the baseline even when production enables batching for a model.
    checks = []
    for index, point in enumerate(answer.points):
        result = await batched(llm, GroundedAnswer(points=[point]), sources)
        checks.append(result[0].model_copy(update={"index": index}))
    return checks


def verdict_metrics(expected, actual):
    if actual is None:
        return {"format_error": True, "correct": 0, "false_accepts": None, "false_rejects": None}
    return {"format_error": False, "correct": sum(a == e for a, e in zip(actual, expected)),
            "false_accepts": sum(a and not e for a, e in zip(actual, expected)),
            "false_rejects": sum(not a and e for a, e in zip(actual, expected))}


def coverage(result):
    text = json.dumps(result).lower()
    patterns = {"logistic_function": r"logistic", "precision": r"precision",
                "recall": r"recall", "classification": r"classification",
                "regression_trees": r"regression tree", "overfitting": r"overfit",
                "generalization": r"generaliz", "optimization_difficulty": r"optimal|computational"}
    return {key: bool(re.search(pattern, text)) for key, pattern in patterns.items()}


async def run(args):
    if args.output.exists():
        raise ValueError("Choose a new report path")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sources, cases = fixtures()
    if args.holdout:
        cases = [
            [("For large negative inputs the logistic function approaches 0.", "S1", True),
             ("The logistic function's derivative is always negative.", "S1", False),
             ("Precision equals true positives divided by true positives plus false positives.", "S2", True),
             ("The model achieved 100% precision on the test data.", "S2", False)],
            [("The chapter focuses on classification trees and binary outputs.", "S3", True),
             ("Regression trees produce categorical outputs.", "S3", False),
             ("A good-enough tree may still require substantial work on large data sets.", "S4", True),
             ("A good-enough tree eliminates all risk of overfitting.", "S4", False)],
        ]
    client = (GPTClient if args.model == "gpt-oss:20b" else OllamaClient)(settings.ollama_url, args.model)
    report = {"model": args.model, "sources": sources, "verification": [], "summaries": [],
              "coverage_note": "Lexical screen only; manually review accuracy, qualifications, and omissions."}

    def save():
        args.output.write_text(json.dumps(report, indent=2))

    with model_budget(args.model):
        for repeat in range(0 if args.children_from else args.repeats):
            for i, case in enumerate(cases):
                answer = GroundedAnswer(points=[{"explanation": claim, "evidence": [{"label": label}]}
                                                 for claim, label, _ in case])
                expected = [expected for _, _, expected in case]
                # Alternate condition order to reduce systematic warm-cache bias.
                for mode in (["single", "batch"] if repeat % 2 == 0 else ["batch", "single"]):
                    started = time.monotonic()
                    row = {"repeat": repeat, "case": i, "mode": mode, "expected": expected,
                           "claims": answer.model_dump()}
                    with track_usage() as calls:
                        try:
                            checks = await (single if mode == "single" else batched)(client, answer, sources)
                            row["checks"] = [c.model_dump() for c in checks]
                            actual = [c.supported for c in checks]
                        except (ValueError, RuntimeError, TypeError) as exc:
                            row["error"] = str(exc)
                            actual = None
                    row.update(verdict_metrics(expected, actual), seconds=round(time.monotonic() - started, 3), usage=summarize(calls))
                    report["verification"].append(row)
                    save()
                    print(json.dumps({k: row[k] for k in ("repeat", "case", "mode", "correct", "false_accepts", "format_error", "seconds")}), flush=True)

        if args.holdout:
            return
        children = json.loads(args.children_from.read_text())["children"] if args.children_from else []
        for source in ([] if args.children_from else sources):
            result = await structured(client, "material overview", PROMPT,
                                      {"heading": source["location"], "text": source["text"]})
            children.append({"heading": source["location"], **result})
        report["children"] = children
        save()
        for repeat in range(args.repeats):
            for mode in (["legacy", "preserved", "qualified"] if repeat % 2 == 0 else ["qualified", "preserved", "legacy"]):
                sections = children if mode != "legacy" else [
                    {"summary": c["summary"][:750], "concepts": c["concepts"][:3]} for c in children]
                started = time.monotonic()
                row = {"mode": mode, "repeat": repeat, "input": sections}
                with track_usage() as calls:
                    try:
                        prompt = PROMPT
                        if mode == "qualified":
                            prompt += (" Keep each section's central idea and limitation distinct. "
                                "Do not imply a workaround for one limitation solves another limitation. "
                                "Never turn a risk or uncertainty into a guarantee. Preserve important "
                                "directional and category distinctions, not just topic names.")
                        result = await structured(client, "material overview", prompt,
                            {"heading": "Selected regression and tree passages", "sections": sections})
                        row.update(result=result, lexical_coverage=coverage(result))
                    except (ValueError, RuntimeError, TypeError) as exc:
                        row["error"] = str(exc)
                row.update(seconds=round(time.monotonic() - started, 3), usage=summarize(calls))
                report["summaries"].append(row)
                save()
                print(json.dumps({k: v for k, v in row.items() if k not in {"input", "usage"}}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--holdout", action="store_true")
    parser.add_argument("--children-from", type=Path)
    asyncio.run(run(parser.parse_args()))
