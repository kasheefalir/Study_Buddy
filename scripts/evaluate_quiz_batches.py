"""Matched quiz batching pilot; synthetic material only, production model budgets.

No live dispatch changes. Saved keys test mechanics, not independent accuracy.
Cloud models send synthetic notes/prompts to their provider.
"""
import argparse
import asyncio
import json
from pathlib import Path
import tempfile

from app.agents.context_budget import model_budget
from app.agents.gpt.client import GPTClient
from app.config import settings
from scripts import evaluate_quiz_comparison as evaluation


class TracedGPT(evaluation.TraceClient, GPTClient):
    """TraceClient's super().chat uses the production GPT client through MRO."""


async def run(args):
    if args.output.exists():
        raise ValueError("Choose a new report filename.")
    normal_client = evaluation.TraceClient
    report = {"protocol": __doc__, "context_window": settings.context_window,
              "fixture": "tests/fixtures/quiz_logistic_material.json", "results": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        for model in args.models:
            evaluation.TraceClient = TracedGPT if model == "gpt-oss:20b" else normal_client
            for size in args.sizes:
                with tempfile.TemporaryDirectory(prefix="buddy-batch-") as directory:
                    root = Path(directory)
                    initial = evaluation.fixture(root, Path(report["fixture"]))
                    with model_budget(model):
                        result = await evaluation.sequence(root, initial, model, size != 1, batch_size=size)
                report["results"].append(result)
                args.output.write_text(json.dumps(report, indent=2))
    finally:
        evaluation.TraceClient = normal_client


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=["phi4-mini:latest", "gpt-oss:20b", "gemma4:31b-cloud"])
    parser.add_argument("--sizes", nargs="+", type=int, choices=[1, 2, 5], default=[1, 2, 5])
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))
