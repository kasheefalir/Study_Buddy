# Phi-4 Mini Evaluation: 2026-10-13

## Decision

Keep as a candidate, not the live default. Phi-4 Mini improved some evidence
selection, abstention, and conversational decisions, but did not reliably ground
answers on the second chapter. No app model, prompts, or context defaults changed.
The benchmark model was unloaded after completion.

## Setup

- Local `phi4-mini:latest`, ID `78fad5d182a7`, 3.8B, Q4_K_M, 2.5 GB download.
  `ollama show` reports 131072 supported context, completion and tools capabilities.
- Same prompts, temperature 0.2, 1200 output limit, source snapshots and frozen
  oracles as the previous tests. Phi-4 performed both selection and writing.
- Dimensionality chunks 445-447: six questions, twice, baseline and minimal at
  16K context (38 calls); baseline at 4K (20 calls).
- Existing probability fixtures, chunks 229-231: six questions twice, baseline
  at 4K (20 calls). No fixture or prompt tuning for this chapter.
- Existing two-pass routing probes at 4K: four cases twice (16 calls).
- Total 94 real local model calls. Fewer calls than Phi-3 because some selections
  abstained before writing, and invalid duplicate IDs also skipped writing.
- Private JSON reports preserve prompts, raw output, usage, errors and timings.
  No full live-app conversation, quiz, or 8 GB hardware acceptance test was run.

## Evidence Results

Required-ID coverage counts eight answerable trials per row; it is not final
answer accuracy. Precision averages oracle ID precision for valid selections on
answerable cases, excluding validation failures. Abstention requires valid output;
an error row's initialized fallback field is never counted as success.

| Model / context / variant | Coverage | Mean ID precision | Missing-fact abstention | Errors | Median seconds |
| --- | --- | --- | --- | --- | --- |
| Earlier Llama / 16K / baseline | 6/8 | 20.0% | 4/4 | 0 | 3.03 |
| Earlier Phi-3 / 16K / baseline | 6/8 | 25.4% | 3/4 | 1 | 5.05 |
| Phi-4 / 16K / baseline | 6/8 | 38.9% | 4/4 | 2 | 3.32 |
| Phi-4 / 16K / minimal | 6/8 | 52.8% | 4/4 | 2 | 3.43 |
| Earlier Phi-3 / 4K / baseline | 5/8 | 17.5% | 4/4 | 0 | 4.47 |
| Phi-4 / 4K / baseline | 8/8 | 45.0% | 4/4 | 0 | 3.95 |

All four 16K Phi-4 errors were duplicate span IDs on the sampling-count case.
The relevant S1:P2 ID was present, sometimes twice by itself. This is a mechanical
contract failure, not evidence that the model could not find the count. A future
explicitly tested deduplication step could remove that obstacle; no normalization
was introduced mid-benchmark or retroactively counted as a successful answer.

Manual review:

- Phi-4 selected both comparison sides in all four 16K trials and both 4K trials.
  The 16K answers nevertheless substituted average-distance growth for the exact
  high-dimensional nearest-versus-average contrast. The 4K first comparison added
  an incorrect decreasing-ratio claim; the second comparison attributed its
  low-dimensional statement to S2 when S3 supplied it.
- Baseline exception answers were useful at both context sizes. The 16K minimal
  variant falsely abstained in both exception trials despite selected support.
- Baseline 16K noise explanations were useful. The minimal variant added claims
  about exponential volume/sparsity and generalization not present in its selected
  evidence. Good source selection did not prevent unsupported expansion.
- 4K sampling answers gave the correct count but added S2 citations to S1 facts.
- Across dimensionality variants, all 12 missing-fact trials ended in valid
  abstention; 10 were rejected by the selector itself. Earlier Llama/Phi-3 selectors
  tended to approve irrelevant evidence and rely on writer abstention instead.

## Second Chapter

Probability at 4K: required-ID coverage 4/8, mean ID precision 50.4%, two writer
validation errors, one valid but unnecessary abstention, median 3.92 seconds.
All four missing-fact cases were correctly rejected by the selector.

- Conditional-probability trial one selected the explicit nonzero restriction
  but the writer abstained. Trial two answered from neighboring text despite
  missing the oracle's preferred S2:P3 ID, illustrating the limit of exact-ID
  coverage as a semantic metric.
- Both independent-update trials missed S3:P2, the direct explanation, and returned
  `status=answered` with an empty points list. These are errors, not abstentions.
- One dependence answer falsely said dependent events have nonzero joint
  probability. The source's own dependent-events example had joint probability
  zero. This is a substantive grounding failure, not just a citation mismatch.
- Fair-coin answers included unnecessary S2 material about a different event pair,
  creating citation confusion or distracting discussion of dependence.

Overall, negative-case abstention was 16/16 across four unique negative questions
and repeated variants. That is promising but does not offset false claims on
answerable questions or establish a general reliability rate.

## Routing

Final route alone was correct in 8/8 probes. Complete route/mode/pause decisions
passed 5/8:

- Greetings 2/2; no second-pass retrieval override in these trials.
- Quiz pause 2/2 with `pause_activity=true`.
- Resume 0/2 complete: correct retrieve route, wrong `summary_material` mode for
  a focused explanation.
- Follow-up 1/2 complete: both retrieved with a concrete resolved query, but one
  incorrectly selected broad summary mode.

Phi-3 at the same 4K setting passed 7/8 complete checks but still failed a greeting
and left follow-up queries unresolved. Thus neither model dominates all routing
behaviors. Conversation probes are synthetic and independent, not a stateful
application acceptance test. Separation of intent ownership from retrieval
planning remains worth testing. Native tools capability did not solve grounding;
these harness calls use JSON schemas, not native tool dispatch.

## Memory And Timing

Observed `ollama ps` loaded sizes, 100% GPU on this host:

| Model | 16K context | 4K context |
| --- | --- | --- |
| Phi-3 Mini | 8.9 GB | 3.8 GB |
| Phi-4 Mini | 4.8 GB | 3.1 GB |

Phi-4 has a more favorable measured footprint. These are snapshots, not peak or
total-system usage; they do not prove the app fits an 8 GB device with OS/browser
and embeddings. Largest actual 4K prompt was 1470 tokens across these runs, leaving
room for the 1200-token output cap. All outputs reported `done_reason=stop`.
The full application's longer contexts were not tested at 4K.

Phi-4's 16K baseline median was lower than Phi-3's, but abstentions and duplicate-ID
errors skipped writer calls, so this is not an apples-to-apples generation-speed
benchmark. Historical runs also differ in warm-up/cache state.

## Reproduce And Preserve

Gitignored reports in `data/study-reviews/`:

- `phi4-selector-20261013.json`
- `phi4-selector-4k-20261013.json`
- `phi4-routing-4k-20261013.json`
- `phi4-probability-4k-20261013.json`

Run the commands in [the Phi-3 report](phi3-evaluation.md), replacing
`OLLAMA_MODEL=phi3:mini` with `OLLAMA_MODEL=phi4-mini:latest` and using fresh output
names. For the second chapter:

```sh
env OLLAMA_MODEL=phi4-mini:latest CONTEXT_WINDOW=4096 python3 -m scripts.evaluate_selector_precision --chunks data/documents/3a4c66034f8a4b6cba7320b89e254ff5/chunks.json --chunk-ids 229 230 231 --title 'Data Science from Scratch' --cases tests/fixtures/selector_probability_cases.json --oracle tests/fixtures/selector_probability_oracle.json --variants baseline --output data/study-reviews/phi4-probability-4k-new.json
```

Verification: 185 tests passed, one opt-in live test skipped. No production edits.
