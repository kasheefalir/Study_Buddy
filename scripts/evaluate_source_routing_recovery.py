"""Fresh-session source probes; never reuse another model's answers."""
import argparse
import json
import tempfile
import time
from collections import defaultdict
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.storage.conversation_store import ConversationStore


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--document", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--controls", action="store_true")
    parser.add_argument("--topic", action="append", help="Override default topics; may be repeated")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Choose a new output path")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    traces = []
    original = main.OllamaClient.structured_plan

    async def traced(self, messages, schema):
        raw = await original(self, messages, schema)
        traces.append({"schema": schema.get("title"), "raw": raw})
        return raw

    main.OllamaClient.structured_plan = traced
    with tempfile.TemporaryDirectory(prefix="buddy-routing-") as directory:
        main.store = ConversationStore(Path(directory))
        with TestClient(main.app) as client:
            topics = args.topic or ["logistic regression", "decision trees"]
            if args.controls:
                topics.append("the exact amount of RAM installed in my laptop")
            for topic in topics:
                traces.clear()
                started = time.monotonic()
                response = client.post("/api/chat", json={
                    "model": args.model, "document_ids": [args.document],
                    "message": "What does the material say about " + topic + "?"})
                data = response.json()
                row = {"model": args.model, "topic": topic, "seconds": round(time.monotonic() - started, 2),
                       "status": response.status_code, "response": data, "traces": list(traces)}
                if response.status_code == 200:
                    saved = main.store.load(data["conversation_id"])[-1]
                    row["routing"] = saved.get("routing")
                    row["review"] = saved.get("material_review")
                rows.append(row)
                timings = defaultdict(float)
                for call in data.get("usage", {}).get("calls", []):
                    if "wall_seconds" in call:
                        timings[call["stage"]] += call["wall_seconds"]
                row["stage_seconds"] = {stage: round(seconds, 3) for stage, seconds in timings.items()}
                args.output.write_text(json.dumps(rows, indent=2))
                print(json.dumps({"model": args.model, "topic": topic, "status": response.status_code,
                    "seconds": row["seconds"], "sources": len(data.get("sources", [])),
                    "answer": data.get("message", data.get("detail"))}), flush=True)


if __name__ == "__main__":
    run()
