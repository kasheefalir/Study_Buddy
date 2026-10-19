"""Replay a quiz request on private conversation copies, preserving the original."""
import argparse
import json
import shutil
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.storage.conversation_store import ConversationStore


def run(args):
    if args.output.exists():
        raise ValueError("Choose a new report path")
    original = main.OllamaClient.structured_plan
    traces, rows = [], []

    async def traced(self, messages, schema):
        raw = await original(self, messages, schema)
        traces.append({"schema": schema.get("title"), "raw": raw})
        return raw

    main.OllamaClient.structured_plan = traced
    original_path = main.store._path(args.conversation)
    payload = json.loads(original_path.read_text())
    for model in args.model:
        with tempfile.TemporaryDirectory() as directory:
            shutil.copyfile(original_path, Path(directory) / original_path.name)
            main.store = ConversationStore(Path(directory))
            traces.clear()
            started = time.monotonic()
            with TestClient(main.app) as client:
                response = client.post("/api/chat", json={
                    "conversation_id": args.conversation, "message": args.message,
                    "document_ids": payload.get("document_ids", []), "model": model})
                state = main.store.quiz(args.conversation)
                row = {"model": model, "status": response.status_code,
                       "seconds": round(time.monotonic() - started, 2),
                       "response": response.json(), "traces": list(traces),
                       "prepared_count": len(state.get("prepared_questions", [])),
                       "total": state.get("total"), "cursor": state.get("cursor")}
                rows.append(row)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(rows, indent=2))
                print(json.dumps({k: v for k, v in row.items() if k not in {"traces", "response"}}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--message", default="quiz me on logistic regression")
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())
