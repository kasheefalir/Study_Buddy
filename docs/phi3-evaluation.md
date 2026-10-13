# Phi-3 Mini Evaluation: 2026-10-13

## Decision

Do not switch the live app to Phi-3 based on this run. It did not improve the
required evidence coverage, retained citation/qualification failures, and was
slower in the like-for-like local tests. Some routing decisions improved, but
the second-pass greeting override still reproduced.

No app model, prompts, or defaults changed. Overrides applied only to benchmark
processes. Phi-3 was unloaded after testing. Phi4-mini was not listed by this
Ollama instance, so it was not tested or downloaded.

## Setup

- Installed `phi3:mini`, ID `4f2222927938`, 3.8B parameters, Q4_0, 2.2 GB download.
  Local `ollama show` reports a 131072-token supported context.
- Same textbook snapshot, chunks 445-447, six questions, two repetitions as the
  earlier Llama selector evaluation. No source, oracle, or prompt edits.
- Phi-3 served as both selector and writer. This tests replacing both roles,
  not whether a Phi selector plus Llama writer would perform better.
- Temperature 0.2; response limit 1200; calls sequential.
- At 16384 context: baseline and minimal variants, 24 trials / 48 model calls.
- At 4096 context: baseline only, 12 trials / 24 calls.
- At 4096 context: existing two-pass routing prompts, eight probes / 16 calls.
- Total: 88 real model calls. JSON schemas worked with its completion capability;
  these tests do not require native tool calling.
- The routing harness now records model, context, temperature, output limit,
  and creation time as well as raw requests and outputs.

## Evidence And Writing

Coverage means inclusion of required oracle IDs across eight answerable trials,
not semantically correct final answers. Precision is mean oracle ID precision.
Abstention requires a valid final response, not simply an error or an internal
fallback placeholder. Error rows are excluded from abstention successes.

| Model / context / variant | Coverage | ID precision | Valid missing-fact abstentions | Validation errors | Median total seconds |
| --- | --- | --- | --- | --- | --- |
| Earlier Llama / 16K / baseline | 6/8 | 20.0% | 4/4 | 0 | 3.03 |
| Phi-3 / 16K / baseline | 6/8 | 25.4% | 3/4 | 1 | 5.05 |
| Earlier Llama / 16K / minimal | 6/8 | 66.7% | 4/4 | 0 | 2.68 |
| Phi-3 / 16K / minimal | 6/8 | 22.9% | 4/4 | 0 | 4.33 |
| Phi-3 / 4K / baseline | 5/8 | 17.5% | 4/4 | 0 | 4.47 |

Manual findings:

- Phi-3 still selected mostly irrelevant spans and omitted necessary comparison
  evidence. Minimal-selection instructions did not deliver Llama's precision gain.
- Both first-round 16K comparisons claimed a distance-ratio trend not established
  by the selected passages. One additionally interpreted an increasing ratio as
  greater disparity. These are not acceptable grounded comparisons.
- The structured-data exception was usefully explained at 16K. At 4K both trials
  omitted the requested exception despite retrieving its supporting span.
- Sampling counts were generally correct, but some responses cited S2/S3 when
  S1 supported the count. Noise responses sometimes added misleading explanation
  or unnecessary S2 citations.
- One 16K baseline missing-number response correctly recognized absent evidence
  but returned `insufficient_evidence` with nonempty `points`, violating the
  contract. This is a validation failure, not hallucinated numerical evidence,
  and not counted as successful abstention. The other 11 negative trials passed.

The 4K evidence calls used at most 1336 actual prompt tokens; routing used at most
1202. Together with the 1200 output cap these fit within 4096 for this test suite.
All 4K responses reported `done_reason=stop`. This does not establish that the
full application's longer histories/material overviews fit in a 4K window.

## Routing

Phi-3 at 4K passed seven of eight final route/mode/pause checks:

- Greeting: 1/2. Both first passes chose conversation; one second pass overrode
  it with retrieval of the old question and incorrectly enabled evidence reuse
  despite the supplied previous evidence being empty.
- Quiz pause: 2/2. Final conversation route and pause flag were correct, although
  the first pass needlessly chose clarification and invented a source question.
- Resume: 2/2.
- Follow-up: 2/2 route checks, but both final queries still contained unresolved
  "that". Route success does not imply useful retrieval-query resolution.

Earlier Llama probes passed four of eight at 16K. Phi-3's result is promising on
this small set, but the context setting also changed; it is not a controlled
model-only routing comparison, an end-to-end test, or proof of robustness.
Keep the proposed separation of intent ownership from retrieval planning on the
roadmap; another model alone did not remove the architectural failure.

## Memory And Speed

Observed `ollama ps` snapshots, 100% GPU on this machine:

| Configured context | Reported loaded model size |
| --- | --- |
| 16384 | 8.9 GB |
| 4096 | 3.8 GB |

Download size is not runtime memory. The 16K setting is unsuitable for the 8 GB
goal. 4K is a more plausible budget but still needs an actual 8 GB device test,
including OS, browser, app, embedding model and peak allocation. These snapshots
are not total system usage or peak measurements.

The 16K baseline median was about 1.7 times the earlier Llama median. Runs were
not simultaneous and include warm-up/cache effects, so do not treat that as a
general speed benchmark. No default context reduction was applied to the app.

## Reports And Reproduction

Private reports remain gitignored under `data/study-reviews/`:

- `phi3-selector-20261013.json`
- `phi3-selector-4k-20261013.json`
- `phi3-routing-4k-20261013.json`

From repository root, with the same imported source and local Ollama, choose fresh
output names to retain prior experiments:

```sh
env OLLAMA_MODEL=phi3:mini python3 -m scripts.evaluate_selector_precision --chunks data/documents/3a4c66034f8a4b6cba7320b89e254ff5/chunks.json --chunk-ids 445 446 447 --title 'Data Science from Scratch' --cases tests/fixtures/evidence_chain_cases.json --oracle tests/fixtures/span_oracle.json --variants baseline minimal --output data/study-reviews/phi3-selector-new.json
env OLLAMA_MODEL=phi3:mini CONTEXT_WINDOW=4096 python3 -m scripts.evaluate_selector_precision --chunks data/documents/3a4c66034f8a4b6cba7320b89e254ff5/chunks.json --chunk-ids 445 446 447 --title 'Data Science from Scratch' --cases tests/fixtures/evidence_chain_cases.json --oracle tests/fixtures/span_oracle.json --variants baseline --output data/study-reviews/phi3-selector-4k-new.json
env OLLAMA_MODEL=phi3:mini CONTEXT_WINDOW=4096 python3 -m scripts.evaluate_route_interruptions --output data/study-reviews/phi3-routing-4k-new.json
```

Verification: 185 tests passed, one opt-in live test skipped. The live model calls
above are separate from that deterministic unit-test count.
