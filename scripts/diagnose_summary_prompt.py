"""Isolated summary routing probe; output stays in local evaluation storage."""
import json
import argparse
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from app import main
from app.storage.conversation_store import ConversationStore
from app.llm.ollama_client import OllamaClient
from app.agents.grounded_answer import GroundedAnswer
from app.llm.structured_output import validated_output


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Choose a new report path")
    original = OllamaClient.structured_plan
    traces = []

    async def traced(self, messages, schema):
        raw = await original(self, messages, schema)
        row = {"schema": schema.get("title"), "raw": raw}
        if schema.get("title") == "GroundedAnswer":
            try:
                validated_output(raw, GroundedAnswer)
            except (ValueError, TypeError) as exc:
                row["validation_error"] = str(exc)
        traces.append(row)
        print(json.dumps(row), flush=True)
        return raw

    OllamaClient.structured_plan = traced
    rows = []
    with tempfile.TemporaryDirectory() as folder:
        main.store = ConversationStore(Path(folder))
        with TestClient(main.app) as client:
            for prompt in ["Summarize the selected study material.", "what does the selected material talk about"] * args.repeats:
                traces.clear()
                response = client.post("/api/chat", json={"model": "gemma4:31b-cloud",
                    "message": prompt, "task": "auto", "document_ids": ["5c1201a526914c8c9fde7a69fc1bfb4c"]})
                rows.append({"prompt": prompt, "status": response.status_code,
                             "response": response.json(), "traces": list(traces)})
                target = args.output
                target.parent.mkdir(exist_ok=True, parents=True)
                target.write_text(json.dumps(rows, indent=2))
                print("STATUS", response.status_code, flush=True)


if __name__ == "__main__":
    run()
