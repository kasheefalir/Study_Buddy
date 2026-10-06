"""Request-local accounting; concurrent conversations never share counters."""
from contextlib import contextmanager
from contextvars import ContextVar


_calls = ContextVar("ollama_calls", default=None)
_stage = ContextVar("ollama_stage", default="answer")


@contextmanager
def track_usage():
    calls = []
    token = _calls.set(calls)
    try:
        yield calls
    finally:
        _calls.reset(token)


@contextmanager
def usage_stage(name):
    token = _stage.set(name)
    try:
        yield
    finally:
        _stage.reset(token)


def record_usage(payload, model, context=None):
    calls = _calls.get()
    if calls is None:
        return
    def count(key):
        value = payload.get(key)
        return value if type(value) is int and value >= 0 else None
    calls.append({"stage": _stage.get(), "model": model,
                  "input_tokens": count("prompt_eval_count"),
                  "output_tokens": count("eval_count")})
    if context is not None:
        calls[-1]["context"] = context


def summarize(calls):
    def total(key):
        values = [call[key] for call in calls]
        return sum(values) if values and all(v is not None for v in values) else None
    return {"calls": list(calls), "input_tokens": total("input_tokens"),
            "output_tokens": total("output_tokens")}
