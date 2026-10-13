"""Stateful real-model smoke test using an isolated store and the user's library."""
import argparse
import asyncio
import json
import tempfile
from pathlib import Path

from app.agents.chat_agent import ChatAgent
from app.config import settings
from app.llm.ollama_client import OllamaClient
from app.storage.conversation_store import ConversationStore


async def run(args):
    if args.output.exists():
        raise ValueError("Choose a fresh report path.")
    report = {"model": settings.ollama_model, "context_window": settings.context_window, "turns": []}
    with tempfile.TemporaryDirectory(prefix="buddy-routing-") as directory:
        store = ConversationStore(Path(directory))
        cid = store.create_id()
        state = {"version": 2, "active": True, "paused": False, "phase": "question",
                 "pending_question": "How do nearest distances compare with average distances in high dimensions?",
                 "question_id": "ownership-test", "options": ["Usually similar", "Always zero", "Always infinite", "No distances exist"],
                 "cursor": 1, "total": 10, "document_ids": [args.document_id],
                 "results": [{"number": 1, "verdict": "correct", "question": "Earlier question"}]}
        store.save(cid, [{"role": "user", "content": "Explain the book's low versus high dimensional distance comparison."},
                         {"role": "assistant", "content": "In high dimensions nearest points often are not much closer than average.",
                          "material_review": {"resolved_request": "Explain low versus high dimensional distances in the book."}}],
                   document_ids=[args.document_id], quiz=state)
        agent = ChatAgent(OllamaClient(settings.ollama_url, settings.ollama_model), store)
        for message, expected in [("Let's pause the quiz and just chat for a minute.", "paused"),
                                  ("how r u?", "paused"), ("Let's resume the quiz where we left off.", "resumed")]:
            row = {"message": message, "expected": expected}
            try:
                _, row["response"] = await agent.reply(message, cid, materials_root=args.materials,
                                                       document_ids=[args.document_id])
                saved = store.quiz(cid)
                row["state"] = saved
                row["usage"] = store.load(cid)[-1].get("usage", {})
                stages = [c["stage"] for c in row["usage"].get("calls", [])]
                row["passed"] = (saved["results"] == state["results"] and saved["cursor"] == state["cursor"]
                    and saved["pending_question"] == state["pending_question"]
                    and bool(saved.get("paused")) == (expected == "paused")
                    and bool(saved.get("active")) == (expected == "resumed")
                    and "retrieval plan" not in stages and not store.load(cid)[-1].get("sources"))
            except Exception as exc:
                row.update(error=str(exc), passed=False)
            report["turns"].append(row)
            print(json.dumps(row), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--materials", type=Path, required=True)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))
