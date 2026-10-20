# DeepSeek-R1 14B Routing Pilot

Date: 2026-10-20. No live routing policy or selected model was changed.

## Setup

Same ten synthetic fixed-context routing cases as the tiny-router pilot, repeated
twice with the shared prompt and output schema. Model: `deepseek-r1:14b`,
reported as 14.8B parameters, Q4_K_M quantization. Standard Ollama client,
16,384-token context, 1,200-token output ceiling, temperature 0.2, and no explicit
thinking override. The benchmark request timeout was 180 seconds.

These are router-only probes, not retrieval, answer correctness, quiz-generation,
or prompt-injection tests. Repeats are not independent questions. The earlier
baseline models were not rerun alongside DeepSeek, so timing comparisons are
indicative rather than controlled concurrent benchmarks.

## Results

| Model | Correct broad route | Exact route/mode/action | Median routing time |
| --- | --- | --- | --- |
| Qwen2.5 0.5B | 8/20 | 0/20 | 0.50 s |
| Phi-4 Mini | 20/20 | 11/20 | 2.27 s |
| GPT-OSS 20B | 20/20 | 18/20 | 3.88 s |
| DeepSeek-R1 14B | 20/20 | 12/20 | 44.17 s |

DeepSeek completed all 20 with valid structured responses: no transport,
validation, or output-limit errors. Calls ranged from 22.18 to 61.37 seconds.
Total scored-call time was 865.60 seconds (14.43 minutes).

The initial greeting took 50.91 seconds, including 8.21 seconds loading and
11.45 seconds prompt evaluation. Later slow calls occurred with the model loaded.
Ollama reported about 11.90 GB resident model memory at this context size, with
the entire reported model allocation on the GPU. This is not total system
memory or a peak-memory measurement.

## Failure Patterns

- Resume returned the correct quiz route but `keep` instead of `resume`, twice.
- Next-question returned the quiz route but `keep` instead of `next`, twice.
- Material summary, conversation recap, new quiz, and pause each missed one
  mode/action expectation across the two repetitions.
- Some explanations described the intended action correctly while the structured
  action differed. The app executes the fields, not the explanation.

Exact-field matching is stricter than downstream success: the app normalizes some
fields. Conversely, these checks do not score query fidelity or pause_activity.
Valid JSON and correct broad routes alone do not establish full reliability.

## Decision

Do not promote DeepSeek 14B to dedicated router. Its median routing call was about
11 times the earlier GPT control and 19 times Phi, without better exact-field
reliability than GPT. The 12/20 versus Phi's 11/20 is too small a difference in
this pilot to establish an accuracy advantage.

This conclusion is limited to the tested harness and routing task, not the
model's overall reasoning or tutoring capability.

Runner: `scripts/evaluate_tiny_router.py`.
Raw local report: `data/evaluations/deepseek14-router-20261020.json`.
Baseline protocol and limitations: `docs/tiny-router-evaluation.md`.
