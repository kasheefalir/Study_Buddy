"""Same production quiz mechanics, synthetic evidence, sequential model calls.

Starts from a fixed five-question plan to isolate quiz generation/playback from
request routing and retrieval. This is not a browser or intent-routing test.
Selection correctness is measured against the generated key, not assumed truth.
Human review of question/key/feedback accuracy is required before promotion.
"""
import argparse
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import time

import httpx

from app.agents.quiz import quiz_turn, public_question, coverage_windows, select_windows
from app.agents.study_tools import library, OUTPUTS
from app.config import settings
from app.llm.ollama_client import OllamaClient
from app.storage.conversation_store import ConversationStore

MODELS = ["llama3.2:3b", "phi4-mini:latest", "gpt-oss:20b", "gemma4:31b-cloud"]
IDENTIFIER = "a" * 32


class TraceClient(OllamaClient):
    def __init__(self, model):
        super().__init__(settings.ollama_url, model, timeout=240)
        self.calls = []

    async def chat(self, messages, **kwargs):
        row = {"schema": (kwargs.get("schema") or {}).get("title"), "request": messages}
        start = time.monotonic()
        try:
            row["raw"] = await super().chat(messages, **kwargs)
            return row["raw"]
        except Exception as exc:
            row["error"] = str(exc)
            raise
        finally:
            row["seconds"] = round(time.monotonic() - start, 3)
            self.calls.append(row)


class FormatRepairClient(TraceClient):
    async def structured_plan(self, messages, schema):
        validator = next(value for value in OUTPUTS.values() if value.__name__ == schema["title"])
        raw = await super().structured_plan(messages, schema)
        try:
            validator.model_validate_json(raw)
        except ValueError as exc:
            errors = [{"field": list(e["loc"]), "message": e["msg"]} for e in exc.errors()]
            repair = {"format_errors": errors,
                      "instruction": "Repair the response format only. Return one JSON object with the required fields directly at its root, no properties wrapper and no Markdown fences. Obey field length limits. Preserve the question, options, correct answer and source meaning. Shorten an overlong summary without adding facts."}
            raw = await super().structured_plan([*messages, {"role": "assistant", "content": raw},
                                                {"role": "user", "content": json.dumps(repair)}], schema)
            validator.model_validate_json(raw)
        return raw


def fixture(root):
    facts = json.loads(Path("tests/fixtures/quiz_comparison_material.json").read_text())
    item = {"id": IDENTIFIER, "name": "Synthetic statistics study notes", "status": "Ready", "kind": "file"}
    (root / IDENTIFIER).mkdir(parents=True)
    (root / (IDENTIFIER + ".json")).write_text(json.dumps(item))
    chunks = [{"id": i + 1, "text": fact["text"], "chapter": fact["heading"],
               "location": "Section " + str(i + 1)} for i, fact in enumerate(facts)]
    (root / IDENTIFIER / "chunks.json").write_text(json.dumps(chunks))
    available = coverage_windows(root, library(root, [IDENTIFIER]))
    return {"version": 2, "active": True, "document_ids": [IDENTIFIER], "total": 5,
            "cursor": 0, "results": [], "phase": "question", "pending_question": "",
            "focus": "", "format": "multiple_choice", "guidelines": "Five conceptual multiple-choice questions, one at a time.",
            "window_plan": select_windows(available, 5), "window_reviews": [],
            "available_windows": len(available), "plan_version": 2, "turns": 0}


