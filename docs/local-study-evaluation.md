# Local Study Workflows

Policy update, 2026-10-16: the source-only generation rule evaluated below is
historical. The user now permits accurate elaboration of concepts covered by
the material, clearly distinguished from author content. See
`bounded-tutoring-evaluation.md` for the new isolated policy and attribution tests.
The failures below remain regression cases, not a requirement to reject all
explanations absent verbatim from a source.

## Release Status

Experimental and disabled. Nothing in production dispatch imports
`app.agents.local_study`. GPT/DeepSeek workflows and the existing small-model
workflow are unchanged. Passing unit tests does not authorize release.

Goal: answer questions, generate study guides, and create quizzes from the
student's own materials locally, not provide unrestricted agent reasoning.

## Inspection

The existing application already has persisted chunks and embedding vectors,
hybrid lexical/vector retrieval, resumable hierarchical material overviews,
quiz state, and separate larger-model workflows. The small-model path adds
intent/planning, evidence sufficiency, structured writing, checking and repair.
Those decisions can fail independently of retrieval. Prior experiments showed
that strict exact-quote checking caused excessive abstention. Source aliases
also became invented facts in generated answers.

Existing model switching preloads the chosen model but does not explicitly
unload the previous generator. The normal configured 16K context also needs
memory validation; download size is not runtime memory consumption.

## Isolated Architecture

- QA: constrained request classification, conservative original-wording spans,
  four hybrid-retrieved chunks, source-only writing, semantic support checking.
  Each detected part gets an independent answer or explicit missing result.
- Provenance: the model sees passage text, never opaque document IDs or source
  aliases. Code attaches the actual context sources after generation. These
  are context references, not a claim that each reference proves every sentence.
- Follow-ups: keep the previous question and source references; resolve saved
  references against the currently selected material, not stored passage text.
- Guides: real headings/slide locations, bounded leaf batches, extracted notes,
  semantic checking, deterministic category merge and normalized exact dedup.
  Near-duplicate paraphrases can remain. No full-document generation call.
- Quizzes: one known passage or small related group, four choices, a blind
  verifier that does not see the intended answer, separate explanation check,
  at most two attempts, and code-owned attribution and choice shuffling.
- Runtime: one generation model plus the existing embedding model, 4096 context,
  700 output tokens, temperature 0.1, no extra reranker or database migration.

The candidate requires one explicitly selected material. It is not a general
multi-document reasoning agent. Model checks are fallible; valid JSON, matching
citations, or a positive verifier decision are not proof of factual correctness.

## Phases And Release Gate

1. Preserve live behavior and inspect previous experiments.
2. Implement isolated workflows and deterministic unit tests.
3. Run fixed factual, paraphrase, missing, follow-up, comparison, multipart,
   definition, ambiguity, metadata, guide and quiz cases on both small models.
4. Evaluate retrieval separately from writing with known-evidence controls.
   Inspect answers manually against the fixed rubrics, including qualifications.
5. Measure latency and sampled process memory. Repeat on an actual 8 GB machine
   before claiming that memory target. Repeat factual tests before any promotion.
6. Promote only consistently better behavior, never faster refusals or improved
   formatting alone. Otherwise retain the existing default and record failures.

## Reproduction

Use the project Python environment with its normal dependencies plus `psutil`
for benchmark memory sampling. Both models and the embedding model must already
be installed in local Ollama. No user content is sent to a cloud service.
Do not use the app concurrently: the evaluation unloads other resident models
and aborts generation if another generator becomes resident during a run.

```sh
python3 -m pytest tests/test_local_study.py -q
python3 -m scripts.evaluate_local_study --output data/study-reviews/local-study-run.json
python3 -m scripts.evaluate_local_study_plain --output data/study-reviews/local-study-plain-run.json
```

Use fresh output names. Reports contain private source excerpts and are kept in
the ignored `data/study-reviews` directory. Fixture IDs refer to this user's
local library; other installations need equivalent materials and annotated IDs.

The baseline is the existing grounded writer under the same compact runtime,
not a full end-to-end production benchmark. Budget errors count as errors, not
as factual refusals. Known-evidence tests still exercise the candidate classifier.
The plain-writer ablation bypasses classification and retrieval to isolate writing.

Memory sampling includes evaluator Python, Ollama daemon and `llama-server`
workers, and the Study Buddy uvicorn process. It excludes the browser and other
apps. Sampled aggregate RSS may double-count shared pages; USS is incomplete
when process access is denied. Neither is an exact GPU allocation measurement.
The earlier report without `llama-server` sampling is invalid for RAM comparisons.

## Results

### Fixed QA Cases, 2026-10-15

Ten cases per model/variant: six answerable and four missing/ambiguous. Manual
review against the fixture rubrics, not the model's own support verdict:

| Metric | Llama existing writer | Llama candidate | Phi existing writer | Phi candidate |
| --- | ---: | ---: | ---: | ---: |
| Correct answers / six answerable | 2/6 | 0/6 | 4/6 | 0/6 |
| Inappropriate refusal/clarification / six | 2/6 | 6/6 | 0/6 | 6/6 |
| Runtime budget errors / ten | 2/10 | 0/10 | 2/10 | 0/10 |
| Missing/ambiguous cases without invented answers | 4/4 | 4/4 | 4/4 | 4/4 |
| QA median seconds, all ten cases | 12.03 | 2.40 | 8.81 | 1.61 |

No unsupported factual assertions were found in the completed QA outputs
(0/8 non-error outputs for each baseline, 0/10 for each candidate). This is not
a useful success metric in isolation: the candidate emitted no factual answers.
The ambiguous case often received an abstention rather than a useful clarification.

