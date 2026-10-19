"""Isolated single-call prompt trial, not a production quiz or retrieval benchmark."""
import argparse
import asyncio
import json
from pathlib import Path
import time

from app.agents.quiz import ChoiceQuestion, WINDOW_PROMPT, choice_question_problem
from app.agents.study_tools import structured_messages
from app.agents.local_study.runtime import LocalRuntime
from app.config import settings
from app.llm.ollama_client import OllamaClient
from app.llm.structured_output import validated_output


BASELINE = WINDOW_PROMPT + (
    " Provide four distinct plausible options without letter prefixes and exactly one defensible correct option. "
    "Copy its exact option text verbatim into correct_answer. Never supply an option number. "
    "Do not include synonymous options or reveal the answer in the question. "
    "Before returning, compare every option with the other three so that no two choices state the same answer."
)
COMPACT = (
    "Create one conceptual multiple-choice question from the source, not a conversation. "
    "Follow the requested focus. Test one idea with four distinct choices answering the same question. "
    "Exactly one choice must be correct; copy that choice verbatim into correct_answer. "
    "Avoid overlapping choices, letter prefixes, unsupported absolutes, and numerical calculations. "
    "Keep summary to one short sentence. In expected_answer explain why the key follows from the source "
    "in at most two sentences. Preserve qualifications such as 'generally' and 'alone'. "
    "If a fixed question and options are supplied, copy them unchanged and choose the supported key."
)


def checked_result(case, result):
    """Checks the independent key and fixed contract, not semantic explanation truth."""
    return {
        "stem_preserved": result["question"] == case["question"],
        "options_preserved": result["options"] == case["options"],
        "key_correct": result["correct_answer"] == case["correct_answer"],
    }


async def run(args):
    if args.output.exists():
        raise ValueError("Use a new report path")
    cases = json.loads(Path("tests/fixtures/quiz_accuracy_cases.json").read_text())
    report = {"protocol": __doc__, "context": settings.context_window,
              "output_limit": settings.response_tokens, "repeats": args.repeats,
              "prompts": {"baseline": BASELINE, "compact": COMPACT}, "rows": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        for model in args.models:
            await LocalRuntime(model).exclusive()
            client = OllamaClient(settings.ollama_url, model, timeout=180)
            await client.preload()
            for repeat in range(args.repeats):
                variants = [("baseline", BASELINE), ("compact", COMPACT)]
                if repeat % 2:
                    variants.reverse()
                for case in cases:
                    for variant, prompt in variants:
                        for mode in ("fixed", "generated"):
                            data = {"sources": [{"source_id": "SOURCE_001", "text": case["source"]}],
                                    "focus": case["question"]}
                            instruction = prompt
                            if mode == "fixed":
                                data.update(fixed_question=case["question"], fixed_options=case["options"])
                                instruction += " Copy fixed_question and fixed_options unchanged; select the supported answer."
                            messages = structured_messages("quiz choices", instruction, data)
                            row = {"model": model, "repeat": repeat, "case": case["id"],
                                   "variant": variant, "mode": mode, "request": messages}
                            start = time.monotonic()
                            try:
                                raw = await client.structured_plan(messages, ChoiceQuestion.model_json_schema())
                                row["raw"] = raw
                                result = validated_output(raw, ChoiceQuestion).model_dump()
                                row["result"] = result
                                row["structural_issue"] = choice_question_problem(result)
                                if mode == "fixed":
                                    row["checks"] = checked_result(case, result)
                                row["factual_review"] = "Manual review required; valid format/key match is not proof of explanation accuracy."
                            except Exception as exc:
                                row["error"] = str(exc)
                            row["seconds"] = round(time.monotonic() - start, 3)
                            report["rows"].append(row)
                            args.output.write_text(json.dumps(report, indent=2))
                            print(json.dumps({k: v for k, v in row.items() if k not in {"request", "raw", "result"}}), flush=True)
    finally:
        await LocalRuntime("llama3.2:3b").exclusive()
        await OllamaClient(settings.ollama_url, "llama3.2:3b").preload()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--models", nargs="+", default=["llama3.2:3b", "phi4-mini:latest"])
    parser.add_argument("--repeats", type=int, default=2)
    asyncio.run(run(parser.parse_args()))
