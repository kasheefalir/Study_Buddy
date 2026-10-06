"""Ephemeral request-local progress, separate from conversation memory."""
from contextlib import contextmanager
from contextvars import ContextVar

active = {}
current = ContextVar("study_activity", default=None)


@contextmanager
def track(identifier):
    token = current.set(identifier)
    active[identifier] = "Understanding your request"
    try:
        yield
    finally:
        active.pop(identifier, None)
        current.reset(token)


def report(stage):
    identifier = current.get()
    if identifier:
        labels = {"quiz intent": "Understanding your quiz request", "quiz request": "Planning your quiz",
                  "quiz choices": "Preparing multiple-choice options", "quiz window": "Preparing your question",
                  "quiz assessment": "Reviewing your answer", "choice feedback": "Explaining your answer", "material tool selection": "Finding relevant passages",
                  "response review": "Checking the explanation against your request and sources",
                  "response revision": "Refining the explanation"}
        labels["retrieval sufficiency"] = "Checking whether the material covers your question"
        active[identifier] = labels.get(stage, "Preparing your response")
