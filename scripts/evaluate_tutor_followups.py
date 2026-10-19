"""Production routing plus isolated writer probes on synthetic, fixed evidence.

This is not an end-to-end retrieval test. No uploaded materials or cloud calls.
Both writer variants receive identical evidence and production planner outputs.
"""
import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx

from app.agents.chat_agent import ROUTER_PROMPT, RETRIEVAL_PLAN_PROMPT
from app.agents.study_tools import structured
from app.agents.local_study.bounded_tutor import messages, TutoringAnswer, attach_references
from app.config import settings
from app.llm.ollama_client import OllamaClient

MODELS = ("llama3.2:3b", "phi4-mini:latest")
QUESTIONS = (
    "What does R-squared of 0.8 mean in this material?",
    "Explain that more simply.",
    "Give me a hypothetical example of that.",
    "How do I train logistic regression for spam classification?",
)


async def run(args):
    if args.output.exists():
        raise ValueError("Choose a new report path; preserve earlier results")
    source = json.loads(Path("tests/fixtures/bounded_tutor_cases.json").read_text())[0]["text"]
    evidence = [{"document_id": "a" * 32, "chunk_id": 1, "location": "Synthetic passage", "text": source}]
    report = {"protocol": __doc__, "rows": [], "repeats": args.repeats,
              "writer_options": {"num_ctx": 4096, "num_predict": 1200, "temperature": 0.1},
              "route_options": {"num_ctx": settings.context_window, "num_predict": settings.response_tokens,
                                "temperature": 0.2},
              "grading": "Manual factual grading required; valid JSON and quotes do not establish correctness"}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(report, indent=2))

    async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=180) as client:
        for model in MODELS:
            resident = await client.get("/api/ps")
            resident.raise_for_status()
            for other in resident.json()["models"]:
                if other["name"] != model and not other["name"].startswith("nomic-embed-text"):
                    response = await client.post("/api/generate", json={"model": other["name"], "keep_alive": 0})
                    response.raise_for_status()
            llm = OllamaClient(settings.ollama_url, model, timeout=180)
            for repeat in range(args.repeats):
                history, last_request = [], ""
                for turn, question in enumerate(QUESTIONS):
                    row = {"model": model, "repeat": repeat, "turn": turn, "question": question, "writers": {}}
                    data = {"latest_message": question, "last_material_request": last_request,
                            "recent_dialogue": history[-3:],
                            "selected_materials": [{"id": "a" * 32, "title": "Regression study notes", "kind": "file", "url": ""}],
                            "unfinished_activity": {"mode": "chat", "quiz_active": False, "quiz_paused": False,
                                                    "phase": "", "pending_question": ""}, "explicit_task": "auto"}
                    try:
                        row["route"] = await structured(llm, "intent route", ROUTER_PROMPT, data)
                        if row["route"]["route"] == "retrieve":
                            row["planner"] = await structured(llm, "retrieval plan", RETRIEVAL_PLAN_PROMPT,
                                {**data, "intent": row["route"], "previous_evidence": evidence if history else []})
                        resolved = row.get("planner", {}).get("query", "")
                        # Alternate order to reduce a consistent warm-cache advantage.
                        variants = ("baseline", "resolved") if repeat % 2 == 0 else ("resolved", "baseline")
                        for variant in variants:
                            start = time.monotonic()
                            result = {}
                            row["writers"][variant] = result
                            try:
                                request = messages(question, evidence, True,
                                    resolved_question=resolved if variant == "resolved" else None)
                                response = await client.post("/api/chat", json={"model": model, "messages": request,
                                    "format": TutoringAnswer.model_json_schema(), "stream": False,
                                    "keep_alive": "5m", "options": report["writer_options"]})
                                response.raise_for_status()
                                body = response.json()
                                result["raw"] = body["message"]["content"]
                                if not body.get("done") or body.get("done_reason") == "length":
                                    raise ValueError("Incomplete completion")
                                answer = TutoringAnswer.model_validate_json(result["raw"])
                                result["answer"] = answer.model_dump()
                                result["rendered"] = attach_references(answer, evidence)
                            except Exception as exc:
                                result["error"] = str(exc)
                            result["seconds"] = round(time.monotonic() - start, 3)
                        chosen = row["writers"].get("resolved", {}).get("answer", {})
                        history.extend([{"role": "user", "content": question},
                            {"role": "assistant", "content": (chosen.get("material_answer", "") + " " +
                             chosen.get("additional_explanation", "") + " " + chosen.get("limitation", ""))[:350]}])
                        last_request = resolved or last_request
                    except Exception as exc:
                        row["error"] = str(exc)
                    report["rows"].append(row)
                    save()
                    print(json.dumps({"model": model, "repeat": repeat, "turn": turn,
                                      "route": row.get("route"), "planner": row.get("planner"),
                                      "error": row.get("error")}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    asyncio.run(run(parser.parse_args()))
