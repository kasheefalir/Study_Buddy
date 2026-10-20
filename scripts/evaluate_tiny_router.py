"""Isolated production-router probes; never changes the live routing policy."""
import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx

from app.agents.chat_agent import ROUTER_PROMPT
from app.agents.study_tools import structured
from app.config import settings
from app.llm.ollama_client import OllamaClient
from app.llm.usage import track_usage


CASES = [
    ("greeting", "Hey, how are you?", {}, "conversation", "chat", "keep"),
    ("source", "What does the material say about logistic regression?", {}, "retrieve", "chat", "keep"),
    ("simplify", "Explain that more simply.", {}, "retrieve", None, "keep"),
    ("overview", "Summarize this material.", {}, "retrieve", "summary_material", "keep"),
    ("recap", "Summarize our conversation, not the book.", {}, "conversation", "summary_conversation", "keep"),
    ("new_quiz", "Give me a five-question quiz on the material.", {}, "quiz", "quiz", "start"),
    ("pause", "Pause the quiz; let's just chat.", {"quiz_active": True}, "conversation", "chat", "pause"),
    ("resume", "Let's resume the saved quiz.", {"quiz_active": True, "quiz_paused": True}, "quiz", "quiz", "resume"),
    ("next", "Give me the next question.", {"quiz_active": True, "phase": "review"}, "quiz", "quiz", "next"),
    ("mixed", "Hey, explain the book's example again.", {}, "retrieve", "chat", "keep"),
]

COMPACT = """Classify latest_message, not older dialogue. Never answer it.
Use recent dialogue only to resolve 'that'.
route: conversation for greetings or general chat; retrieve for questions about
selected material, source follow-ups, simplification or material summaries;
quiz for starting/resuming/advancing a quiz; clarify for ambiguous requests.
mode: chat normally; summary_material for material overview; summary_conversation
for chat recap; simplify for simpler source explanations; quiz for quiz requests.
activity_action: keep normally; start for new quiz; pause for pausing; resume for
returning to a paused quiz; next for advancing; end for stopping; review for misses.
Do not choose next unless requested. A greeting does not resume a quiz.
pause_activity is true for pausing. query contains the resolved source question
only for retrieve, otherwise empty. reasoning must be brief."""


async def run(args):
    if args.output.exists():
        raise ValueError("Choose a fresh report path.")
    report = {"protocol": "Synthetic fixed-context shared router comparison, not full answer latency or GPT-specific routing.",
              "compact": args.compact,
              "rows": [], "residency": []}
    async with httpx.AsyncClient(timeout=15) as http:
        for model in args.model:
            client = OllamaClient(settings.ollama_url, model, 180)
            for repeat in range(args.repeats):
                for name, message, state, route, mode, action in CASES:
                    data = {
                        "latest_message": message,
                        "last_material_request": "Explain logistic regression in the selected material.",
                        "recent_dialogue": [
                            {"role": "user", "content": "Explain logistic regression in the material."},
                            {"role": "assistant", "content": "It models a binary outcome's probability."}],
                        "selected_materials": [{"id": "a" * 32, "title": "Statistics notes", "kind": "file", "url": ""}],
                        "unfinished_activity": {"mode": "chat", "quiz_active": False,
                            "quiz_paused": False, "quiz_ended": False, "phase": "",
                            "pending_question": "Which outcome is binary?", **state},
                        "explicit_task": "auto",
                    }
                    row = {"model": model, "repeat": repeat, "case": name, "input": data,
                           "expected": {"route": route, "mode": mode, "activity_action": action}}
                    start = time.monotonic()
                    with track_usage() as calls:
                        try:
                            result = await structured(client, "intent route", COMPACT if args.compact else ROUTER_PROMPT, data)
                            row["result"] = result
                            row["passed"] = (result["route"] == route and
                                (mode is None or result["mode"] == mode) and result["activity_action"] == action)
                        except Exception as exc:
                            row.update(passed=False, error=str(exc))
                    row.update(seconds=round(time.monotonic() - start, 3), usage=calls)
                    report["rows"].append(row)
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(json.dumps(report, indent=2))
                    print(json.dumps({k: row[k] for k in ("model", "case", "repeat", "passed", "seconds")}), flush=True)
            response = await http.get(f"{settings.ollama_url}/api/ps")
            report["residency"].append({"after": model, "ollama": response.json()})
        # Alternate the two clients to measure reload costs with both resident.
        report["alternating"] = []
        for model in [args.model[-1], args.model[0]] * 2:
            start = time.monotonic()
            with track_usage() as calls:
                try:
                    result = await structured(OllamaClient(settings.ollama_url, model, 180),
                                              "intent route", COMPACT if args.compact else ROUTER_PROMPT, data)
                    error = None
                except Exception as exc:
                    error = str(exc)
            report["alternating"].append({"model": model, "seconds": time.monotonic() - start,
                                           "usage": calls, "error": error})
        args.output.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))
