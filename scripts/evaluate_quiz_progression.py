"""Replay a saved answered quiz in isolation, then exercise advancement with Ollama."""
import argparse
import asyncio
import json
import tempfile
import time
from pathlib import Path

from app.agents.chat_agent import ChatAgent
from app.config import settings
from app.llm.ollama_client import OllamaClient
from app.storage.conversation_store import ConversationStore


async def run(args):
    original = json.loads(args.session.read_text())
    report = {"model": args.model, "cases": []}
    with tempfile.TemporaryDirectory(prefix="buddy-quiz-regression-") as directory:
        store = ConversationStore(Path(directory))
        agent = ChatAgent(OllamaClient(settings.ollama_url, args.model, settings.request_timeout_seconds), store)
        for explicit in ((True,) if args.fresh else (False, True)):
            cid = store.create_id()
            # The last two entries are the reported failed advancement, not new evidence.
            store.save(cid, original["messages"][:-2], document_ids=original["document_ids"], quiz=original["quiz"])
            previous = original["quiz"]["pending_question"]
            row = {"explicit_button": explicit, "turns": []}
            try:
                if args.fresh:
                    store.save(cid, [], document_ids=original["document_ids"], quiz={})
                    started = time.monotonic()
                    await agent.reply("Create a five question multiple choice quiz on the selected material", cid,
                                      materials_root=settings.data_dir / "documents", document_ids=original["document_ids"], task="quiz")
                    prepared = store.quiz(cid)
                    row["preparation_seconds"] = round(time.monotonic() - started, 2)
                    assert len(prepared["prepared_questions"]) == 5
                    assert all(len(q["options"]) == 4 for q in prepared["prepared_questions"])
                    assert prepared["results"] == [] and prepared["cursor"] == 0
                    row["prepared_questions"] = prepared["prepared_questions"]
                    previous = prepared["pending_question"]
                    print(f"Prepared all five questions in {row['preparation_seconds']} seconds", flush=True)
                    await agent.reply("ABCD"[prepared["correct_index"]], cid,
                                      materials_root=settings.data_dir / "documents", document_ids=original["document_ids"],
                                      quiz_question_id=prepared["question_id"])
                while store.quiz(cid)["phase"] != "complete":
                    before = store.quiz(cid)
                    kwargs = {"next_question_id": before["question_id"]} if explicit else {}
                    _, text = await agent.reply("Next question", cid, materials_root=settings.data_dir / "documents",
                                                document_ids=original["document_ids"], task="quiz", **kwargs)
                    question = store.quiz(cid)
                    if args.fresh:
                        assert not store.load(cid)[-1].get("usage", {}).get("calls"), "Next must not call the model"
                    assert question["cursor"] == before["cursor"] + 1, text
                    assert question["pending_question"] != previous, text
                    assert len(question["options"]) == 4, text
                    assert store.load(cid)[-1]["quiz_question"]["id"] == question["question_id"]
                    previous = question["pending_question"]
                    row["turns"].append({"question": previous, "options": question["options"], "number": question["cursor"] + 1})
                    print(json.dumps(row["turns"][-1]), flush=True)
                    answer = "ABCD"[question["correct_index"]]
                    await agent.reply(answer, cid, materials_root=settings.data_dir / "documents",
                                      document_ids=original["document_ids"], quiz_question_id=question["question_id"])
                    assert store.quiz(cid)["results"][-1]["verdict"] == "correct"
                    if not explicit:
                        break
                row["passed"] = True
                row["final_phase"] = store.quiz(cid)["phase"]
            except Exception as exc:
                row.update(passed=False, error=str(exc))
            report["cases"].append(row)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--model", default="phi4-mini:latest")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fresh", action="store_true")
    asyncio.run(run(parser.parse_args()))
