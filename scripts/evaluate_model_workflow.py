"""Exercise real Ollama through the app API with isolated conversation storage."""
import argparse
import json
from pathlib import Path
import tempfile
import time

from fastapi.testclient import TestClient
from app import main
from app.storage.conversation_store import ConversationStore


def run(args):
    report = {"model": args.model, "turns": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="buddy-model-workflow-") as directory:
        main.store = ConversationStore(Path(directory))
        client = TestClient(main.app)
        cid = None

        def turn(name, message, **extra):
            nonlocal cid
            started = time.monotonic()
            payload = {"message": message, "model": args.model,
                       "document_ids": [args.document_id], **extra}
            if cid:
                payload["conversation_id"] = cid
            response = client.post("/api/chat", json=payload)
            data = response.json()
            row = {"name": name, "request": message, "seconds": round(time.monotonic() - started, 2),
                   "http_status": response.status_code, "response": data}
            if response.status_code == 200:
                cid = data["conversation_id"]
                row["quiz_state"] = main.store.quiz(cid)
                row["workflow"] = main.store.load(cid)[-1].get("material_review", {})
            report["turns"].append(row)
            args.output.write_text(json.dumps(report, indent=2))
            print(json.dumps({"name": name, "seconds": row["seconds"], "status": response.status_code,
                              "message": data.get("message", data.get("detail")),
                              "sources": len(data.get("sources", [])),
                              "stages": [c.get("stage") for c in data.get("usage", {}).get("calls", [])]}), flush=True)
            return data if response.status_code == 200 else None

        probes = {"greeting": "Hey, how are you?",
                  "narrow_fact": "According to the book, what does betweenness centrality measure?",
                  "followup": "Can you explain that more simply?",
                  "missing_fact": "What exact laptop model and RAM capacity did Joel Grus use to write this book? Answer only if the book explicitly says."}
        selected = getattr(args, "cases", None) or [*probes, "quiz_start"]
        for name, message in probes.items():
            if name in selected:
                turn(name, message)
        cid = None
        question = turn("quiz_start", "Create a two-question multiple-choice quiz on the selected material.", task="quiz") if "quiz_start" in selected else None
        if question:
            state = main.store.quiz(cid)
            if state.get("total") == 2 and state.get("pending_question"):
                if args.interrupt:
                    turn("pause", "Let's pause the quiz. How are you doing?")
                    turn("resume", "Let's resume the quiz where we left off.")
                for number in range(2):
                    state = main.store.quiz(cid)
                    index = state["correct_index"] if number else (state["correct_index"] + 1) % 4
                    result = turn(f"answer_{number + 1}", "ABCD"[index], quiz_question_id=state["question_id"])
                    if not result:
                        break
                    if number == 0:
                        if not turn("quiz_next", "Next question", next_question_id=state["question_id"]):
                            break
                turn("missed_review", "Review missed answers")
            else:
                report["quiz_error"] = "Did not start a two-question quiz"
        args.output.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interrupt", action="store_true", help="Probe pause/resume before answering the first question")
    parser.add_argument("--cases", nargs="+", choices=["greeting", "narrow_fact", "followup", "missing_fact", "quiz_start"])
    run(parser.parse_args())
