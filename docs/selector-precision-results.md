# Selector Precision Experiments: 2026-10-13

## Decision

Keep these changes experimental. Preserve the previous explicit-abstention writer
unchanged. No live app configuration, prompts, or routing changed in this run.
No server restart is needed. The existing server does not use this harness.

Implemented `scripts/evaluate_selector_precision.py`, four mechanical unit tests,
held-out probability fixtures, and a separate production-prompt routing probe.
Ran 220 real `llama3.2:3b` calls: 132 development, 72 held-out, 16 routing.
Full suite: 185 passed, one opt-in live test skipped. Diff whitespace check passed.

## Protocol

- Development: Data Science from Scratch chunks 445-447, six questions, twice.
- Held-out: probability chunks 229-231, six different questions, twice. The
  questions and span oracle were frozen before the held-out calls.
- Writer: existing `evaluate_writer.candidate_request` XML candidate, temperature
  0.2, identical across variants. This is the previously evaluated candidate,
  not a claim that the live server uses this writer.
- Selector variants change one feature at a time: visible schema, temperature
  zero, three unrelated few-shot examples, question-part coverage JSON, or minimal
  sufficient selection. Original selector is the baseline.
- Source hash, original spans/offsets, oracle, writer file hash, requests, schema,
  raw responses, usage, errors, temperatures and latency are saved per run.
  Model calls never receive the oracle. Output paths cannot overwrite old runs.
- Calls ran serially, with variant order rotated. Latencies include local
  caching/warm-up effects; they are not independent hardware benchmarks.
- No retriever settings changed: fixed evidence isolates selector/writer behavior.
  These results do not measure end-to-end retrieval recall.

## Development Results

Coverage counts inclusion of all required oracle IDs over eight answerable trials.
Precision is the mean selected-ID precision over those trials. Empty selection
has undefined precision. Missing-fact abstention measures the final writer output.

| Variant | Required-ID coverage | Mean ID precision | Missing-fact abstention | Median seconds |
| --- | --- | --- | --- | --- |
| Baseline | 6/8 | 20.0% | 4/4 | 3.03 |
| Schema in prompt | 5/8 | 17.5% | 4/4 | 4.23 |
| Selector temperature zero | 8/8 | 25.0% | 4/4 | 2.78 |
| Few-shot examples | 6/8 | 48.7% | 4/4 | 3.46 |
| Question-part coverage | No valid selections | N/A | No writer calls | 3.01 |
| Minimal selection | 6/8 | 66.7% | 4/4 | 2.68 |

Coverage JSON failed semantic validation in all 12 trials: the model returned
`supported` with empty evidence. Valid JSON did not mean a valid decision.
No invalid selection was passed to synthesis or counted as an abstention success.
The untested combined variant is available for future experiments, not endorsed.

Manual inspection found:

- Temperature zero included both comparison spans in both trials, but the writer
  still attached S2 to claims supported by S3. Coverage did not fix citations.
- Minimal selection and examples produced useful direct noise explanations;
  minimal selection instead chose the ratio formula for both comparison trials.
- Baseline often filled all five available slots with mostly unrelated spans.
- Schema visibility alone did not help this task; one answerable sampling trial
  became an abstention. Its second comparison added a ratio trend not explicitly
  established by its selected text.
- Sample counts were often correct but repetitive and attached to extra sources.

## Held-Out Results

Selected temperature zero for development coverage and minimal selection for
precision. Tested each against the baseline on the untouched probability cases.

| Variant | Required-ID coverage | Mean ID precision | Missing-fact abstention | Median seconds |
| --- | --- | --- | --- | --- |
| Baseline | 7/8 | 62.5% | 4/4 | 4.12 |
| Selector temperature zero | 6/8 | 63.3% | 4/4 | 3.78 |
| Minimal selection | 6/8 | 80.0% | 4/4 | 3.46 |

