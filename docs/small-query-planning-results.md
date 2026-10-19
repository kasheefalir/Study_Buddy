# Small-model query planning trial

## 2026-10-15: Tested, not promoted

Implemented an opt-in query-planning and explanation experiment in
`app/agents/query_plan_trial.py`, with a repeatable runner in
`scripts/evaluate_small_query_plans.py`. Production routing and writers are unchanged.

Private result artifact: `data/study-reviews/small-query-plans-20261015.json`.
Do not commit uploaded passages or this private report.

### Method

- Llama 3.2 3B and Phi-4 Mini; six questions each, two variants: 24 attempted turns.
- Materials: Data Science from Scratch, Introduction to R, and Logistic Regression 2 slides.
- Compared the existing single-query planning prompt with a standalone-question,
  multi-query prompt that also preserves the original question as a search.
- Both variants used the same experimental writer, separating source-based text
  from optional additional context labeled unverified. This is not a comparison
  against the entire production writer/checker pipeline.
- Summaries used the existing document overview/coverage path in both variants.
- Intent and selected material were supplied by fixtures. Follow-up history was
  seeded identically. This does not test live intent routing or task transitions.
- One run per case, sequential models, alternating variant order. No 8 GB memory
  benchmark or statistically reliable speed comparison was performed.

### Observations

| Case | Llama 3.2 | Phi-4 Mini |
| --- | --- | --- |
| Centrality comparison | Multi-query still combined concepts; retrieved betweenness but missed the degree-definition target. Claimed a comparison without adequate retrieved support. | Single-query missed both target chunks. Multi-query failed material-ID validation. |
| Contextual follow-up | Both variants resolved betweenness and retrieved its definition. | Single-query resolved the subject; multi-query failed material-ID validation. |
| Whole-material summary | Both covered major R topics. Multi-query invented external URL queries, but these were not executed because the overview path handled the request. | Both produced useful topic summaries from the existing generated overview. |
| Two fare coefficients | Both retrieved relevant evidence but omitted the Southwest coefficient. | Both included the distance and Southwest coefficients; extra commentary in the single-query answer contradicted its own supported answer. |
| Missing random seed | Both declined to invent the number. | Both declined to invent the number. |
| Missing laptop specifications | Both declined to invent specifications. | Both declined to invent specifications. |

All eight missing-information answers avoided fabricating the requested details.
Some Phi answers asserted absence from the whole document rather than limiting
the claim to retrieved evidence; these are not proofs of document-wide absence.

All 22 completed writer outputs contained unknown structured source IDs: models
typically copied document UUIDs instead of passage labels such as S1. One also
included a valid S1. Inline citation validity was not comprehensively verified.
The experiment records unknown IDs and resolves valid IDs to stored passages;
it does not certify that a cited passage supports a claim.

Summary coverage was complete via the cached generated hierarchy (27 represented
chunks, zero original chunks in the writer payload). Coverage is not independent
validation of summary accuracy.

### Evaluation limitations

The multi-query branch rejects out-of-session material IDs. The single-query
branch records its plan but searches the fixture's selected book regardless of
the returned IDs. Phi also mistyped IDs in single-query plans. Consequently the
two multi-query validation errors cannot establish that the single-query planner
is more reliable. Future comparisons need identical validation for both branches.

The source-based/extra-context split is a labeling experiment, not a grounding
guarantee: unsupported statements still appeared inside the source-based field.
Do not present that field as verified just because the model placed text there.

### Retain And Next Steps

Retain contextual question resolution, original user wording, document-scope
validation, summary coverage, and the missing-information test cases. Keep the
new workflow opt-in: no consistent quality improvement justifies replacing live
behavior yet.

Next controlled trial: constrain material and passage IDs to schema enums, apply
the same validation to both variants, and require separate comparison subquestions
without silently dropping either part of a multipart request. Evaluate retrieval
coverage separately from writer completeness. A valid ID only fixes attribution
format, not semantic support. Do not add another generic refusal checker.

Verification: 255 tests passed, one skipped, including four new focused tests.

## 2026-10-15: Grouped evidence and constrained IDs

Implemented a separate opt-in `app/agents/small_models/` workflow and runner
`scripts/evaluate_small_grouped.py`. Private artifact:
`data/study-reviews/small-grouped-20261015.json`.

Twelve more attempted turns (the same six cases on each model) all completed.
Two model calls per turn, no checker or retry. Dynamic schema enums restricted
material aliases and each answer part's passage IDs; code rendered references.
All returned material and passage IDs passed membership validation. Duplicate
citations remained possible and were deduplicated for rendering. Every planned
part received an answer; this does not mean every original user requirement was
preserved or correctly answered.

### Results

- Llama split the centrality comparison into separate concept queries. Retrieval
  still missed the degree-definition target and the writer incorrectly described
  degree centrality using shortest paths. This is not an acceptable answer.
- Phi retrieved both target definitions, unlike its earlier single-query trial.
  Its answer distinguished direct connections from shortest-path roles, but
  still oversimplified betweenness and included claims needing support review.
  It created three parts, including a redundant combined comparison.
- Both models rewrote the two-coefficient fare question as repeated per-mile
  questions. Llama omitted the Southwest difference; Phi put that difference
  only in additional context. Structured completeness did not prevent intent loss.
- Both resolved follow-ups but generated redundant parts. Summary coverage used
  the existing overview path; Phi unnecessarily expanded a summary into three
  parts. These duplicate parts increase context and output work.
- Both avoided inventing a random seed.
- Both regressed on the missing-laptop case: the answer was literally `M1`, the
  material alias. Phi explicitly claimed the evidence specified that laptop.
  Phi's planner also generated `M1` and `Not specified` as search queries. The
  new prompt/structure therefore did not preserve prior abstention behavior.

