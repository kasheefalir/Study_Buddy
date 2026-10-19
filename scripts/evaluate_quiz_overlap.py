"""Replay a narrow overlap exception, then test the unchanged semantic gate."""
import asyncio
import argparse
import json
from pathlib import Path
import re
import time

import httpx

from app.agents.quiz import choice_question_problem, choice_quality_problem
from app.agents.local_study.runtime import LocalRuntime
from app.config import settings
from app.llm.ollama_client import OllamaClient


class RecordedClient(OllamaClient):
    async def structured_plan(self, messages, schema):
        self.last_request = messages
        self.last_raw = None
        self.last_raw = await super().structured_plan(messages, schema)
        return self.last_raw


async def exclusive(model):
    async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=180) as client:
        response = await client.get("/api/ps")
        response.raise_for_status()
        for item in response.json()["models"]:
            if item["name"] not in {model, settings.embedding_model, settings.embedding_model + ":latest"}:
                result = await client.post("/api/generate", json={"model": item["name"], "keep_alive": 0})
                result.raise_for_status()


def distinguishing_answer(data):
    # Function words and generic verbs cannot rescue a near-echo.
    framing = {"the", "and", "for", "with", "from", "that", "this", "are", "was",
               "were", "has", "have", "had", "does", "can", "will", "would", "could",
               "should", "not", "only", "always", "never", "used", "use", "using", "being"}
    def terms(text):
        return set(re.findall(r"\w{3,}", text.casefold())) - framing
    answer = data["correct_answer"]
    new = terms(answer) - terms(data["question"])
    others = set().union(*(terms(option) for option in data["options"] if option != answer))
    return bool(new - others)


def candidate_problem(data):
    problem = choice_question_problem(data)
    if problem.startswith("The correct option mostly repeats") and distinguishing_answer(data):
        return ""
    return problem


async def run(args):
    output = args.output
    if output.exists():
        raise ValueError("Report already exists")
    previous = json.loads(Path("data/study-reviews/quiz-speed-accuracy-20261016.json").read_text())
    changes = [{"row": i, "data": r["result"], "old": choice_question_problem(r["result"]),
                "new": candidate_problem(r["result"])} for i, r in enumerate(previous["rows"])
               if "result" in r and choice_question_problem(r["result"]) != candidate_problem(r["result"])]
    valid = changes[0]["data"]
    source = "Standardization subtracts the training mean and divides by the training standard deviation. Apply those same training statistics to the test data. Do not fit preprocessing on test data; doing so leaks information from the test set."
    wrong = dict(valid, correct_answer=valid["options"][2], expected_answer="Use the validation set's own statistics.")
    duplicate = dict(valid, options=[valid["options"][0], valid["correct_answer"],
                                    "Use the training mean and training standard deviation.", valid["options"][3]])
    report = {"replayed": len(previous["rows"]), "changed": changes, "checks": [],
              "context": settings.context_window, "output_limit": settings.response_tokens,
              "thinking": "GPT-OSS low; others request false", "source": source}
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        for model in args.models:
            await exclusive(model)
            llm = RecordedClient(settings.ollama_url, model, timeout=180)
            await llm.preload()
            for repeat in range(2):
                for name, data, expected in (("valid", valid, True), ("wrong_key", wrong, False),
                                             ("overlapping", duplicate, False)):
                    row = {"model": model, "repeat": repeat, "case": name, "expected_accept": expected,
                           "old_structural_issue": choice_question_problem(data),
                           "candidate_structural_issue": candidate_problem(data)}
                    started = time.monotonic()
                    try:
                        from scripts.evaluate_quiz_overlap_holdouts import baseline_check, trial_check
                        check = baseline_check
                        if args.trial:
                            check = trial_check
                        issue = await check(llm, data, [{"chunk_id": 1, "location": "Test scaling", "text": source}])
                        row.update(accepted=not bool(issue), issue=issue)
                    except Exception as exc:
                        row.update(accepted=None, error=str(exc))
                    row.update(seconds=round(time.monotonic() - started, 3),
                               request=llm.last_request, raw=llm.last_raw)
                    report["checks"].append(row)
                    output.write_text(json.dumps(report, indent=2))
                    print(json.dumps({k: v for k, v in row.items() if k not in {"request", "raw"}}), flush=True)
    finally:
        await LocalRuntime("llama3.2:3b").exclusive()
        await OllamaClient(settings.ollama_url, "llama3.2:3b").preload()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/study-reviews/quiz-overlap-contrast-20261016.json"))
    parser.add_argument("--models", nargs="+", choices=["llama3.2:3b", "phi4-mini:latest", "gpt-oss:20b", "gemma4:31b-cloud"], default=["llama3.2:3b", "phi4-mini:latest"])
    parser.add_argument("--trial", action="store_true", help="Test the larger-model candidate checker, not the production prompt")
    asyncio.run(run(parser.parse_args()))