The candidate's full pipeline provided all annotated evidence in 4/6 Llama
cases and 1/6 Phi cases. These counts include classifier failures that prevented
retrieval; they are not embedding recall alone. Even with known correct passages,
the structured candidate answered 0/6 answerable cases for each model.

Observed failure points:

- Llama's structured writer selected `not_found` even for the explicit fare
  coefficient. Exact-quote requirements were not involved.
- Phi classified ordinary fare questions as comparisons and stopped before
  retrieval because their wording did not match the conservative comparison parser.
- The classifier did not receive the stored prior question; both models asked
  for clarification on the follow-up despite the retained topic.
- Supplying the full comparison request beside an independent focus still led
  Phi to demand an explicit comparison in the source instead of explaining each
  concept separately. Known correct evidence did not resolve this.
- The existing writer's longer repair prompts exceeded the candidate's compact
  input cap in two cases per model. These are not production-runtime failures.

Decision: reject this candidate for live release. Its apparent speed improvement
is not a tutoring improvement. Preserve the existing workflow.

### Guides, Quizzes And Memory

| Measurement | Llama 3.2 3B | Phi-4 Mini |
| --- | ---: | ---: |
| Single-slide summary latency | 6.63 s | 5.36 s |
| Full 22-slide / 23-chunk guide latency | 126.82 s | 160.72 s |
| Guide sections accepted by model checker | 20/22 | 17/22 |
| Quiz requests accepted by checker | 0/2 | 1/2 |
| Accepted quizzes with correct answer key (manual) | 0/2 requested | 0/2 requested |
| Peak sampled aggregate process RSS | 6.32 GiB | 7.76 GiB |

Guide acceptance is NOT factual accuracy. Llama invented formulas and an example
from a title-only slide and filled an exercise blank with a false zero fare; its
checker accepted both. Its single-slide summary omitted other predictors from
an asserted fare equation. Phi rejected the title-only expansion but accepted
some outside explanation of exercise blanks and dropped conditional wording.
Neither guide is approved as reliably source-only. All original chunks were
processed and provenance retained, but provenance does not guarantee support.

Phi's accepted quiz is a release-blocking false positive. The generated question
asked for a drawback of algorithm-based variable selection. The supported option
was a gap between the model and its reasoning logic, but the accepted correct
index pointed at "always interpretable." The blind verifier's number-to-choice
mapping was wrong; a retry changed the intended index to agree with the wrong
verification. Shuffling correctly preserved that already-wrong answer key.
Future tests should ask the verifier for an exact choice value and map it in
code, not allow competing zero-based/one-based index interpretations. Merely
adding another checker would not establish reliability.

The host has 32 GiB RAM, not 8 GiB. USS inspection was incomplete for 4-5
processes and is not reported as the total footprint. RSS includes shared pages
and is not an exact physical/Metal allocation total. The measured peaks are
useful warnings, not portable RAM requirements. Neither candidate is certified
for an 8 GB computer; OS/browser headroom and actual 8 GB testing remain required.

Reports: `data/study-reviews/local-study-20261015-corrected-memory.json`
(68 completed model/workflow case rows). The earlier interrupted report
`local-study-20261015.json` has invalid worker-memory accounting and is excluded.

### Plain-Text Writer Diagnostic

Twenty additional trials used known correct passages and bypassed classification
and retrieval. They removed the structured `status` decision from the writer,
but retained the semantic verifier. This was a diagnostic, not a deployed fix.

| Metric | Llama | Phi |
| --- | ---: | ---: |
| Complete correct answers / six answerable | 2/6 | 3/6 |
| False refusals / six answerable | 3/6 | 3/6 |
| Incomplete answer accepted / six answerable | 1/6 | 0/6 |
| Missing/ambiguous cases without invented facts | 4/4 | 4/4 |
| Median latency, ten cases | 3.28 s | 3.65 s |
| Peak sampled process RSS for this diagnostic | 4.18 GiB | 4.76 GiB |

No unsupported factual assertions were found in the ten final QA outputs per
model, but Llama omitted the Southwest half of a multipart answer and its checker
claimed the question was answered. Phi's comparison checker rejected a useful
comparison. Both models refused the fare paraphrase despite an explicit fare
coefficient. The smaller memory footprint is for these short known-evidence
calls, not full guides, production context, or an 8 GB qualification.

A separate retrieval-only check found required annotated evidence in 5/6 cases
with the original question (using the prior explicit question for the follow-up).
The comparison missed degree centrality. Thus the retrieval, classification,
writing, and checking failures are distinct. A new vector database would not
resolve most failures observed here.

Report: `data/study-reviews/local-study-plain-20261015.json`. Combined total:
88 completed workflow trials, not 88 individual inference calls.

## Recommendation

Keep Llama as the existing provisional low-resource default; keep Phi available
as an alternative. Phi's existing writer did better on this tiny set, but its
larger full-workflow memory observation and the small, single-run sample do not
justify changing the universal 8 GB default. Neither candidate passes release.

Next scoped experiments should carry prior context into classification, avoid
letting a mistaken complexity label block ordinary factual questions, make part
completion explicit, and map verifier choice values in code. Sparse/title-only
slide sections need explicit missing-content handling rather than expansion
from model knowledge. Test each change independently against these failures;
do not stack another generic checker or enable any of them on unit tests alone.

Validation: 280 tests passed, one skipped, including ten isolated workflow/runtime
tests. Production dispatch has no reference to the new candidate package.
