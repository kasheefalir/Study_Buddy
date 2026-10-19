# Material-Bounded Tutoring And Attribution

## Updated Policy

The material defines the topics, not every permissible sentence. A tutor may
explain a covered concept using accurate background or hypothetical examples.
It must not introduce an uncovered concept required to answer the question,
invent author examples, or attribute its explanation to the book.

The isolated candidate separates:

1. **From your material**: a faithful source statement or paraphrase and one
   exact anchor excerpt. Code resolves the excerpt to actual source metadata.
2. **Additional explanation (not stated in the material)**: elaboration, linked
   to the same concept anchor but never presented as text supported in full by
   that citation.
3. **Boundary/limitation**: any uncovered part, missing evidence, or ambiguity.

This does not require a quote for every sentence. An exact anchor proves that
text exists in the source, not that an explanation is correct or in scope.
Those are separate evaluation questions. The candidate does not misrepresent
its string-match validator as a semantic validator.

Retrieved excerpts alone cannot prove a concept is absent from the entire book.
The default input mode is `retrieved_excerpts`. Only a complete material input
allows an absence claim; a live implementation would need a coverage lookup
or additional retrieval before declaring a topic absent.

## Experiment

Files: `app/agents/local_study/bounded_tutor.py`,
`scripts/evaluate_bounded_tutor.py`, `tests/fixtures/bounded_tutor_cases.json`,
and `tests/test_bounded_tutor.py`. No production dispatch changes.

Six short authored synthetic materials/questions, repeated twice for each model:
R-squared explanation, absent logistic regression, mixed covered/uncovered
question, invented-author-example trap, correlation/causation, and median/outlier
arithmetic. Each passage is the complete synthetic material. No private uploads
or conversations are loaded by the runner, including for cloud requests.

Models: Llama 3.2 3B, Phi-4 Mini, GPT-OSS 20B, Ollama `gemma4:31b-cloud`.
Same instruction, schema, passages, temperature 0.1, context request 4096,
output budget 1200. GPT-OSS uses `think=low`, Gemma `think=false`; these provider
controls are logged rather than claimed to be identical reasoning budgets.
Cloud handling of sampling/context options may differ. Local generators run
sequentially and previous generators are unloaded. No model is downloaded.

This isolates generation and attribution, not retrieval, whole-book coverage,
memory fit, or real-world reliability. Repeated low-temperature trials are not
independent statistical samples; observed counts are not calibrated probabilities.

## Scoring

- Exact anchor match: the quotation exists in the supplied passage.
- Material attribution: the claimed source statement is actually supported.
- Added explanation: correct, relevant to a covered concept, and distinguished
  from author content. Check arithmetic and interpretation manually.
- Boundary handling: no uncovered logistic explanation, no invented author
  example, and no omitted covered part in the mixed question.
- Protocol validity: the structured output satisfies code's rendering contract.
  An invalid field layout is reported separately from factual or scope mistakes.
- Consistency: limitations must not contradict the answer they accompany.

Raw results are checkpointed under ignored `data/study-reviews`. Human review,
not the model's own confidence or a second model vote, determines semantic findings.

## Release Status

Experimental; not enabled in the live application.

## Initial Results: 48 Trials

Two repetitions of six cases per model. The initial version supplied the JSON
schema through Ollama's `format` field, but not explicitly in the prompt body.

There are eight trials per model requiring a positive concept anchor: R-squared,
mixed-scope, correlation, and median, each repeated twice. The other four trials
ask about absent information and can legitimately return no quotation.

| Model | Correct existing anchor on positive trials | Valid rendering contract / all trials | Observations |
| --- | ---: | ---: | --- |
| Llama 3.2 3B | 5/8 | 5/12 | Incorrect R-squared interpretation and median arithmetic; logistic scope leakage |
| Phi-4 Mini | 8/8 | 8/12 | Correct median arithmetic; logistic scope leakage and contradictory limitations |
| GPT-OSS 20B | 8/8 | 11/12 | Correct numerical median example; one invented example placed in material-answer field; logistic leakage in one repeat |
| Gemma Cloud | 8/8 | 0/12 | Mostly clear content separation, no logistic expansion; broken JSON/schema contract |

