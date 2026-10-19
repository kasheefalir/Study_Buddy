# Small-Model Quiz Speed And Accuracy

Later direction: [Large-Model Quiz Holdouts](large-model-quiz-holdouts.md)
records GPT/Gemma-targeted optimization and the GPT-only promotion. The earlier
small-model experiments below remain historical evidence, not a capability cap.

## Protocol (2026-10-16)

Added an independently authored, checked answer-key fixture for three previous
failure categories: direction of outlier effects, held-out test standardization,
and correlation versus causation. Correct answers and review criteria live in
`tests/fixtures/quiz_accuracy_cases.json`; the evaluator never sends the oracle
answer field to the model.

`scripts/evaluate_quiz_speed_accuracy.py` compares the current generation prompt
with a shorter generation-only contract. Each model runs each of three cases in
two modes, with two repeats and reversed prompt order on the second repeat:

- Fixed: preserve the authored question/options and select its answer.
- Generated: create a new question and choices from the same source and focus.

Both prompts receive the same schema, source, focus, and runtime settings:
4096 context, 700 output tokens, temperature 0.2, thinking disabled. Each draft
uses exactly one call, with no retries or model-based checker. Models are
preloaded before timing. This isolates the generation stage; it does NOT prove
end-to-end quiz speed or safe removal of the production quality check.

There are 48 calls: two local models x three cases x two prompt variants x two
modes x two repeats. No cloud requests and no private documents are involved.
Raw requests, responses, timings, and deterministic checks are saved locally in
`data/study-reviews/quiz-speed-accuracy-20261016.json` (ignored by Git).

## Interpretation

| Model / prompt | Fixed keys correct | Fixed wording fully preserved | Mean draft seconds (all modes) |
| --- | --- | --- | --- |
| Llama / baseline | 6/6 | 4/6 | 2.797 |
| Llama / compact | 6/6 | 6/6 | 2.738 |
| Phi / baseline | 6/6 | 3/6 | 3.629 |
| Phi / compact | 6/6 | 6/6 | 3.685 |

Free-generation means were Llama baseline 2.565s versus compact 2.667s, and
Phi baseline 3.703s versus compact 3.643s. These tiny, mixed differences do not
establish a speed advantage. Forty-eight calls produced parseable outputs.
The shorter contract preserved supplied wording better but did not consistently
fix question quality. Repeated near-identical outputs are not independent proof
of generalization. No numerical accuracy or full-quiz latency claim is made.

Fixed-choice answer-key success and factual quality of freely generated choices
are distinct measurements. The automatic checks only establish exact key
agreement and preservation of supplied wording; they do not certify explanation
truth. Free-generation outputs require independent review for correctness,
exactly one defensible option, qualifications, and explanatory consistency.

Observed failures include:

- Llama baseline says an extreme observation has no effect on the median.
- Llama compact selects causation while its explanation says correlation does
  not establish causation, on both repeats.
- Llama compact standardization questions contain overlapping true options.
- Phi compact outlier choices include both sensitivity of the mean and lesser
  sensitivity of the median as separate defensible answers.
- Phi compact standardization choices describe the same correct procedure twice.
- The existing lexical stem-overlap check rejects a correct Phi baseline answer
  about using training-set statistics. This is a potential unnecessary retry,
  not justification to remove the check without downstream regression tests.
- Phi baseline's second standardization question also has two valid answers:
  using test statistics and fitting preprocessing on test data both leak data.
- Phi compact's second standardization draft has a correct key but adds option
  letter prefixes despite instructions, showing remaining presentation drift.

The compact contract remains EXPERIMENTAL. It is not wired into the live quiz
workflow. Preserve prepared small-model quizzes, code-owned progression/scoring,
and the production quality check. Neither smaller token limits nor shorter
prompts are promoted based only on speed. No large-model workflow was changed.

Verification: 324 tests passed, one skipped. The evaluator restored Llama after
the run. All changes in this round are evaluation fixtures, scripts, tests, and
documentation; no live quiz prompts or output budgets changed.

## Reproduce

```sh
CONTEXT_WINDOW=4096 RESPONSE_TOKENS=700 OLLAMA_THINK=false python3 -m scripts.evaluate_quiz_speed_accuracy --output data/study-reviews/quiz-speed-accuracy-new.json
```

Next targeted experiment: eliminate false-positive regeneration without allowing
known invalid questions through. Compare total calls and wall time, not just
draft latency. Preserve the independent key fixture and add held-out concepts
before treating gains as general. Numerical feedback remains a separate test;
these generation-only trials request no arithmetic and cannot validate that path.

