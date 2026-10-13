"""Live probes of the two existing intent passes, separate from RAG evaluation."""
import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app.agents.chat_agent import ROUTER_PROMPT, INTENT_RESOLUTION_PROMPT, RETRIEVAL_PLAN_PROMPT
from app.agents.study_tools import IntentRoute, IntentDecision, RetrievalPlan, structured_messages
from app.config import settings
from scripts.evaluate_selector_precision import model_call


CASES = [
    {"name": "greeting", "message": "how r u?", "expected": "conversation", "mode": "summary_material", "active": False},
    {"name": "pause", "message": "Let's pause the quiz and just chat for a minute.", "expected": "conversation", "mode": "chat", "active": True},
    {"name": "resume", "message": "Okay, back to the book: explain that distance comparison again.", "expected": "retrieve", "mode": "chat", "active": False},
    {"name": "followup", "message": "Why does adding noise make that worse?", "expected": "retrieve", "mode": "chat", "active": False},
]


async def run(args):
    if args.output.exists():
        raise ValueError("Preserve previous report; choose a new output path.")
    rows = []
    report = {"created": datetime.now(timezone.utc).isoformat(),
              "model": settings.ollama_model,
              "context_window": settings.context_window,
              "response_tokens": settings.response_tokens,
              "temperature": 0.2,
              "separated": args.separated,
              "protocol": "Independent production-prompt probes; not an end-to-end conversation or retrieval test.",
              "results": rows}
    material = {"id": "a" * 32, "title": "Data Science from Scratch", "kind": "file", "url": ""}
    for repeat in range(2):
        for case in CASES:
            history = [{"role": "user", "content": "Explain the book's low versus high dimensional distance comparison."},
                       {"role": "assistant", "content": "In low dimensions, nearest points are much closer than average; in many dimensions they often are not."}]
            if case["name"] == "resume":
                history.append({"role": "user", "content": "Let's pause studying and chat."})
            data = {"latest_message": case["message"], "last_material_request": history[0]["content"],
                    "recent_dialogue": history[-3:], "selected_materials": [material],
                    "unfinished_activity": {"mode": case["mode"], "quiz_active": case["active"],
                                            "pending_question": "What happens to nearest-point distances?" if case["active"] else ""},
                    "explicit_task": "auto"}
            row = {"case": case, "repeat": repeat + 1, "calls": []}
            try:
                stages = [("intent route", ROUTER_PROMPT, IntentRoute),
                          (("retrieval plan", RETRIEVAL_PLAN_PROMPT, RetrievalPlan) if args.separated else
                           ("intent decision", INTENT_RESOLUTION_PROMPT, IntentDecision))]
                for stage, prompt, model in stages:
                    if stage == "retrieval plan":
                        if row["first_pass"]["route"] != "retrieve":
                            break
                        data = {**data, "intent": row["first_pass"], "previous_evidence": []}
                    if stage == "intent decision":
                        data = {**data, "first_intent_pass": row["first_pass"], "previous_evidence": []}
                    request = structured_messages(stage, prompt, data)
                    trace = {"stage": stage, "request": request, "schema": model.model_json_schema()}
                    row["calls"].append(trace)
                    start = time.monotonic()
                    trace["raw"], trace["usage"] = await model_call(request, trace["schema"], 0.2)
                    trace["seconds"] = round(time.monotonic() - start, 3)
                    parsed = model.model_validate_json(trace["raw"]).model_dump()
                    row["first_pass" if stage == "intent route" else "planner" if args.separated else "decision"] = parsed
                if args.separated:
                    row["decision"] = dict(row["first_pass"])
                    if "planner" in row:
                        row["decision"]["query"] = row["planner"]["query"]
                decision = row["decision"]
                row["passed"] = decision["route"] == case["expected"] and decision["mode"] == "chat"
                if case["name"] == "pause":
                    row["passed"] &= decision["pause_activity"] or decision.get("activity_action") == "pause"
            except Exception as exc:
                row["error"] = str(exc)
                row["passed"] = False
            rows.append(row)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2))
            print(json.dumps({k: v for k, v in row.items() if k != "calls"}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--separated", action="store_true")
    asyncio.run(run(parser.parse_args()))
