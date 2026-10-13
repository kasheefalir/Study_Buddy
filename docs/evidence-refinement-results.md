# Evidence Refinement Tests: 2026-10-13

## Decision

Do not promote to the live app. Keep the standalone harness, literal citation
assertions, raw reports, and repeatable cases. No server restart, retrieval change,
keyword intent router, extra model, or reranker was introduced.

## Protocol

Real llama3.2:3b; same six textbook questions, twice each. Main run: 48 variant
trials, 86 calls. Follow-up ID/page mapping: 12 trials, 24 calls. Total: 110 calls.
Results manually inspected against source text, not scored by another model.

- Baseline: previous verified-selection -> selected-chunk synthesis chain.
- Dual rewrite: one model call produces literal and conceptual questions; both
  selection passes run. Valid evidence from either is retained. Original question
  remains visible and is always used for synthesis. No retrieval is rerun here.
- Neighbors: immediate preceding/following chunks from the same document/chapter,
  deduplicated, in document order. Existing source labels retained. Chunks 445-447
  expand to 444-448. These are page-sized chunks, not newly segmented paragraphs.
- Mapping: model lists concepts, source IDs, PDF page indices, excerpts, and a
  difference before synthesis. Metadata and copied excerpts checked by code.
- Mapping IDs: follow-up removes the extra excerpt-copying requirement. Model
  maps concepts to IDs/pages and describes the difference before synthesis.
  Code verifies ID/page consistency, not the semantic correctness of that map.

The first four variants use rotated order. Mapping IDs was tested afterward,
not interleaved. Temperature remains 0.2; no fixed seed. Input estimate ceiling
is 3,000 tokens, no silent truncation; actual maximum was 1,334 in the main run
and 1,036 in the follow-up. Source text, prompts, schemas, errors, labels, hashes,
outputs, and timings are saved in private reports.

## Results Ledger

Each entry summarizes two trials. "Correct" includes supported factual content
and appropriate source attribution, not just passing schema validation.

| Case | Baseline chain | Dual rewrite | Neighbors | Mapping with quotes | Mapping IDs |
| --- | --- | --- | --- | --- | --- |
| Low/high comparison | Wrong S2 citation twice; unsupported additions | False refusal twice | False refusal twice | Quote validation fails twice | False refusal once; incomplete comparison once |
| Structured-data exception | One quote rejection; one correct | One false refusal; one correct | False refusal twice | One quote rejection; one answer reverses exception despite quoting it | Correct twice |
| Extra noisy dimension | Quote rejection twice | False refusal twice | False refusal twice | Quote rejection twice | Quote rejection twice |
| Sampling count/dimensions | Correct twice | Correct numbers, but unjustified S2 citations twice | False refusal twice | Additional mapping quote check rejects twice | Correct twice |
| Missing numerical ratio | Correct abstention twice | Correct abstention twice | Correct abstention twice | Correct abstention twice | Correct abstention twice |
| Missing method/parameter | Correct abstention twice | Correct abstention twice | Correct abstention twice | Correct abstention twice | Correct abstention twice |

Preserve: all five paths correctly abstained on all four missing-information
trials each. Mapping IDs preserved four successful narrow answers but did not
fix noise or the comparison. The baseline exception succeeded only once here,
versus twice in the prior experiment: repeated success is not a guarantee.

Do not call refusal-only behavior an improvement: neighbors refused every
answerable question. Adding context did not cause a token-budget error; the
model explicitly declared the answer absent. The answer was already available
in S3 before expansion. This is not evidence of a retrieval cosine threshold bug.

The mapping with extra quotes was a stricter implementation than the proposed
ID/page list. It introduced another copy-validation failure point. Retaining
that result and separately testing the simpler mapping avoids attributing these
failures solely to page mapping. Its comparison maps remained vague even when
the source/page values were valid. Neither map format is semantic verification.

## Citation Assertions

The literal diagnostic caught both baseline low-dimensional claims citing S2
instead of S3. It checks configured entity strings in rendered points against
each cited source, flags unknown labels, and records failures without aborting
the remaining experiment. Unit assertions reproduce wrong and correct citations.

Limits: the comparison fixture currently names `low-dimensional`; this is not
automatic entity extraction. Synonyms can be missed or falsely rejected. Multi-
source points can be overflagged. Reversing a claim while retaining its entity
passes the string test; a unit test explicitly demonstrates that limitation.
Sampling-count miscitations and incomplete comparisons needed manual review.
`development_check_passed` in the first report means only this literal check
passed, not answer correctness; newer reports call it `citation_check_passed`.

## Timing And Verification

Median total per trial, including refusals: baseline 4.46 s; dual rewrite 4.46 s;
neighbors 1.56 s; quote mapping 4.52 s; ID mapping 6.10 s. ID-mapping trials that
reached synthesis had median total latency 9.67 s. Fast refusals must not be
compared with useful answers as a speed win. These are local timings, not an
8 GB memory benchmark or complete app latency.

Offline suite: 173 passed, one opt-in live checker test skipped. Git diff
whitespace check passed. Tests cover citation mismatches, the semantic blind
spot, neighbor boundaries/deduplication, preserved labels, and mapping IDs/pages.

## Reproduce

```sh
python3 -m scripts.evaluate_evidence_refinements \
  --chunks data/documents/YOUR_DOCUMENT_ID/chunks.json \
  --chunk-ids 445 446 447 --title 'Data Science from Scratch' \
  --cases tests/fixtures/evidence_chain_cases.json \
  --variants baseline dual_rewrite neighbors mapping \
  --output data/study-reviews/evidence-refinements-20261013.json
```

Run again with `--variants mapping_ids` and a separate output path for the
follow-up. Saved report: `data/study-reviews/evidence-mapping-ids-20261013.json`.
Both reports are ignored by Git because they contain imported textbook text.
Do not overwrite them when adding another experiment; use a new report name.

Next unresolved test remains selecting preassigned sentence/span IDs instead of
copying text, while preserving original source context. Do not add it to the
live app without rerunning these cases and checking answer coverage, factual
support, citations, missing-answer handling, and latency separately.
