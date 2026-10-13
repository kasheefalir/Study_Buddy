# Span Selection And Oracle Evidence: 2026-10-13

## Decision

Keep experimental. No live app changes or restart. Retain exact span IDs and the
manually reviewed evidence fixture as diagnostic tools, not a production-ready
selector. Preserve the previous explicit-fallback writer prompt/schema rather
than adopting the new simpler writer. Do not interpret code-attached citations
as proof of factual support.

## Protocol

Same imported textbook chunks 445-447, six questions, two repeats, llama3.2:3b.
Main experiment: 36 trials, 64 model calls. Saved-selection replay: 12 trials,
12 additional calls. Total: 76 actual model calls. No retrieval, reranker, new
model, or production conversation state changes.

Text spans retain exact source offsets and original text. The diagnostic splitter
uses punctuation boundaries, not a general-purpose PDF parser; headers, code,
footers and cross-sentence references require inspection. Source hash and ordered
chunk IDs bind the oracle fixture to this exact snapshot. The repository fixture
contains only IDs/hash and review notes, not copyrighted source passages.

Manually reviewed evidence: comparison S3:P2 and P4 (both sides, with exception);
exception S3:P4; noise S3:P3; sampling S1:P2. Neither missing-detail question has
supporting spans. Oracle writer tests for missing facts receive ALL three source
chunks, not an empty input, to avoid making abstention trivial.

Variants:

- Selected bound: model selects up to five span IDs. Code resolves original text,
  groups it by source, calls a simpler writer once per source, attaches its label.
- Oracle bound: same writer, but manually reviewed evidence instead of selection.
- Oracle existing: previous explicit-fallback writer with manually reviewed
  evidence. Here "existing" means the previous experimental candidate, not a
  claim about the version loaded in the running app.
- Selected existing: replay exact model selections through the previous writer,
  avoiding another selector call. This isolates writer behavior on identical input.

First three variants use rotated order; replay follows afterward. Temperature
0.2, no fixed seed. Main maximum input estimate 1,223 tokens, ceiling 2,000.
Differences in prompts, output schema, source grouping, and number of calls mean
this does not isolate citation attachment alone.

## What Worked

- All 12 selection responses resolved to valid, unique original span IDs. No
  quotation-copying failures occurred. Original source text and offsets survive.
- Required evidence was included in six of eight answerable selections: exception,
  noise, and sampling twice each. Comparison missed its low-dimensional side twice.
- Noise, previously blocked by quote matching, produced a useful explanation in
  both selected-bound runs. This is a real gain, not a complete pipeline fix.
- With manually selected evidence, the previous writer correctly expressed both
  comparison sides and retained the structural exception twice. It also answered
  noise and sampling twice, with source S3/S1 citations respectively.
- Previous writer preserved all four missing-answer abstentions with oracle
  context, and all four with replayed model selections. Keep this behavior.

## Failures And Qualifications

| Case | Selected bound | Oracle bound | Oracle existing | Selected existing replay |
| --- | --- | --- | --- | --- |
| Comparison | Incomplete twice; low-dimensional span missing | Both sides, but weakens low-dimensional contrast, overstates "negligible," omits exception | Supported contrast/exception twice; minor formatting defect | Incomplete first; second supplies missing low-dimensional claim absent from provided spans, plus miscitations |
| Exception | First useful; second ambiguously reverses exception | Correct twice | Identifies structure twice but omits explicit lower-dimensional behavior | Useful twice, extra irrelevant material in first |
| Noise | Useful twice | Useful twice | Useful twice | Related high-dimensional statement, not the noise explanation, twice |
| Sampling | Correct S1 facts plus unhelpful "not stated" messages from other sources | Correct twice | Correct twice, repetition | Correct numbers, unjustified S2 citations twice |
| Missing numerical ratio | Correct abstention twice despite false support selection | Acknowledges missing value but returns formula/discussion rather than strict abstention | Correct abstention twice | Correct abstention twice |
| Missing method/parameter | Invented recommendation twice; first includes unsupported L1/L2 speculation | Invented recommendation from a figure heading twice | Correct abstention twice | Correct abstention twice |

The selector approved evidence on ALL four missing-information trials. Valid IDs
therefore establish provenance, not answerability. Many selections fill all five
slots with irrelevant captions/footer text. The original report's oracle_coverage
is vacuously true for empty oracle sets; exclude these from recall calculations.
The updated script/replay uses null for missing-answer coverage.

Code binding removes arbitrary source-label choices, but cannot prevent invented
claims from acquiring those labels. The new writer failed even with all original
chunks supplied for missing facts. Do not ship that writer or use its success
on the noise question to overlook the regression.

This narrows the diagnosis: relevant, focused evidence materially helps the
previous writer in this set. Selection coverage/precision still matters, and
writer prompts remain sensitive. It does not prove retrieval is solved or that
the writer never hallucinates. One chapter and two repeats are not a broad eval.

## Quote Fallback

The harness permits a source quotation after a refusal ONLY for evidence marked
relevant by the manually reviewed oracle. Valid model-selected IDs alone do not
enable this fallback. Unit tests verify both cases. The supported oracle trials
did not refuse, so no live fallback improvement was demonstrated. Unsupported
explanations are not automatically detected or repaired by this mechanism.

## Timing And Verification

Median total trial latency: selected bound 3.44 s; oracle bound 1.22 s; oracle
existing 1.91 s. Replay writer median 2.13 s; adding saved selector timings gives
3.61 s median reconstructed chain latency, not a newly measured end-to-end run.
These include refusals and local warm-cache effects. No 8 GB memory benchmark.

181 tests passed, one opt-in live checker test skipped. Added assertions for
source reconstruction/offsets, unknown/duplicate IDs, status consistency,
code-attached labels, rejection of model-written citation labels, and safe quote
fallback eligibility. No semantic success is inferred from these mechanical tests.

## Reproduce And Preserve

```sh
python3 -m scripts.evaluate_span_selection \
  --chunks data/documents/YOUR_DOCUMENT_ID/chunks.json \
  --chunk-ids 445 446 447 --title 'Data Science from Scratch' \
  --cases tests/fixtures/evidence_chain_cases.json \
  --oracle tests/fixtures/span_oracle.json \
  --output data/study-reviews/span-selection-NEW.json
```

For replay, add `--selected-report data/study-reviews/span-selection-NEW.json`
and choose a different output file. For another import, manually review a new
oracle fixture and source hash; do not bypass the snapshot check.

Saved private reports: `data/study-reviews/span-selection-20261013.json` and
`data/study-reviews/span-selection-replay-20261013.json`. Both are ignored by Git.
They contain original evidence, spans, IDs, all raw requests/schemas/responses,
timings, renderings and failures. Preserve them rather than overwrite.
