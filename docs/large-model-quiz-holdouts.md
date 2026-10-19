# Large-Model Quiz Holdouts

2026-10-16. GPT-OSS and Gemma are the optimization targets. The small-model
workflow is protected from regression, not used as a ceiling for large-model
features. Same-harness evaluation and model-specific promotion remain separate.

## Protocol

Authored three new subjects: SQL aggregates, stack ordering, and HTTP status
codes. Each has a valid draft, wrong designated key, overlapping true choices,
and a correct general-knowledge key whose defining evidence is absent from the
supplied excerpt. The missing-evidence cases test material support, not whether
the model knows the topic. Each is run twice per model: 24 calls per model.

The identical production quality prompt, schema, and lossless JSON normalizer
are used for both models. Context 4096, output cap 700, temperature 0.2;
GPT uses low reasoning and Gemma requests thinking=false. Preload is excluded
from per-call timing. Only synthetic authored passages are sent to cloud.

SQL and HTTP probe the proposed overlap exception's newly admitted boundary.
The stack subject is an unchanged-path control: the original lexical rule
already allows its wording. Semantic checks are run even where the original
structural check rejects, so their decisions can be inspected independently.
A passing semantic check alone is NOT equivalent to a production acceptance.

Promotion requires recovering valid drafts without admitting new unsupported
or incorrect drafts. Passing the same-harness comparison does not automatically
enable a model-specific path. Repeats on this small fixture are not calibrated
accuracy probabilities, nor an isolated test of parameter count.

## Reproduction

```sh
CONTEXT_WINDOW=4096 RESPONSE_TOKENS=700 OLLAMA_THINK=false python3 -m scripts.evaluate_quiz_overlap_holdouts --output data/study-reviews/quiz-overlap-holdouts-new.json
```

Fixture: `tests/fixtures/quiz_overlap_holdouts.json`.
Raw run: ignored local `data/study-reviews/quiz-overlap-holdouts-20261016.json`.
Each row preserves prompt, raw output, expected verdict, actual verdict,
structural baseline/candidate decisions, errors, and timing. The runner refuses
to overwrite a report and restores Llama when it finishes.

Regression tests verify fixture variants, unchanged input data, structural
boundary classification, and scorecard handling of existing failures versus
newly admitted failures and parse errors.

## Results And Promotion

| Model / checker | Correct semantic decisions | False accepts | Formatting errors |
| --- | --- | --- | --- |
| GPT / original | 15/24 | 9 | 0 |
| GPT / revised | 23/24 | 1 | 0 |
| Gemma / original | 18/24 | 0 | 0 |
| Gemma / revised | 20/24 | 0 | 4 |

The revised checker independently compares the designated key against source
evidence, checks every option for equivalent correct answers, and explicitly
does not reject a full-sentence option just for repeating stem wording. It
replaces the existing checker prompt, not an additional model call.

GPT correctly classified 12/12 cases in its first repeat and 11/12 in its second.
Its remaining false acceptance was the second HTTP overlapping-choice case.
The retained structural rule rejects that case in both baseline and candidate,
so the combined candidate admits no invalid draft in this fixture. All six
valid drafts pass the combined candidate. This is bounded fixture evidence,
not a guarantee against future mistakes.

Gemma's original checker rejected all six valid drafts on style grounds. The
revised checker accepted all six, but four rejection responses duplicated
fields both inside and outside a `properties` wrapper. Existing strict parsing
correctly refused those responses. These errors are not counted as successful
rejections; normalizer rules were not loosened to improve the score.

Rechecked the original statistics cases with the revised prompt: GPT 6/6,
Gemma 6/6, no formatting errors. Total for this round: 48 baseline holdout calls,
48 revised holdout calls, and 12 original-case regression calls = 108 calls.

**Promoted GPT only**, for source-backed multiple-choice quizzes:

- `app/agents/gpt/quiz_policy.py` contains the evaluated checker prompt and
  distinguishing-word eligibility rule.
- `app/agents/quiz.py` selects these only for exact model `gpt-oss:20b` with
  supplied passages. A distinguishable option proceeds to semantic review;
  it is never automatically accepted as true.
- Duplicate options, missing keys, existing rejection decisions, and overlap
  cases without a distinguishing content word remain blocked.
- Llama, Phi, DeepSeek, Gemma, unknown models, and quizzes without source
  passages retain the prior behavior. No model selector or cloud upload route
  was added. Gemma remains evaluated through the runner, not newly exposed in UI.
- Gemma's revised checker remains experimental due to the formatting regression.

Mean checker time on these holdouts: GPT original 4.43s, revised 5.07s; Gemma
original 0.95s, revised 0.67s. GPT's accuracy gain was not a per-call speedup.
Allowing valid overlap drafts may avoid regeneration, but net quiz latency has
not been measured. No extra checks/calls, automatic format-repair retries, or
runtime budget changes were added. Production GPT uses its existing client and
larger reply budget; these equal-budget tests do not establish performance of
that complete production configuration.

Additional reports:
- `data/study-reviews/quiz-overlap-holdouts-trial-20261016.json`
- `data/study-reviews/quiz-overlap-original-trial-20261016.json`

Use `--trial` with either evaluator to reproduce the revised checker. Baseline
evaluation explicitly pins the old prompt even after production GPT promotion.
Tests assert exact equality between tested and promoted prompts, model/source
scoping, preserved negative decisions, and unchanged structural protections.

Verification: 353 tests passed, one skipped. The running server was not
restarted; the GPT policy becomes active on the next app restart. The selected
Llama model was restored after evaluation. No commits or pushes were made.

Next: test complete GPT tutoring/quiz sequences under its production client,
and independently resolve Gemma formatting before promoting its revised path.
Keep the fixed-harness comparison separate from these production optimizations.
