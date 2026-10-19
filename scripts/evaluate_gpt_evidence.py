"""Broader paired native-GPT trial using local materials; never edits user chats."""
import asyncio
import argparse
import json
import time
from pathlib import Path

from app.config import settings
from app.agents.study_tools import passages, coherent_passages
from app.agents.gpt.evidence_trial import independent_candidates, audit_answer, literal_issues
from scripts.evaluate_gpt_tools import ToolTrial, SearchArgs

BOOK = "3a4c66034f8a4b6cba7320b89e254ff5"
R = "8d9fd23ca9ed45be98ead5736b14d7a7"
SLIDES = "5c1201a526914c8c9fde7a69fc1bfb4c"
CASES = [
    ("greeting", BOOK, "Hey, how are you?", [], False),
    ("centrality", BOOK, "What does betweenness centrality measure according to the book?", [675], False),
    ("followup", BOOK, "Can you explain that more simply?", [675], True),
    ("comparison", BOOK, "Compare degree centrality with betweenness centrality according to the book.", [86, 675], False),
    ("missing_laptop", BOOK, "What exact laptop model and RAM capacity did Joel Grus use to write this book? Answer only if explicitly stated.", [], False),
    ("r_comparison", R, "According to this tutorial, how does using the command line compare with scripts for repeated analyses?", [2, 3], False),
    ("r_execution", R, "What keyboard shortcut and button does the tutorial give for executing R code?", [8], False),
    ("r_missing", R, "What exact RStudio version number was used to write this tutorial?", [], False),
    ("fare", SLIDES, "In the homework example, how much does fare change per additional mile and for routes served by Southwest, holding other variables constant?", [3], False),
    ("classification", SLIDES, "What are the stated accuracy, sensitivity, and specificity for the loan-classification example?", [11, 12], False),
    ("errors", SLIDES, "Compare Type I and Type II errors in the loan confusion matrix, including their counts.", [12], False),
    ("slides_missing", SLIDES, "What exact random seed was used to split the loan dataset into training and test sets?", [], False),
]


class EvidenceTrial(ToolTrial):
    def __init__(self, root, ids):
        super().__init__(root, ids, evidence_policy=True)
        self.retrieval_log = []
        self.messages[0]["content"] += (
            " Prefer concise explanations. Never use quotation marks for paraphrases. "
            "If facts are unsupported, explicitly say the retrieved evidence does not establish them.")

    async def execute(self, name, arguments):
        if name != "search_materials":
            raise ValueError("Unknown tool")
        args = SearchArgs.model_validate(arguments)
        if args.document_id not in self.books:
            raise ValueError("Material outside selected scope")
        item, chunks = self.books[args.document_id]
        hits, trace = await independent_candidates(self.root, item, chunks, args.query)
        selected = coherent_passages(chunks, 6, hits)
        trace["context_ids"] = [c["id"] for c in selected]
        self.retrieval_log.append(trace)
        found = []
        for source in passages(item, selected):
            key = (source["document_id"], source.get("chunk_id"), source["location"])
            if key not in self.sources:
                self.sources[key] = {**source, "label": f"S{len(self.sources) + 1}"}
            found.append(self.sources[key])
        return found

    async def checked_turn(self, question):
        draft = await self.turn(question)
        audits = [await audit_answer(question, draft["answer"], draft["sources"])]
        attempts = [draft]
        if audits[-1]["errors"]:
            correction = ("Revise your answer to my previous question. The evidence audit found these issues: "
                          + json.dumps(audits[-1]["errors"]) +
                          ". Search again if necessary. Remove unsupported claims and fabricated quotes. "
                          "If evidence is still insufficient, say what is missing from retrieved evidence.")
            draft = await self.turn(correction)
            attempts.append(draft)
            audits.append(await audit_answer(question, draft["answer"], draft["sources"]))
        rejected = bool(audits[-1]["errors"])
        answer = ("I could not verify an answer against the retrieved evidence."
                  if rejected else draft["answer"])
        if rejected:
            self.messages[-1]["content"] = answer
        return {**draft, "answer": answer, "attempts": attempts, "audits": audits,
                "forced_abstention": rejected, "retrieval_log": list(self.retrieval_log)}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output", default="data/study-reviews/gpt-evidence-broad.json")
    args = parser.parse_args()
    path = Path(args.output)
    if path.exists() and not args.resume:
        raise ValueError("Report already exists; choose a new --output or use --resume")
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = json.loads(path.read_text()) if args.resume and path.exists() else []
    completed = {(row["mode"], row["name"]) for row in rows}
    for mode in ("baseline", "candidate"):
        trial = None
        for name, doc, question, gold, followup in CASES:
            if (mode, name) in completed:
                continue
            if not followup:
                trial = (EvidenceTrial(settings.data_dir / "documents", [doc]) if mode == "candidate"
                         else ToolTrial(settings.data_dir / "documents", [doc], True, True))
            if trial is None:
                raise ValueError("Resume before a follow-up requires rerunning its preceding case")
            started = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    trial.checked_turn(question) if mode == "candidate" else trial.turn(question), 360)
                ids = {s["chunk_id"] for s in result["sources"]}
                result["gold_ids_present"] = sorted(ids & set(gold))
                result["gold_ids_expected"] = gold
                result["literal_issues"] = literal_issues(result["answer"], result["sources"])
            except Exception as exc:
                result = {"error": type(exc).__name__ + ": " + str(exc)}
            row = {"mode": mode, "name": name, "question": question,
                   "seconds": round(time.monotonic() - started, 2), **result}
            rows.append(row)
            path.write_text(json.dumps(rows, indent=2))
            print(json.dumps({key: row[key] for key in ("mode", "name", "seconds", "answer", "error", "forced_abstention", "gold_ids_present", "literal_issues") if key in row}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