Minimal selection kept the fair-coin answer to the directly relevant span in
both trials. It still selected distracting material for the dependence comparison
and conditional-probability question. Citations continued to migrate between
sources, and extracted probability notation was already damaged in the PDF text.

Exact-ID coverage is a diagnostic, not answer accuracy: for example, a selection
can omit S1's short independence definition but include S3's equivalent
information-based explanation. Manual review remains necessary. Precision also
depends on the predeclared allowed spans, not a universally correct semantic judge.

Across both datasets, the frozen writer abstained on all 32 completed missing-fact
trials (four unique negative questions repeated across variants). The selector
itself wrongly approved evidence on every one. Preserve the writer's independent
abstention option; selector approval must not force an answer. This small test set
does not establish a general hallucination rate or guarantee safe abstention.

## Routing Is A Separate Failure

`scripts/evaluate_route_interruptions.py` ran two existing production intent
prompts on four independent synthetic contexts, twice. It does not modify a live
conversation or test the full application state transition.

- Greeting: 0/2 final routes correct. First pass recognized conversation in both;
  second pass incorrectly overrode it with retrieval of an old material request.
- Pause: 0/2 complete decisions correct. Conversation route was correct, but both
  passes left `pause_activity=false` despite the explicit pause request.
- Resume: 2/2 final routes/modes correct.
- Follow-up: 2/2 routes/modes correct, but both final queries retained the unresolved
  phrase "that" despite a more explicit first-pass query. Route success is not
  proof of useful retrieval-query resolution.

Next focused routing experiment: make the second pass resolve references and
resource scope without silently replacing a correctly understood latest intent.
Test interruption/pause and nuanced return-to-study cases before promotion. This
is not justification for a greeting keyword router.

## Preserve / Do Not Repeat Blindly

Preserve code-resolved original span IDs, writer abstention, immutable experiment
reports, separate routing probes, and held-out checks. Minimal selection is a
useful precision candidate, not a complete improvement. Do not promote temperature
zero solely on the development 8/8 result. Do not stack the failed coverage schema
or assume more examples fix comparisons. The next evidence experiment should
target per-claim citation binding while preserving comparison context and the
same abstention writer, rather than another generic prompt rewrite.

## Reproduction And Privacy

Reports are local and gitignored under `data/study-reviews/`:

- `selector-precision-20261013.json`
- `selector-probability-20261013.json`
- `route-interruptions-20261013.json`

Run from the repository root with Ollama available; use fresh output names:

```sh
python3 -m scripts.evaluate_selector_precision --chunks data/documents/3a4c66034f8a4b6cba7320b89e254ff5/chunks.json --chunk-ids 445 446 447 --title 'Data Science from Scratch' --cases tests/fixtures/evidence_chain_cases.json --oracle tests/fixtures/span_oracle.json --output data/study-reviews/selector-precision-new.json
python3 -m scripts.evaluate_selector_precision --chunks data/documents/3a4c66034f8a4b6cba7320b89e254ff5/chunks.json --chunk-ids 229 230 231 --title 'Data Science from Scratch' --cases tests/fixtures/selector_probability_cases.json --oracle tests/fixtures/selector_probability_oracle.json --variants baseline temperature_zero minimal --output data/study-reviews/selector-probability-new.json
python3 -m scripts.evaluate_route_interruptions --output data/study-reviews/route-interruptions-new.json
python3 -m pytest -q
```

Fixtures contain questions and source hashes/IDs, not the textbook passages. Local
reports contain private source text and should not be committed. Source snapshots
must match the oracle hash and chunk order or the harness refuses the run.

Documentation basis: [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
recommends schema visibility and low temperature, but does not promise factual
accuracy. These tests measure those suggestions rather than assuming they work.
Continue using the installed chat template; do not add Llama special tokens inside
ordinary `/api/chat` messages. Production `structured_messages` already includes
the schema in the prompt; that was not a missing production routing feature.
