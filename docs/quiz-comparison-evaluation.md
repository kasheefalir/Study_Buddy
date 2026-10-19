# Five-Question Quiz Comparison

Follow-up: [Small-Model Quiz Speed And Accuracy](quiz-speed-accuracy-evaluation.md)
records the subsequent 48-call short-prompt trial and independent answer keys.

Date: 2026-10-16. These are exploratory single runs, not reliability estimates.
127 live model calls were recorded. Cloud requests used only the authored
synthetic fixture, never uploaded student materials.

Verification: 322 tests passed, one skipped. The selected Llama model was restored
and the running app health check confirmed it was connected and loaded.

## Protocol

`scripts/evaluate_quiz_comparison.py` exercises production `quiz_turn` with a
fixed five-question plan and fixed source windows from
`tests/fixtures/quiz_comparison_material.json`. It isolates generation and
playback: it does not test intent routing, retrieval, or browser interactions.
All conditions use 8192 context tokens, 2048 output tokens, temperature 0.2;
GPT uses low thinking and others request false (provider support may differ).
This is not the optimized model-specific GPT workflow.

State is saved and reloaded after each step. Questions 1 and 3 receive deliberately
wrong selections; others match the generated key. Assertions check four choices,
hidden pending keys, question IDs/numbering, final 3/5 score, completion without
advancing again, missed-question review, and retained final-question context.
Scoring against a generated key does NOT establish that the key is factually right.

## Baseline: Identical Incremental Harness

| Model | Answers completed | Calls | Run seconds | Failure or caveat |
| --- | --- | --- | --- | --- |
| Llama 3.2 3B | 1/5 | 9 | 26.48 | Q2 failed quality gate after three drafts |
| Phi-4 Mini | 5/5 | 17 | 79.15 | Mechanics passed; wrong standardization keys |
| GPT-OSS 20B | 2/5 | 7 | 71.45 | Q3 summary exceeded schema length |
| Gemma 4 cloud | 0/5 | 1 | 0.89 | Fenced JSON/schema wrapper failed parsing |

Manual review found factual failures independent of formatting. Llama described
the median as unaffected by extremes and calculated an example incorrectly.
Phi's Q4/Q5 keys incorrectly said not to apply standardization/training statistics
to the test set. GPT assumed extreme values necessarily increase the mean and
gave incorrect mean/median calculations. Checkers both accepted flawed drafts
and rejected useful content. Do not interpret mechanical success as accuracy.

## Separate Adaptive Conditions

| Condition | Answers completed | Calls | Observation |
| --- | --- | --- | --- |
| Llama prepared bank | 5/5 | 18 | Initial preparation 37.338s; Next 2-4ms, zero calls |
| Phi prepared bank | 5/5 | 17 | Initial preparation 63.955s; Next 2-3ms, zero calls |
| GPT model-based format repair | 5/5 | 18 | Three repair calls; 166.44s total |
| Gemma model-based format repair | 5/5 | 34 | Seventeen repair calls; 31.00s total |
| Gemma code-only envelope cleanup | 0/5 | 6 | Parsed correctly; quality rejection after three drafts |

Prepared banks solve progression latency, not factual correctness. Llama still
produced overlapping choices and inconsistent feedback. Phi still generated a
key using test-set statistics for standardization and incorrect numeric feedback.
Retain the existing prepared fallback for usability, not as an accuracy fix.

The model-repair experiment asked for formatting-only corrections, but sometimes
changed options or feedback. It is NOT enabled in production. GPT still had
incorrect arithmetic and an overbroad claim that training-statistic scaling
guarantees no future-information leakage. Gemma's five question/key pairs in that
condition were sound on manual review, with some imprecise explanatory wording;
one run does not establish consistent superiority or full factual reliability.

Fresh Gemma with code-only cleanup retained `valid=false` checker decisions.
It repeatedly offered correlation and sum as distractors for a central-tendency
question. The checker rejected those implausible choices. No formatting error
remained, but no quiz completed. Do not bypass that gate to improve the score.

## Implemented / Rejected

Implemented only lossless quiz JSON-envelope cleanup in
`app/llm/structured_output.py`, used by quiz choices, quality, and feedback.
It removes an optional JSON fence and an exact schema-metadata wrapper, then
runs the original Pydantic validator. It never edits answers, truncates fields,
adds missing values, or overrides negative checker verdicts. Other stages retain
their previous parsing behavior. The running server needs a restart to load it.

Replay of 86 recorded calls: 64 already-valid outputs remained identical,
18 wrapper-only failures were recovered, and four invalid outputs still failed.
Replay is not 86 additional model calls and does not measure factual improvement.
Unit tests cover value preservation, malformed/wrong wrappers, negative verdicts,
and isolation from retrieval planning.

Do not promote the model-based repair. Do not replace small-model prepared
quizzes with incremental generation based on these results. No retrieval,
answer-writer, routing, or model-selection changes were made for this experiment.

## Reproduction And Evidence

Run from the repository root:

```sh
CONTEXT_WINDOW=8192 RESPONSE_TOKENS=2048 OLLAMA_THINK=false python3 -m scripts.evaluate_quiz_comparison --output data/study-reviews/quiz-comparison-new.json
```

Use `--help` for prepared and experimental repair options. Raw reports in the
ignored local `data/study-reviews` directory preserve prompts, responses, timings,
and state assertions:

- `quiz-comparison-20261016.json`
- `quiz-format-repair-20261016.json`
- `quiz-prepared-20261016.json`
- `quiz-envelope-replay-20261016.json`
- `quiz-envelope-cloud-20261016.json`

Timings include different failure points and repair work and are not controlled
model speed rankings. Next priorities: independently validate answer keys and
single-answer distractors, keep arithmetic examples in code, and test repeated
runs before promoting further generation changes. Then test intent/pause/resume
and the full browser flow separately.
