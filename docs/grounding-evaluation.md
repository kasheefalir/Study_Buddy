# Grounding Evaluation

Latest follow-up: [intent ownership and code-owned attribution](stage-ownership-results.md).
Separated intent/planner responsibilities promoted; live grounded writer unchanged.
Final routing probes passed 8/8 on each model after a Phi resume correction. Code-bound citation
experiments still produced unsupported claims or invalid outputs; not promoted.

Earlier follow-up: [Phi-4 Mini model comparison](phi4-evaluation.md).
94 real calls: favorable memory, better greeting/pause decisions and negative-case
selection, but second-chapter false claims, missed evidence and contract failures
remain. Measured loaded size: 4.8 GB at 16K, 3.1 GB at 4K. Live app unchanged.

Earlier follow-up: [Phi-3 Mini model comparison](phi3-evaluation.md).
88 real calls: no writer/selection upgrade justified; the greeting override still
occurs. Loaded Phi-3 measured 8.9 GB at 16K context versus 3.8 GB at 4K. Live model
unchanged. Phi4-mini was not present in the local Ollama inventory.

Earlier follow-up: [selector precision ablations and held-out routing probes](selector-precision-results.md).
220 real calls: minimal selection improved precision but lost coverage; temperature
zero did not generalize its coverage gain. Preserve the writer's 32/32 observed
missing-fact abstentions. The second intent pass reproduced the greeting error.
No production promotion.

Earlier follow-up: [span-ID selection and manually verified evidence](span-selection-results.md).
ID selection eliminated quote-copy errors but overselected irrelevant spans and
missed one comparison side. Preserve the previous explicit-fallback writer:
the simpler code-bound writer regressed on absent facts. No production promotion.

Earlier follow-up: [rewrite, neighboring-context, and citation-mapping tests](evidence-refinement-results.md).
The 110-call follow-up did not justify promotion. Literal citation regression
checks are useful; none of these selection changes reliably fixed the missed
answer or incomplete comparison. Keep prior successes and failures below.

## Evidence Selection Experiment: 2026-10-13

Decision: keep experimental, not promoted to the running app. Tested real
llama3.2:3b against the same three imported PDF chunks (445-447), six questions,
two rounds, 30 model calls. No model-based judge was used for the results below.
This isolates evidence selection/writing, not retrieval or conversational routing.

Compared the previous explicit-fallback JSON writer candidate with two paths:
code-rendered verified excerpts, and synthesis from only the original chunks
selected by the gatekeeper. The gatekeeper is shared between those two paths.
Synthesis retains the abstention option. It receives selected full chunks to
preserve context, not just the quoted spans. The baseline is NOT the production
writer. XML/metadata also differ from baseline, so this is not a clean ablation
of evidence selection alone.

### Working / Preserve

- All three paths correctly abstained on all four missing-information trials
  (two questions, twice). Selection skipped synthesis on these trials.
- All 17 displayed extractive quotations matched their cited source. Code checks
  source IDs and exact text, tolerates whitespace only, then renders original
  matched text. This verifies provenance, NOT relevance or answer completeness.
- Sampling count and the structured-data exception were answered successfully
  by both selected-evidence paths in both rounds: four answerable trials.
- Unselected chunks are excluded from synthesis; source labels remain stable.
- Offline validation covers altered text, wrong/unknown sources, whitespace,
  contradictory status/evidence, and source exclusion. Full suite: 169 passed,
  one opt-in live checker test skipped. These tests establish mechanics only.

### Mixed / Not Solved