These anchor counts were manually checked against the complete synthetic
passages, including reading fenced cloud JSON for analysis only. The runner did
NOT silently repair or accept those cloud results. This is a single-passage
anchor test, not proof of multi-document citation selection or whole-book recall.

Important semantic observations:

- Llama correctly quoted the R-squared sentence in both repetitions, then said
  80 percent of the points fall close to the fitted line. That interpretation
  is false. It also calculated the mean of 1,2,3,4,5,100 as 31.5 and median as 3;
  the correct values are 115/6 and 3.5. One wrong example passed the anchor check.
- Phi's first R-squared numerical example was internally inconsistent. Its
  second gave an overly confident explanation of all residual variation as
  omitted factors, without acknowledging noise/model error. Both mixed-scope
  responses explained the uncovered logistic concept while the limitation said
  it was not covered. Correlation and median illustrations were substantially
  better, though some limitations contradicted the explanation.
- GPT-OSS's first mixed response explicitly went beyond scope after admitting
  it was outside scope. Its second stayed within the requested boundary but
  overgeneralized the range of R-squared without conditions. Its second median
  answer put the invented numerical example under `material_answer`; a valid
  concept quotation does not make that example the author's example.
- Gemma did not explain the uncovered logistic transformation in either repeat.
  It distinguished the absent author example, and the median illustration was
  sensible. Its R-squared illustration still attributed residual variation too
  confidently to other factors. It used code fences, omitted required fields,
  and substituted invalid statuses such as `complete_material`/`partial_material`.

All four models' source-anchor references are weaker evidence than verified
explanations. There is no justified general probability of reliable attribution
from twelve short trials. No factual check is inferred from schema validity.

Initial raw report: `data/study-reviews/bounded-tutor-20261016.json`.

## Shared Protocol Follow-Up

The only prompt change is to include the same full schema and a no-code-fences
instruction for every model, in addition to the API schema. One repetition per
case/model tests this correction. This small diagnostic cannot establish stable
improvement or authorize live release.

Follow-up report: `data/study-reviews/bounded-tutor-schema-20261016.json`.
All 24 trials completed. No repair/retry calls or provider-specific prompt changes.

| Model | Exact concept anchors / four positive cases | Faithful material-answer fields / four | Rendering contract / six |
| --- | ---: | ---: | ---: |
| Llama 3.2 3B | 4/4 | 3/4 | 6/6 |
| Phi-4 Mini | 4/4 | 4/4 | 4/6 |
| GPT-OSS 20B | 4/4 | 3/4 | 6/6 |
| Gemma Cloud | 4/4 | 4/4 | 6/6 |

This is the most useful distinction for attribution: every positive answer
found a real concept anchor, but Llama and GPT-OSS each put an invented median
example into the supposedly source-only field. Llama's example also contained
wrong arithmetic. Code's citation mapping cannot detect this by quote matching.

The explicit shared schema fixed Gemma's protocol failures and improved Llama's
protocol. Phi's two rejected results expressed appropriate absence boundaries
but put those statements into a field required to be empty; these are formatting
failures, not fabricated answers. Future rendering can handle refusal messages
separately without promoting those fields as material-based explanations.

Semantic review after the change:

- Llama still gave a false R-squared example, wrong median arithmetic, and a
  hypothetical holiday sale as a cause of outdoor temperature. It stopped
  explaining logistic regression but failed to clearly identify the missing
  half of the mixed question and incorrectly called it fully answered.
- Phi clearly declined the logistic part this time. Its correlation and median
  examples were useful. The R-squared example still asserted that all residual
  variation comes from omitted factors; noise and model error were not allowed
  for. It retained some unnecessary or awkward limitation statements.
- GPT-OSS respected the logistic boundary in this pass and computed the median
  illustration correctly, but misplaced that illustration in `material_answer`.
  Its R-squared example also attributed residual variation too confidently.
- Gemma separated material from examples and handled both absent and mixed-scope
  requests correctly in this pass. Its remaining R-squared residual explanation
  needs the same qualification. The cloud result is promising, not a guarantee.

## Decision And Next Work

The new policy, source-anchor mapping, distinct explanation labels, and shared
explicit-schema prompt are implemented in the isolated candidate. The live
strict workflow is unchanged because the small models still have material
accuracy and attribution failures. No model confidence score is treated as proof.

