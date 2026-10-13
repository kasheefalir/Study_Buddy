"""Compare frozen writer with code-bound attribution, without changing the live writer."""
import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.config import settings
from scripts.evaluate_selector_precision import model_call
from scripts.evaluate_writer import FALLBACK, candidate_request, render_candidate


class BoundAnswer(BaseModel):
    model_config = {"extra": "forbid"}
    status: Literal["answered", "insufficient_evidence"]
    points: list[str] = Field(max_length=4)

    @model_validator(mode="after")
    def consistent(self):
        if (self.status == "answered") != bool(self.points):
            raise ValueError("Answered requires points; abstention requires none.")
        if any(not p.strip() or "[" in p or "]" in p for p in self.points):
            raise ValueError("Empty points and model-generated citation brackets are not allowed.")
        return self


def bound_request(question, source):
    request, _ = candidate_request(question, [source], False)
    request[0]["content"] += (
        " Each point must be a plain explanation string, not an evidence object. "
        "Do not output citations, source names, or page numbers. Code owns attribution. "
        "Only answer what this single block establishes; do not invent a missing comparison side.")
    request[1]["content"] = json.dumps({"question": question, "resolved_request": question,
                                       "evidence": [{"text": source["text"]}]})
    return request, BoundAnswer.model_json_schema()


def render_bound(raw, source):
    answer = BoundAnswer.model_validate_json(raw)
    return "\n\n".join(p.strip() + f" [{source['label']}]" for p in answer.points) or FALLBACK


async def run(args):
    if args.output.exists():
        raise ValueError("Choose a new report path; previous experiments are immutable.")
    data = args.chunks.read_bytes()
    chunks = {c["id"]: c for c in json.loads(data)}
    sources = [{**chunks[cid], "label": f"S{i+1}"} for i, cid in enumerate(args.chunk_ids)]
    report = {"model": settings.ollama_model, "context_window": settings.context_window,
              "source_hash": hashlib.sha256(data).hexdigest(), "sources": sources,
              "protocol": "Fixed full chunks, original writer vs original instructions with single-source code attribution. No retrieval or selector; provenance is not factual correctness.",
              "results": []}
    for case in json.loads(args.cases.read_text()):
        for variant in ["original", "code_owned"]:
            row = {"case": case, "variant": variant, "calls": []}
            answers = []
            try:
                for source in (sources if variant == "code_owned" else [None]):
                    request, schema = (bound_request(case["question"], source) if source else
                                       candidate_request(case["question"], sources, False))
                    trace = {"request": request, "schema": schema,
                             "assigned_source": source["label"] if source else None}
                    row["calls"].append(trace)
                    start = time.monotonic()
                    trace["raw"], trace["usage"] = await model_call(request, schema, 0.2)
                    trace["seconds"] = round(time.monotonic() - start, 3)
                    answers.append(render_bound(trace["raw"], source) if source else
                                   render_candidate(trace["raw"], sources))
                row["rendered"] = "\n\n".join(a for a in answers if a != FALLBACK) or FALLBACK
            except (ValueError, RuntimeError) as exc:
                row["error"] = str(exc)
            row["seconds"] = round(sum(c.get("seconds", 0) for c in row["calls"]), 3)
            report["results"].append(row)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2))
            print(json.dumps({k: v for k, v in row.items() if k != "calls"}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--chunk-ids", nargs="+", type=int, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))