## Follow-Up: Overlap Exception (Not Promoted)

Tested an offline exception for an answer that introduces a content word absent
from the question and the other choices. Generic words, negation, and filler
cannot qualify. This recovers the saved Phi draft whose only distinguishing
word is "training", while retaining rejection of the old assignment-purpose
echo and the incorrect "no effect on the median" answer.

Replayed the 48 saved drafts and ran 24 local semantic-check calls across Llama
and Phi, two repeats each. First set: valid training-statistics key, invalid
test-statistics key, and overlapping correct options. Second set: replace the
incorrect key with "validation" so it specifically qualifies for the proposed
exception. All semantic checks approved all three categories on both repeats
for both models. These are small targeted tests, not general failure rates.

The second set demonstrates an actual combined-path regression:

| Draft | Existing overlap check | Candidate check | Semantic check, both models |
| --- | --- | --- | --- |
| Correct training-statistics key | Rejects | Passes | Accepts |
| Incorrect validation-statistics key | Rejects | Passes | Accepts |
| Overlapping true choices | Rejects | Rejects | Accepts |

Do NOT promote the exception. A distinguishing word is not evidence of truth,
and the existing checker did not protect the new boundary. No production code,
prompts, quality gates, or output limits changed in this follow-up. No measured
end-to-end speed improvement is claimed. Saving a regeneration would be useful
only if invalid keys stayed out.

Artifacts: `scripts/evaluate_quiz_overlap.py`, `tests/test_quiz_overlap_trial.py`,
and ignored local reports `quiz-overlap-20261016.json` (first set) and
`quiz-overlap-contrast-20261016.json` (second set). The script currently reproduces
the second set and refuses to overwrite its report. The independent expected
accept/reject outcomes are stored with model decisions. Four regression tests
cover the intended exception, preserved rejections, and its factual limitation.

Verification: 328 tests passed, one skipped. Llama was restored after both runs.
Next experiment should address answer-key verification independently of the
draft's own explanation, not further weaken overlap filtering. Keep the same
wrong-key and overlapping-answer controls when testing any faster path.

## Larger-Model Checker Comparison (2026-10-16)

At the user's request, ran the identical contrast cases and production quality
prompt on GPT-OSS 20B and Gemma 4 31B cloud. Same 4096 context, 700 output limit,
temperature 0.2, and two repeats per case. GPT uses its supported low reasoning
setting; other models request thinking=false. The format normalizer is unchanged.
This tests the semantic checker directly, not a complete quiz or each model's
optimized architecture. Only the synthetic scaling passage was sent to cloud.

| Model | Accept valid draft | Reject wrong validation-set key | Reject overlapping choices | Correct decisions |
| --- | --- | --- | --- | --- |
| Llama 3.2 3B (prior contrast run) | 2/2 | 0/2 | 0/2 | 2/6 |
| Phi-4 Mini (prior contrast run) | 2/2 | 0/2 | 0/2 | 2/6 |
| GPT-OSS 20B | 2/2 | 2/2 | 1/2 | 5/6 |
| Gemma 4 31B cloud | 2/2 | 2/2 | 2/2 | 6/6 |

GPT explicitly identified training statistics as the correct key on both wrong-
key cases, but missed the duplicate meaning once. Gemma identified both errors
on both repeats. No parsing failures occurred; Gemma's wrapped JSON was handled
by the existing lossless normalizer without changing verdicts.

Mean timed checker call: GPT 6.47 seconds, Gemma 0.55 seconds in this run, excluding
preload. Cloud network/server/cache conditions and different hardware make these
observations unsuitable as general speed rankings. Two repeats on three closely
related cases are not calibrated accuracy estimates or proof of robustness.

Raw evidence: ignored local `data/study-reviews/quiz-overlap-large-20261016.json`
contains prompts, raw outputs, verdicts, timings, and settings. Reproduce with:

```sh
CONTEXT_WINDOW=4096 RESPONSE_TOKENS=700 OLLAMA_THINK=false python3 -m scripts.evaluate_quiz_overlap --models gpt-oss:20b gemma4:31b-cloud --output data/study-reviews/quiz-overlap-large-new.json
```

The runner now accepts explicit model/output arguments and records formatting
errors separately from accept/reject decisions. No production changes were made;
the overlap exception remains offline pending broader held-out validation, even
for the larger models. Llama was restored. Verification: 328 tests passed, one
skipped; diff whitespace check passed.