| Case (two runs each) | Explicit-fallback baseline | Verified excerpts | Selected-chunk synthesis |
| --- | --- | --- | --- |
| Low/high-dimensional comparison | Extra unsupported claims; first run contradicts source sampling example | Authentic but incomplete: omits explicit high-dimensional contrast | Both runs miscite low-dimensional claim as S2 instead of S3; extra inferred claims |
| Structured-data exception | Unsupported padding or confused explanation | Correct, with unnecessary extra text | Correct narrow answer |
| Extra noisy dimension | Unsupported padding, then false abstention | Both rejected on source-text verification | Skipped after gate rejection |
| Sampling count/dimensions | Correct factual answer, repetitive | Correct | Correct concise answer |
| Exact ratio at dimension 73 | Correct abstention | Correct abstention | Correct abstention; synthesis skipped |
| Regularization method/parameter | Correct abstention | Correct abstention | Correct abstention; synthesis skipped |

Of eight answerable trials, the extractive path supplied four complete answers,
two incomplete comparisons, and two fallbacks. Synthesis supplied four clean
answers, two comparisons with citation/grounding errors, and two fallbacks.

The noisy-dimension failures need careful interpretation: the model joined
`higher-` and `dimensional` across a PDF line break. Whitespace-only validation
rejects that change; it is not evidence of fabricated content. Independently,
the selector omitted the directly relevant noise sentence and claimed the
reason was absent. Relaxing text matching alone would not fix answer coverage.
Both runs also used supported status alongside missing-information commentary,
so that field should not be treated as a reliable explanation of the decision.

### Timing And Limits

Median baseline writer: 3.54 s; selection: 4.61 s; completed selection+synthesis:
8.20 s (six synthesized answers). Missing-information selection median: 1.15 s.
Overall chain median including skips/rejections: 5.67 s. These are local ordered
calls, not randomized end-to-end latency or memory measurements on an 8 GB
machine. One chapter, six questions, and two repeats are a small diagnostic set,
not a general accuracy benchmark. No additional model or reranker was loaded.

### Reproduction And Tracking

```sh
python3 -m scripts.evaluate_evidence_chain \
  --chunks data/documents/YOUR_DOCUMENT_ID/chunks.json \
  --chunk-ids 445 446 447 --title 'Data Science from Scratch' \
  --cases tests/fixtures/evidence_chain_cases.json \
  --output data/study-reviews/evidence-chain-20261013.json
```

The ignored local report stores every raw response, request, schema, source text,
source hash, timing, validation error, and rendered result. Keep this private;
the repository contains only the reusable harness, cases, tests, and findings.
Report: `data/study-reviews/evidence-chain-20261013.json`.

Next candidate, not implemented: select preassigned sentence/span IDs instead of
copying excerpts, with code returning the original text and neighboring context.
Retest these same cases before adding new ones. Require preservation of the four
correct missing-answer outcomes and four successful narrow answers, improvement
on noisy-dimension coverage, and correct S3 comparison citations before promotion.
Do not stack another generic checker or weaken provenance checks to hide failures.

## Writer Input Experiment: 2026-10-13

Standalone experiment only; production routing, retrieval, checker, and server
were not changed. Used llama3.2:3b, the same three original PDF chunks (445-447),
three fixed questions, and two runs: 18 calls total. The current source-writer
request was captured directly before its first model call as the baseline.

Variants:

- Baseline: existing prompt/schema requiring at least one point, JSON evidence.
- Escape JSON: shorter prompt and a validated answered/insufficient_evidence
  outcome, with empty points required for abstention.
- Escape XML + headers: same candidate prompt/schema, XML-escaped evidence with
  document title and section/location, and the question after the context.

Observed results (manual comparison with actual source text, not model judging):

- Both candidates abstained correctly on 4/4 missing-information trials each:
  an exact numeric result absent from the extracted text and an unstated
  regularization recommendation/parameter. Code rendered the exact fallback.
- The baseline supplied related formulas rather than acknowledging the absent
  numeric value. For the missing recommendation it acknowledged missing details
  but padded the answer with extra discussion.
- The baseline reversed the low/high-dimensional distance comparison in both
  answerable trials. The XML candidate preserved the central comparison in both,
  but attached some claims to passages that did not support them; one run asserted
  a ratio trend while citing only the code/caption passage.
