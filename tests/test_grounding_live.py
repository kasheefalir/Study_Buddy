"""Opt-in semantic regression using a locally supplied nearest-distance passage."""
import asyncio
import json
import os
from pathlib import Path

import pytest

from app.agents.grounded_answer import (
    GroundedAnswer, verify_points,
)
from app.config import settings
from app.llm.ollama_client import OllamaClient


@pytest.mark.skipif(not os.getenv("BUDDY_LIVE_EVIDENCE"), reason="Requires local book and Ollama")
def test_live_checker_distinguishes_support_from_topic_overlap():
    chunks = json.loads(Path(os.environ["BUDDY_LIVE_EVIDENCE"]).read_text())
    chunk_id = int(os.environ["BUDDY_LIVE_CHUNK_ID"])
    text = next(c["text"] for c in chunks if c["id"] == chunk_id)
    claims = [
        "Regularization guarantees accurate nearest-neighbor predictions.",
        "With many dimensions, nearest points are often not much closer than average points.",
        "In high dimensions, nearest points are much closer than average points.",
        "In low-dimensional data sets, the closest points tend to be much closer than average.",
    ]
    answer = GroundedAnswer(points=[{"explanation": claim, "evidence": [{"label": "S1"}]}
                                   for claim in claims])
    llm = OllamaClient(settings.ollama_url, settings.ollama_model)
    checks = asyncio.run(verify_points(llm, answer, [{"label": "S1", "text": text}]))
    assert [c.supported for c in checks] == [False, True, False, True], checks