async def sequence(root, initial, model, prepared, repair_format=False):
    llm = (FormatRepairClient if repair_format else TraceClient)(model)
    result = {"model": model, "mode": "prepared" if prepared else "incremental",
              "repair_format": repair_format, "turns": [], "calls": llm.calls}
    state = deepcopy(initial)
    store = ConversationStore(root / "conversations")
    cid = store.create_id()
    history = []

    async def turn(name, message, action=None):
        nonlocal state, history
        before = deepcopy(state)
        started = time.monotonic()
        row = {"name": name, "message": message}
        result["turns"].append(row)
        count = len(llm.calls)
        try:
            text, state, sources = await quiz_turn(root, [IDENTIFIER], message, state, llm,
                recent=history, activity_action=action, prepare_all=prepared)
            row.update(text=text, question=public_question(state), sources=sources, state=deepcopy(state))
            history.extend([{"role": "user", "content": message}, {"role": "assistant", "content": text or ""}])
            store.save(cid, history, document_ids=[IDENTIFIER], quiz=state)
            state = ConversationStore(root / "conversations").quiz(cid)
            assert state == row["state"], "Quiz did not survive storage reload"
        except Exception as exc:
            row["error"] = str(exc)
            row["input_state_preserved"] = before == state
            raise
        finally:
            row["seconds"] = round(time.monotonic() - started, 3)
            row["model_calls"] = len(llm.calls) - count
            print(json.dumps({"model": model, "mode": result["mode"], "turn": name,
                              "seconds": row["seconds"], "error": row.get("error")}), flush=True)

    try:
        await turn("start", "Next question", "next")
        ids = set()
        for number in range(1, 6):
            assert state["cursor"] == number - 1 and len(state["options"]) == 4
            assert state["question_id"] not in ids, "Repeated question ID"
            ids.add(state["question_id"])
            assert "correct_index" not in public_question(state), "Pending key exposed"
            index = state["correct_index"]
            if number in (1, 3):
                index = (index + 1) % 4
            await turn("answer_" + str(number), "ABCD"[index])
            assert len(state["results"]) == number
            expected = "incorrect" if number in (1, 3) else "correct"
            assert state["results"][-1]["verdict"] == expected
            if number < 5:
                await turn("next_" + str(number + 1), "Next question", "next")
        assert state["phase"] == "complete" and not state["active"]
        assert sum(r["verdict"] == "correct" for r in state["results"]) == 3
        last = deepcopy(state)
        await turn("after_complete", "Next question", "next")
        assert state == last, "Completion advanced or discarded the final question"
        await turn("missed_review", "Review missed answers", "review")
        review = result["turns"][-1]["text"]
        assert state == last
        assert all(r["question"] in review for r in state["results"] if r["verdict"] == "incorrect")
        result["mechanics_passed"] = True
    except Exception as exc:
        result.update(mechanics_passed=False, error=str(exc))
    result["completed_answers"] = len(state.get("results", []))
    result["final_state"] = state
    result["factual_quality"] = "Requires independent manual review; mechanics success is not factual success"
    return result


async def run(args):
    if args.output.exists():
        raise ValueError("Choose a new report filename")
    if (settings.context_window, settings.response_tokens, settings.ollama_think) != (8192, 2048, "false"):
        raise ValueError("Run with CONTEXT_WINDOW=8192 RESPONSE_TOKENS=2048 OLLAMA_THINK=false")
    report = {"protocol": __doc__, "fixture": "tests/fixtures/quiz_comparison_material.json",
              "options": {"num_ctx": 8192, "num_predict": 2048, "temperature": 0.2},
              "thinking": "GPT-OSS low; other models false, provider support may differ", "results": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=240) as client:
        for model in args.models:
            resident = await client.get("/api/ps")
            resident.raise_for_status()
            for other in resident.json()["models"]:
                if other["name"] != model and not other["name"].startswith("nomic-embed-text"):
                    response = await client.post("/api/generate", json={"model": other["name"], "keep_alive": 0})
                    response.raise_for_status()
            with tempfile.TemporaryDirectory(prefix="buddy-quiz-comparison-") as directory:
                root = Path(directory)
                initial = fixture(root)
                result = await sequence(root, initial, model, args.prepared, args.repair_format)
            report["results"].append(result)
            args.output.write_text(json.dumps(report, indent=2))
            print(json.dumps({k: v for k, v in result.items() if k not in {"turns", "calls", "final_state"}}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--models", nargs="+", choices=MODELS, default=MODELS)
    parser.add_argument("--prepared", action="store_true")
    parser.add_argument("--repair-format", action="store_true", help="Experimental one-retry schema repair; separate from baseline")
    asyncio.run(run(parser.parse_args()))
