"""Opt-in real-model experiments; never changes the live model or user sessions."""
import argparse
import asyncio
import json
import logging
from pathlib import Path
import tempfile
import time

import httpx

from app.config import settings
from app.agents.deepseek.agent import DeepSeekAgent
from app.agents.deepseek.client import DeepSeekClient
from app.agents.deepseek.cache import ReadCache
from app.agents.deepseek.planning import CombinedRoute, Route, Read, ROUTER, COMBINED, decide
from app.agents.deepseek.search import search
from app.agents.deepseek.verification import verify_batch
from app.agents.grounded_answer import GroundedAnswer, verify_points
from app.agents.study_tools import library
from app.llm.ollama_client import OllamaClient
from app.llm.usage import track_usage, summarize
from app.storage.conversation_store import ConversationStore


def score_control(name, route, document, expected, action):
    valid = route.route == expected and route.action == action
    valid = valid and all(read.document_id == document for read in route.reads)
    valid = valid and (bool(route.reads) if expected == "retrieve" else not route.reads)
    if name in {"fact", "followup"}:
        valid = valid and any(read.tool == "search" and "betweenness" in read.query.lower() for read in route.reads)
    if name == "comparison":
        valid = valid and all(any(read.tool == "search" and term in read.query.lower()
            and other not in read.query.lower() for read in route.reads)
            for term, other in [("degree", "betweenness"), ("betweenness", "degree")])
    return bool(valid)


