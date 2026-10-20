# Dedicated Qwen Router Pilot

Date: 2026-10-20. Decision: **do not enable** Qwen2.5 0.5B routing.
No live routing settings or conversations were changed.

## Method

Ten synthetic fixed-context cases, each repeated twice: greeting, source question,
simplification, material overview, chat recap, new quiz, pause, resume, next, and
greeting combined with a source request. All models used the shared intent-router
prompt and schema through the production structured-output helper. GPT used the
standard client for this identical-harness control, not its specialized production
router/client. These are not full-app speed or accuracy measurements.

The compact Qwen variant shortened instructions but retained the same output
schema and cases. Repetitions are not 20 independent questions. A short historical
source explanation and saved pending-question text were supplied to all cases;
quiz activity flags varied per case.

| Variant | Correct route | Exact route/mode/action | Median call time |
| --- | --- | --- | --- |
| Qwen2.5 0.5B, shared prompt | 8/20 | 0/20 | 0.50 seconds |
| Qwen2.5 0.5B, compact prompt | 8/20 | 4/20 | 0.45 seconds |
| Phi-4 Mini, shared prompt | 20/20 | 11/20 | 2.27 seconds |
| GPT-OSS 20B, shared prompt | 20/20 | 18/20 | 3.88 seconds |

Exact-field checks are deliberately strict and are not downstream failure rates:
the application normalizes some fields, and "simplify" can be reasonable where
the fixture expects "chat". Query fidelity and pause_activity were not scored.
Qwen's failures went beyond these distinctions: it treated greetings as retrieval
and assigned unrelated activity transitions. Valid JSON was not sufficient.

## Memory and Loading

The test host has 32 GiB system RAM. Ollama reported Qwen resident size of
693,874,195 bytes (about 694 MB), at a 16,384-token configured context.
This is model residency, not total app/system memory or a peak-memory measurement.

Loading GPT initially evicted the previously resident models. During subsequent
alternation, Qwen's first return took 1.89 seconds, including 1.04 seconds of
loading; the next took 0.41 seconds with about 0.004 seconds loading.
The later snapshot showed Qwen and GPT simultaneously resident. This does not
establish that they can coexist on an 8 GB machine.

The speed and space savings are real at the router-call level, but do not justify
the measured routing errors. No improvement to total answer latency is claimed.

## Reproduction

```bash
python3 -m scripts.evaluate_tiny_router \
  --model qwen2.5:0.5b --model phi4-mini:latest --model gpt-oss:20b \
  --output data/evaluations/tiny-router-new.json
python3 -m scripts.evaluate_tiny_router \
  --model qwen2.5:0.5b --compact \
  --output data/evaluations/tiny-router-compact-new.json
```

Original raw results, usage, and residency snapshots are saved locally in
`data/evaluations/tiny-router-20261020.json` and
`data/evaluations/tiny-router-compact-20261020.json`. Existing reports are never
overwritten.