Observed end-to-end latency: Llama 4.41-13.29 seconds (median 6.47); Phi
9.95-31.82 seconds (median 13.90). These are single-run local timings, not an
8 GB memory test or controlled throughput benchmark. The comparison payload
could reach 18 passage entries (six per part), with duplicates between groups;
the two-call design alone does not guarantee low latency.

### Decision

Do not enable this grouped workflow in production. Keep enum-constrained IDs
and code-owned reference rendering as promising mechanics, not a validated
grounding solution. GPT-OSS, DeepSeek and the live small-model workflow remain
unchanged. No UI warning or model-dispatch changes were made in this experiment.

Before another trial, remove material aliases from the writer payload, keep
planner control metadata separate from evidence, and test the alias-confusion
case explicitly. Limit redundant parts and total evidence budget; preserve the
original multipart intent. Evaluate these changes separately instead of adding
another semantic checker or claiming all structural changes improved accuracy.

Verification: 258 tests passed, one skipped. New tests cover short-ID schema
constraints, unknown materials, missing sections, cross-part source rejection,
and storage-ID isolation in evidence payloads. These mechanical tests do not
establish model answer accuracy.

## 2026-10-15: Explicit metadata, exact quotes, independent answers

Implemented `small_models/quoted_trial.py` as another opt-in variant, preserving
both earlier experiments. Source aliases are explicit SOURCE_001 identifiers;
writer passage references are PASSAGE_001. Control metadata is separate from
passage text. The writer never receives material aliases or planner queries.
Each planned focus is checked as an exact original-question span. The original
question is retained, each focus is answered in its own call, and code combines
claim/quote records without a further synthesis model. The final deterministic
renderer also displays quotes beside claims (unit-tested after the model runs).

The validator requires every accepted claim to contain an exact, nonempty quote
from its cited passage within that part's evidence. It rejects unknown IDs,
missing fields and non-verbatim quotes. A unit test explicitly demonstrates the
limit: an irrelevant but exact quotation can pass provenance validation. This
does not certify factual entailment or completeness. There is no free-form,
uncited factual answer field in the accepted output.

### Same-case model run

Private artifact: `data/study-reviews/small-quoted-20261015.json`.
Twelve attempts, six per model. Nine completed; three failed exact-focus
validation (both follow-ups and Phi's laptop question). Eight completed turns
abstained. Only Phi's fare answer produced claims: both coefficients were correct
and both quotes matched Slide 4 exactly. It omitted the explicit constant-other-
variables qualification from claim prose, though that qualification was present
in the displayed supporting quotes. This is useful evidence, not consistent
success. Llama refused the same answerable fare question despite retrieving it.

Both planners kept the comparison and fare requests combined instead of
decomposing them. Phi also copied planner instruction text into a random-seed
search query. The validator catches copied-focus errors but cannot establish
that an apparently valid decomposition preserves all meaning.

No accepted answer repeated the M1 laptop hallucination. However, Phi's laptop
plan failed before answering, so this must not be described as a clean automatic
abstention success for both models. Summary questions were falsely refused even
with complete generated overview coverage.

### Diagnostic With Human-Specified Parts

Private artifact: `data/study-reviews/small-quoted-oracle-20261015.json`.
Twelve additional turns bypassed the planner with explicit human-defined parts
and focused queries. Recent dialogue was passed to the independent writers for
follow-ups. All twelve completed and all abstained, including fare, follow-up
and summary cases with relevant evidence. Both centrality searches still missed
the degree-definition target while retrieving the betweenness target.

These results isolate a writer failure in addition to planner and retrieval
failures: exact-quote instructions/schema caused frequent model-chosen refusals
before validation. The validator did not reject the real-run answers; most had
no claims to validate. Do not credit abstention-heavy runs as accuracy gains or
infer that quote copying is reliable from the two successful fare claims.

### Decision And Verification

Not promoted. Neither production model dispatch nor GPT-OSS/DeepSeek workflows
changed. The requested quote and metadata mechanisms are implemented, but the
automatic decomposition and useful factual answering remain unreliable. No
consistent factual-quality improvement was demonstrated, and no additional
checker or automatic repair was added to disguise the failures.

262 tests passed, one skipped. New tests cover exact quote membership, unknown
and cross-part sources, mandatory claims/quotes, exact question spans, control
metadata isolation, independent calls and deterministic combination. Private
reports preserve raw writer outputs and validation results for inspection.

## 2026-10-15: Narrow Production Promotion

Promoted only the successful ID-membership mechanism, via
`small_models/source_constraints.py` and the existing `study_tools.structured`
entry point. Llama 3.2 3B and Phi-4 Mini now receive document-ID enum constraints
for retrieval planning, material tool selection and retrieval sufficiency.
Post-parse validation also rejects out-of-scope IDs, including when the client
does not enforce schemas. Empty scope permits only an empty selection.

No aliases, quote requirements, decomposition or new writer were promoted.
Existing passage-label enums and code-rendered citations in `grounded_answer.py`
already provide the corresponding citation-format mechanics. Intent, quiz and
larger-model schemas are unchanged. No model calls were added.

Verification: all twelve real retrieval-planner calls (six existing material
cases per small model) returned in-scope document IDs through the production
helper. This is a mechanical ID reliability result, not a new factual accuracy
claim or end-to-end tutoring benchmark. Unit tests cover all three constrained
stages, empty scope, schema immutability, invalid-ID rejection and unchanged
GPT-OSS/DeepSeek schema behavior. Full suite: 270 passed, one skipped.