async def run(args):
    if args.phase == "rescore":
        report = json.loads(args.output.read_text())
        for row in report["rows"]:
            result = row.get("result", {})
            if "output" in result:
                result.setdefault("initial_loose_score", result["passed"])
                result["passed"] = score_control(row["name"], CombinedRoute.model_validate(result["output"]),
                    args.document, result["expected_route"], result["expected_action"])
        report["scoring"] = "v2: specific queries require search; comparisons require separate concept searches"
        args.output.write_text(json.dumps(report, indent=2))
        print(json.dumps([{ "name": r["name"], "passed": r.get("result", {}).get("passed") } for r in report["rows"]]))
        return
    root = settings.data_dir / "documents"
    document = args.document
    item, _ = library(root, [document])[0]
    materials = [{"id": document, "title": item["name"]}]
    deepseek = DeepSeekClient(settings.ollama_url, "deepseek-r1:8b", settings.request_timeout_seconds)
    controller = deepseek if args.model == "deepseek-r1:8b" else OllamaClient(settings.ollama_url, args.model, 120)
    rows = []
    args.output.parent.mkdir(parents=True, exist_ok=True)

    async def measure(name, operation):
        started = time.monotonic()
        with track_usage() as calls:
            try:
                value = await asyncio.wait_for(operation(), timeout=args.timeout)
                row = {"name": name, "result": value}
            except Exception as exc:
                row = {"name": name, "error": type(exc).__name__ + ": " + str(exc)}
            row.update(seconds=round(time.monotonic() - started, 2), usage=summarize(calls))
            if row.get("result", {}).get("answer", {}).get("usage"):
                row["usage"] = row["result"]["answer"]["usage"]
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                row["resident_models"] = (await client.get(settings.ollama_url + "/api/ps")).json()
            except httpx.HTTPError:
                pass
        rows.append(row)
        args.output.write_text(json.dumps({"phase": args.phase, "controller": args.model, "route_only": args.route_only, "rows": rows}, indent=2))
        print(json.dumps(row, default=str) if args.phase == "controls" else json.dumps({
            "name": name, "seconds": row["seconds"], "error": row.get("error"),
            "result": row.get("result", {}).get("summary", row.get("result")),
            "calls": len(row["usage"]["calls"])}), flush=True)

    question = "According to the book, what does betweenness centrality measure?"
    if args.phase == "controls":
        cases = [
            ("greeting", "Hey, how are you?", [], {}, "conversation", "keep", []),
            ("fact", question, [], {}, "retrieve", "keep", ["betweenness"]),
            ("followup", "Can you explain that more simply?", [{"role": "user", "content": question},
                {"role": "assistant", "content": "Betweenness centrality measures shortest paths through a node."}], {}, "retrieve", "keep", ["betweenness"]),
            ("comparison", "Compare degree centrality and betweenness centrality in this book.", [], {}, "retrieve", "keep", ["degree", "betweenness"]),
            ("pause", "Before we continue, how are you doing?", [], {"active": True, "phase": "question", "pending_question": "What is a median?"}, "conversation", "pause", []),
            ("resume", "Okay, let's pick up where we left off.", [{"role": "assistant", "content": "The quiz is paused."}],
             {"active": False, "paused": True, "phase": "question", "pending_question": "What is a median?"}, "quiz", "resume", []),
        ]
        for name, message, history, quiz, expected, action, terms in cases:
            if args.case and name != args.case:
                continue
            async def operation():
                route = await decide(controller, "controller probe", Route if args.route_only else CombinedRoute, ROUTER if args.route_only else ROUTER + COMBINED,
                    {"message": message, "explicit_task": "auto", "materials": materials,
                     "recent_dialogue": history, "quiz": quiz})
                valid = (route.route == expected and route.action == action) if args.route_only else score_control(name, route, document, expected, action)
                return {"output": route.model_dump(), "expected_route": expected, "expected_action": action, "passed": valid}
            await measure(name, operation)
    elif args.phase == "workflow":
        with tempfile.TemporaryDirectory(prefix="buddy-speed-") as directory:
            store = ConversationStore(Path(directory))
            agent = DeepSeekAgent(deepseek, store, combined=not args.route_only, lean_search=args.route_only,
                                  controller=controller, read_cache=ReadCache())
            message = question if args.case != "missing" else "What exact laptop model and RAM capacity did Joel Grus use to write this book? Answer only if the book explicitly says."
            async def operation():
                cid, reply = await agent.reply(message, materials_root=root, document_ids=[document])
                answer = store.load(cid)[-1]
                return {"summary": reply, "answer": answer, "quiz": store.quiz(cid)}
            await measure(args.case or "fact", operation)
    elif args.phase == "cache":
        cache = ReadCache()
        reads = [Read(tool="search", document_id=document, query="betweenness centrality")]
        for name in ("cold", "warm"):
            async def operation():
                sources, calls, _ = await search(controller, root, [document], question,
                                               initial_reads=reads, cache=cache, max_rounds=1)
                return {"summary": {"cache_hits": cache.hits, "sources": sources, "tools": calls}}
            await measure(name, operation)
    else:
        baseline = json.loads(Path("data/study-reviews/deepseek-isolated-schema-20261013.json").read_text())
        sources = next(t["response"]["sources"] for t in baseline["turns"] if t["name"] == "narrow_fact")
        answer = GroundedAnswer.model_validate({"points": [
            {"evidence": [{"label": "S4"}], "explanation": "Betweenness centrality adds up the proportion of shortest paths between other pairs of nodes that pass through a node."},
            {"evidence": [{"label": "S4"}], "explanation": "Joel Grus wrote the book on a MacBook Pro with 32 GB of RAM."},
            {"evidence": [{"label": "S1"}], "explanation": "Betweenness centrality adds up the proportion of shortest paths between other pairs of nodes that pass through a node."},
        ]})
        for name, check in (("separate", verify_points), ("batched", verify_batch)):
            if args.case and args.case != name:
                continue
            async def operation():
                result = await check(deepseek, answer, sources)
                verdicts = [entry.supported for entry in result]
                return {"summary": {"verdicts": verdicts, "expected": [True, False, False],
                                    "passed": verdicts == [True, False, False], "checks": [c.model_dump() for c in result]}}
            await measure(name, operation)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["controls", "workflow", "cache", "checks", "rescore"], required=True)
    parser.add_argument("--model", default="deepseek-r1:8b")
    parser.add_argument("--document", default="3a4c66034f8a4b6cba7320b89e254ff5")
    parser.add_argument("--case")
    parser.add_argument("--route-only", action="store_true")
    parser.add_argument("--timeout", type=float, default=600, help="Wall-clock ceiling per probe, in seconds")
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))