- No candidate abstained on the one answerable question in either run. This is
  a small sample, not a measured general false-refusal rate.
- Baseline estimated input: 1,395-1,424 tokens. Candidate estimates: 1,001-1,074.
  These are the app's estimates, not exact tokenizer counts. All variants received
  the same three chunks: this experiment does not test larger versus smaller k.
- Candidate missing-answer calls took approximately 0.34-1.57 seconds. These are
  writer-only warm/local timings, not complete app latency or an 8 GB memory test.

Interpretation: the explicit abstention path plus shorter prompt is promising.
Do not attribute the effect solely to the schema: the prompt also changed. XML
and metadata were tested together, not independently. Citation correctness and
unsupported inference remain unresolved. No reranker or manual Llama chat tokens
were added. Do not promote these results as a full RAG fix.

To reproduce, substitute the local document ID and write the report outside Git:

```sh
python3 -m scripts.evaluate_writer \
  --chunks data/documents/YOUR_DOCUMENT_ID/chunks.json \
  --chunk-ids 445 446 447 --title 'Data Science from Scratch' \
  --cases tests/fixtures/writer_distance_cases.json \
  --output /tmp/buddy-writer-comparison.json
```

The report contains source text, raw responses, rendered answers, input estimates,
and timings. Keep it private along with the imported book. The standalone script
does not modify study sessions or call the checker. Its status/citation validation
and XML escaping have offline tests in tests/test_writer_experiment.py.

## 2026-10-13

Tested locally with llama3.2:3b and the nearest-neighbor chapter of the imported
Data Science from Scratch PDF. Test conversations were temporary.

Confirmed mechanical defect: the checker emitted multiple contradictory verdicts
for the same index. Validation then rejected the whole check and retried writing.
The checker now has one required object key per point; duplicate keys, missing
keys, and extra point keys are rejected. Cited passage text is deduplicated.

Experiments that must not be mistaken for a complete fix:

- A simpler checker accepted valid paraphrases but also accepted invented claims
  and a reversed comparison in a full chat test.
- Explicit comparison checks rejected the invented claim and reversal, but also
  rejected valid statements from the same passage.
- A correct route for a source question did not ensure correct interruption:
  after a follow-up, a greeting with a request to pause resumed the old topic.
- Retrieval found relevant content, but the writer could reverse the distance
  relationship and the checker could accept it. More retrieval is not sufficient.

Checking the four controls independently passed where the combined check failed.
The production checker now evaluates one point per call. Drafts are capped at
four points; the existing single repair attempt remains. That permits at most
ten writing/checking calls per answer, without loading a second model. The
latency tradeoff needs to be measured in full chat tests; this is not a guarantee
of semantic accuracy. No keyword-routing override was added. Conversational
routing remains unresolved.

Final verification: 157 offline tests passed; the opt-in four-claim live check
passed with pointwise verification. A full retrieval/writing/checking run took
29.3 seconds and still accepted an unsupported claim that the minimum distance
remained relatively constant. This candidate is NOT validated for production.
The running server was deliberately not restarted with this experimental change.
Do not report the grounding issue fixed based on the passing isolated control.

## Repeatable Live Check

The optional test uses the actual production checker request and schema. Supply
a local chunks.json and the chunk ID for the paragraph contrasting nearest-point
and average distances in low- versus high-dimensional spaces. Keep the book out
of version control. For the tested import this was chunk ID 447.

```sh
BUDDY_LIVE_EVIDENCE=data/documents/YOUR_DOCUMENT_ID/chunks.json \
BUDDY_LIVE_CHUNK_ID=447 \
python3 -m pytest tests/test_grounding_live.py -q
```

The test requires Ollama. It expects rejection of invented regularization advice
and a reversed comparison, and acceptance of an exact statement and a faithful
paraphrase. It is intentionally not marked xfail: a failure is a real model-level
regression/limitation, separate from the default offline unit suite.
