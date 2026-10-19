"""Identical synthetic attribution probes; never reads the user's uploaded library."""
import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx

from app.agents.local_study.bounded_tutor import TutoringAnswer, attach_references, messages
from app.config import settings

MODELS = ("llama3.2:3b", "phi4-mini:latest", "gpt-oss:20b", "gemma4:31b-cloud")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new output filename")
    cases = json.loads(Path("tests/fixtures/bounded_tutor_cases.json").read_text())
    report = {"data": "Synthetic authored fixtures only; no uploaded material", "rows": [],
              "prompt_version": "schema_in_prompt_v2",
              "settings": {"temperature": 0.1, "num_ctx": 4096, "num_predict": 1200},
              "limitations": "Manual semantic grading required; remote provider may not honor all sampling options"}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(report, indent=2))

    async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=180) as client:
        tags = await client.get("/api/tags")
        tags.raise_for_status()
        installed = {m["name"] for m in tags.json()["models"]}
        for model in MODELS:
            if model not in installed:
                report["rows"].append({"model": model, "error": "Not installed; not downloaded"})
                save()
                continue
            resident = await client.get("/api/ps")
            resident.raise_for_status()
            for other in resident.json()["models"]:
                if other["name"] != model and not other["name"].startswith("nomic-embed-text"):
                    response = await client.post("/api/generate", json={"model": other["name"], "keep_alive": 0})
                    response.raise_for_status()
            for repeat in range(args.repeats):
                for case in cases:
                    evidence = [{"document_id": "synthetic", "chunk_id": 1,
                                 "location": "Synthetic passage", "text": case["text"]}]
                    payload = {"model": model, "messages": messages(case["question"], evidence, True),
                               "format": TutoringAnswer.model_json_schema(), "stream": False,
                               "keep_alive": "5m", "options": report["settings"]}
                    if model == "gpt-oss:20b":
                        payload["think"] = "low"
                    elif model == "gemma4:31b-cloud":
                        payload["think"] = False
                    start = time.monotonic()
                    row = {"model": model, "case": case["id"], "repeat": repeat,
                           "think": payload.get("think", "not requested")}
                    try:
                        response = await client.post("/api/chat", json=payload)
                        response.raise_for_status()
                        result = response.json()
                        row["raw"] = result["message"]["content"]
                        row["usage"] = {k: result.get(k) for k in ("eval_count", "prompt_eval_count", "done_reason", "load_duration")}
                        if result.get("done_reason") == "length" or not result.get("done"):
                            raise ValueError("Incomplete completion")
                        answer = TutoringAnswer.model_validate_json(row["raw"])
                        row["answer"] = answer.model_dump()
                        row["rendered"] = attach_references(answer, evidence)
                    except Exception as exc:
                        row["error"] = f"{type(exc).__name__}: {exc}"
                    row["seconds"] = round(time.monotonic() - start, 3)
                    report["rows"].append(row)
                    save()
                    print(json.dumps({k: v for k, v in row.items() if k not in {"raw", "answer", "rendered", "usage"}}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