Keep this distinction in the eventual UI: **source reference** versus **concept
reference for an added explanation**. Never mark an explanation verified merely
because its anchor exists. For the small models, next test short, single-concept
explanations, code-checked arithmetic examples, and separate source/explanation
generation so an example cannot be placed into the source-only field. Each is
a candidate intervention, not yet a demonstrated fix. Test whole-book concept
coverage and multi-source attribution before deployment.

72 total model trials (48 initial + 24 follow-up), using synthetic material only.
285 unit tests passed, one skipped. The observations are not calibrated success
probabilities and do not establish larger-model superiority in general.

## Follow-Up And Topic-Change Evaluation: 2026-10-16

84 additional local model calls: 64 connected-stage probes, 12 planner replays,
and 8 held-out planner calls. No uploaded documents or cloud calls were used.
These are production routing/planning prompts plus an isolated writer with fixed,
synthetic evidence, NOT end-to-end retrieval or live-app answer tests.

Inspection corrected an earlier assumption: production `structured_messages`
already supplies its schema in the system prompt as well as the API format.
Do not add it a second time. New tests lock that contract for every registered
stage and verify separation of user data from system instructions.

### Connected Sequence

Two repetitions per model of: R-squared definition, simpler explanation,
hypothetical example, then logistic-regression training outside the material.
Each turn compares the isolated writer without a resolved question against the
same writer with the production planner's resolved question. The original user
question is retained separately. Both variants share the candidate conversation
history for routing; this is a paired writer probe, not two independent chats.

Reports (local ignored evaluation data):

- `data/study-reviews/tutor-followups-20261016.json`
- `data/study-reviews/followup-planner-20261016.json`
- `data/study-reviews/followup-heldout-20261016.json`

| Model | Baseline renderable | Resolved-question renderable |
| --- | --- | --- |
| Llama 3.2 3B | 8/8 | 8/8 |
| Phi-4 Mini | 5/8 | 4/8 |

Renderable means schema and exact-anchor checks, NOT factual correctness.
Llama still confused explained variation with a percentage of data points.
The candidate kept hypothetical examples out of its source-only field more
often, but still made unsupported residual-variation claims. Phi sometimes
marked a useful explanation `outside_material`, altered an exact quote, or
continued the old R-squared topic after a new logistic-regression question.
One baseline Phi refusal still included logistic-training advice, contrary to
the requested topic boundary. Do not normalize these responses into successes.

Writer-only median seconds: Llama 3.52 baseline / 3.79 candidate; Phi 5.35 /
6.07. Routing uses configured production budgets; writers use 4096 context,
1200 output, temperature 0.1. Model/context loading and shared caches affect
these numbers; this is not a controlled speed or 8GB RAM benchmark.

### Planner Correction And Holdout

Tested an additional instruction to retain the subject, requested operation,
qualifications, and latest topic even when the router's query is stale.
On the saved six Llama follow-up/topic-switch inputs, manually reviewed query
fidelity improved from 2/6 to 6/6. Phi retained its four good follow-up queries
but still failed both topic switches; one failure also changed evidence reuse
from false to true despite the absent topic.

Four additional Llama inputs covered median examples, simplifying correlation,
mean/median comparisons with an example for each, and a photosynthesis topic
change. The candidate still dropped the hypothetical-example request for the
median. More importantly, it removed the examples from a multipart comparison
that the baseline had preserved. This is a regression, so the planner addition
is NOT enabled, including for Llama.

### Promotion Decision

- Preserve the already-live explicit-schema behavior, with regression coverage.
- Keep resolved-question writer guidance and planner guidance isolated.
- Do not replace the live writer or modify GPT/DeepSeek workflows.
- The next experiment should preserve original user requirements independently
  of the generated search query, so a query rewrite cannot silently remove a
  requested example or comparison. Test this against the saved holdouts as well
  as the original cases; do not assume improved queries imply accurate answers.

304 unit tests passed, one skipped. The app remains on Llama 3.2 3B.

### Subsequent Quiz Evaluation

See [Five-Question Quiz Comparison](quiz-comparison-evaluation.md) for the
2026-10-16 fixed-evidence quiz tests, separate fallback conditions, factual
failures, and the narrowly promoted lossless quiz-output parsing improvement.
