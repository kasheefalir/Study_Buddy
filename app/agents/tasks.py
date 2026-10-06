"""Small deterministic task router; no additional model call required."""
from pathlib import Path
import re
from app.agents.quiz import REVIEW, START, NEXT, CHANGE

PROMPTS = Path(__file__).parent / "prompts"
MODES = {"auto", "chat", "quiz", "simplify", "summary_conversation", "summary_material"}


def task_for(message, requested, quiz):
    if requested not in MODES:
        raise ValueError("Unknown study task")
    if requested != "auto":
        return requested
    if re.search(r"\b(stop|end|exit|cancel)\b.*\bquiz\b", message, re.I) and not REVIEW.search(message):
        return "chat"
    if START.search(message) or REVIEW.search(message) or (quiz.get("version") and (NEXT.fullmatch(message) or CHANGE.search(message))):
        return "quiz"
    if re.search(r"\b(summarize|summarise|summary|recap)\b", message, re.I):
        if re.search(r"\b(conversation|chat|discussion|discussed)\b", message, re.I):
            return "summary_conversation"
        # Ambiguous summaries must reach the resource planner, not silently skip retrieval.
        return "summary_material" if re.search(r"\b(slides?|powerpoint|document|material|file|notes)\b", message, re.I) else "chat"
    if re.search(r"\b(simply|simpler|simplify)\b|plain language", message, re.I):
        return "simplify"
    return "quiz" if quiz.get("active") else "chat"


def task_prompt(mode):
    return (PROMPTS / (mode + ".md")).read_text(encoding="utf-8") if mode != "chat" else "Follow the student's current request naturally."
