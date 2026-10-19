"""Replay saved follow-up inputs against a candidate planner instruction only."""
import argparse
import asyncio
import json
from pathlib import Path

import httpx

from app.agents.chat_agent import RETRIEVAL_PLAN_PROMPT
from app.agents.local_study.followup_planner import FOLLOWUP_GUIDANCE
from app.agents.study_tools import structured
from app.config import settings
from app.llm.ollama_client import OllamaClient


async def run(args):
    if args.output.exists():
        raise ValueError("Choose a new report path")
    baseline = json.loads(args.baseline.read_text())
    source = json.loads(Path("tests/fixtures/bounded_tutor_cases.json").read_text())[0]["text"]
    evidence = [{"document_id": "a" * 32, "chunk_id": 1, "location": "Synthetic passage", "text": source}]
    report = {"baseline": str(args.baseline), "protocol": __doc__, "rows": []}
    histories, requests = {}, {}
    current = None
    async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=180) as client:
        for row in baseline["rows"]:
            model = row["model"]
            key = (model, row["repeat"])
            history = histories.setdefault(key, [])
            if current != model:
                resident = await client.get("/api/ps")
                resident.raise_for_status()
                for other in resident.json()["models"]:
                    if other["name"] != model and not other["name"].startswith("nomic-embed-text"):
                        response = await client.post("/api/generate", json={"model": other["name"], "keep_alive": 0})
                        response.raise_for_status()
                current = model
            if row["turn"] in (1, 2, 3):
                data = {"latest_message": row["question"], "last_material_request": requests.get(key, ""),
                        "recent_dialogue": history[-3:],
                        "selected_materials": [{"id": "a" * 32, "title": "Regression study notes", "kind": "file", "url": ""}],
                        "unfinished_activity": {"mode": "chat", "quiz_active": False, "quiz_paused": False,
                                                "phase": "", "pending_question": ""},
                        "explicit_task": "auto", "intent": row["route"], "previous_evidence": evidence}
                result = {"model": model, "repeat": row["repeat"], "turn": row["turn"],
                          "input": data, "baseline": row.get("planner")}
                try:
                    result["candidate"] = await structured(OllamaClient(settings.ollama_url, model, timeout=180),
                        "retrieval plan", RETRIEVAL_PLAN_PROMPT + FOLLOWUP_GUIDANCE, data)
                except Exception as exc:
                    result["error"] = str(exc)
                report["rows"].append(result)
                args.output.write_text(json.dumps(report, indent=2))
                print(json.dumps({k: v for k, v in result.items() if k != "input"}), flush=True)
            chosen = row["writers"].get("resolved", {}).get("answer", {})
            history.extend([{"role": "user", "content": row["question"]},
                {"role": "assistant", "content": (chosen.get("material_answer", "") + " " +
                 chosen.get("additional_explanation", "") + " " + chosen.get("limitation", ""))[:350]}])
            requests[key] = row.get("planner", {}).get("query") or requests.get(key, "")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))
