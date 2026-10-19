# Source Routing Recovery

## 2026-10-16: Reported Cloud False Absence

The saved session showed Gemma answering logistic-regression and decision-tree
questions with zero retrieved passages. A direct router probe reproduced a
correct `retrieve` decision wrapped in a Markdown JSON fence. Strict JSON
parsing rejected the wrapper, so the fallback answered without retrieval.
After GPT answered, Gemma could use that answer in history without an
independent source lookup. This is not evidence that GPT taught the cloud model.

## Changes Retained

- Accept JSON fences through the existing lossless structured-output parser;
  retain field validation, route enums, and selected-material constraints.
- Accept equivalent string citation IDs as label objects; reject unknown IDs.
- Show the output schema in writer and checker instructions as well as the API
  schema argument. Exclude repeated writer/checker schemas for GPT-OSS: testing
  elicited schema echoes and malformed JSON there. Its prior schema-prompt
  style and API schema remain in use.
- Keep initial retrieved passages if the optional expansion check has invalid
  output. The answer writer and source-support checker still run.
- Truncate checker diagnostic reasons to 300 characters without changing true
  or false verdicts. Previously verbose reasons discarded supported answers.
- Correct accidentally disconnected retrieval instruction strings.
- Tell no-retrieval responses not to claim they searched the material; persist
  routing diagnostics for subsequent debugging.
- Align GPT's context packing with its actual 4,096-token output reservation.
- Keep search queries about the requested concept rather than repeating source
  titles already represented by document filters.

## Evidence And Repeatability

`scripts/evaluate_source_routing_recovery.py` runs each question in a fresh,
temporary conversation. It does not reuse GPT's answers or edit user sessions.
The material is the user's Data Science from Scratch book.

Final Gemma runs (`routing-recovery-gemma-diagnostics.json` and its `-repeat`
report under `data/evaluations/`) answered logistic regression and decision
trees in both runs: 4/4 answerable probes. Both missing-information controls
(the user's laptop RAM) abstained. Answerable turns took 8.29, 8.82, 8.71,
and 16.84 seconds; these are observations, not controlled speed benchmarks.

Manual passage inspection confirmed the logistic function, 93% precision,
82% recall, decision boundary, tree definition, tree types, interpretability,
and overfitting discussion. Book index page numbers differ from PDF page
locations; the distinction should be clearer in the UI. Duplicate inline
citation formatting also remains a presentation issue.

Intermediate results are retained, not counted as final successes: accepting
fences alone exposed writer-shape errors; repeating the initial successful
Gemma build exposed the diagnostic-length failure. Increasing prompt emphasis
alone did not resolve those failures. The same diagnostic-length failure also
appeared in GPT's intermediate run.

The final GPT report (`routing-recovery-gpt-preserved.json`) answered both
topics with citations and declined the laptop-RAM control. Observed latencies
were 68.96, 101.23, and 22.03 seconds. This is one final run, not a consistency
benchmark. Earlier GPT runs overlapped and their latency is not comparable.
GPT's logistic explanation included a mathematical expression inside a Python
code fence that is not executable Python; code-output correctness remains a
limitation even when conceptual source support passes. Do not present these
results as perfect responses or as proof of all-model parity.

371 automated tests passed, one skipped. The small models have regression-test
coverage here but were not rerun on these live book probes. This narrow test
set does not establish general factual accuracy or eliminate self-checker
errors. No checker bypass or automatic acceptance of unsupported claims was
introduced. Sequential per-point checks remain a latency bottleneck; evaluate
batching separately before promotion.

## Pipeline Capacity Follow-Up

The six pressure points were checked against the current implementation:

1. Compact evidence status and source metadata already reach writer and repair.
2. GPT context packing already uses the client's 4,096-token reply reserve.
3. New expanded packing reserves recent dialogue, then gives spare capacity to
   evidence. Round-robin document/section ordering reduces first-document bias.
   It is not a semantic guarantee that every subquestion has supporting evidence.
   Llama and Phi retain their previous compact budget and ordering: a live Llama
   trial did not establish a benefit from expanded evidence.
4. Each standard/GPT model call now records client wall time and available
   Ollama generation, prompt-processing, load, and total durations by stage.
   Missing provider timings remain absent, not zero. Existing verified-evidence
   reuse already skips retrieval and has regression coverage; no support checks
   were removed. Failed transport calls do not yet have these success records.
5. Standard-client output truncation detection was already implemented.
6. Overview merges now receive complete child summaries, all child concepts,
   and headings, instead of another 750-character/three-concept cut. Existing
   caches are not automatically rebuilt. Output caps remain bounded; final
   summary fidelity still needs a live reference-outline evaluation.

### Measurements

- At 4,096 context / 512 output, the fixed two-document packing fixture improved
  from one passage from A to five passages covering A and B. Estimated input
  remained 2,666 tokens against a 3,072-token allowance. This measures evidence
  availability, not answer accuracy.
- Gemma answered both original book topics and declined the missing laptop-RAM
  control in `pipeline-capacity-gemma.json`. Times were 7.32, 10.43, and 7.49
  seconds. Source support checks used 2.12 and 2.31 seconds; writers used 1.28
  and 3.69 seconds. No controlled speedup claim is made.
- Llama's expanded-capacity trial abstained on both answerable topics and the
  missing-information control (`pipeline-capacity-llama.json`). Do not promote
  expanded packing for small models based on these results. No new Phi live
  benchmark was run; its allocation stays unchanged.
- GPT's `pipeline-capacity-gpt.json` answered logistic regression with a source
  citation (56.34 seconds) and declined the laptop-RAM control (22.61 seconds).
  This is a focused regression probe, not a claim of increased factual accuracy
  or a controlled speed comparison. Its final response is narrower than some
  earlier runs. Decision trees were not rerun for GPT in this follow-up.
- The merge regression asserts that a qualification beyond character 750 and
  concepts four and five actually reach every parent prompt. It does not assert
  that a model necessarily retains those facts in its generated summary.

374 tests passed, one skipped. Next: evaluate summary fidelity against a
chapter outline and compare batched support checking against the saved
per-point baseline. Neither is claimed complete in this follow-up.

## Fixed-Evidence Checker and Summary Trials

Reports are saved locally under `data/evaluations/summary-verification-*.json`,
`summary-qualified-gemma.json`, and `gemma-batch-live.json`. The evaluator is
`scripts/evaluate_summary_verification.py`. It uses frozen passages from the
local `routing-recovery-gemma-diagnostics-repeat.json` report; that input report
is required to reproduce these runs. No conversation or overview cache is edited.

### Promoted: Small Gemma Verification Batches

Gemma's single and batch conditions each returned 32/32 correct verdicts across
16 unique claims, each repeated twice, including a separate holdout set.
Cases include reversed percentages, wrong citations, unsupported guarantees,
and supported definitions. Neither condition had false acceptances, false
rejections, or malformed output. Four-claim checks took 0.64-0.79 seconds
batched versus 1.54-1.97 seconds individually in these trials.

Only `gemma4:31b-cloud` now batches two to four points. Invalid/incomplete JSON
falls back to individual checking; a valid rejection remains a rejection.
Oversized batches also use the original path. Transport errors are not blindly
retried. GPT and small-model production checks are unchanged.

Fresh-chat end-to-end Gemma probes answered logistic regression and decision
trees with sources and abstained on the unsupported laptop-RAM question.
Elapsed times were 6.62, 6.78, and 5.33 seconds. These are regression probes,
not controlled whole-pipeline speed benchmarks or proof of universal accuracy.

### Not Promoted: Summary Prompt Experiment

The reference outline covers logistic behavior, precision, recall, categorical
classification outputs, numeric regression-tree outputs, overfitting,
generalization risk, and computational difficulty of optimal trees. Manual
review additionally checks that computational workarounds are not presented
as cures for overfitting, and that risks do not become guarantees.

Gemma's legacy/preserved merges mentioned all eight screened topics, but some
blurred computational difficulty and overfitting and said strategies "ensure
generalization." A qualification-preserving prompt avoided that wording in
two repeats and retained the categorical/numeric distinction. This is promising,
not sufficient to enable globally. GPT's initial merges omitted some tree-type
detail; preserving children alone did not consistently recover it.

This is a four-excerpt merge probe, not a complete-book or chapter evaluation.
Production merges have fan-in three. All Gemma child summaries were under 750
characters, so this trial did not exercise the old character cut; it tested
concept retention and headings. Lexical coverage is only a screen, not a factual
accuracy score. Existing full-child preservation remains in place, but the new
qualification prompt remains experimental. Next fidelity test needs additional
chapters, longer children, and a manually adjudicated reference outline.

### GPT Holdout and Remaining Promotion Gate

GPT also achieved 32/32 correct verdicts per condition over the same 16 unique
claims repeated twice, with no format failures or false acceptances/rejections.
Initial four-claim batches took 8.74-16.56 seconds versus 16.45-26.03 seconds
individually. Holdout batches took 8.12-13.76 seconds versus 15.19-21.92 seconds.
The batch candidate is promising for GPT, but remains isolated until a GPT
end-to-end writer/repair regression run verifies the integration. Its production
checker remains unchanged; smaller-model checks also remain unchanged.

Verification after the Gemma promotion: 380 tests passed, one skipped;
`git diff --check` passed. The app was restarted and returned HTTP 200.

## GPT Batch Integration Completed

The GPT promotion gate above is now satisfied for the tested cases. GPT uses
the same two-to-four-point batch path as Gemma, while retaining GPT's API schema
without repeating schema text in its prompt. Single points stay on the original
path. Oversized or malformed batches fall back to individual checking; valid
rejections still drive the existing bounded repair flow.

Fresh conversations in `data/evaluations/gpt-batch-integration.json`:

- Logistic regression: sourced answer, 37.81 seconds. One answer point meant
  the unchanged individual checker ran (5.56 seconds).
- Decision trees: three sourced points, 57.12 seconds. Trace confirms one
  `source support batch` call covering all three points (15.68 seconds), with
  all three verdict slots present. Manual passage review supports the definitions,
  category distinction, splitting explanation, and overfitting qualifications.
- Missing laptop RAM: abstained, 17.57 seconds, without claiming the book had
  established the requested hardware information.

These variable-length answers are not a controlled speed comparison. The
fixed-evidence experiments above establish the measured checker speed advantage.
No live model-generated answer in this run needed repair. Deterministic full
writer/checker/repair tests separately verify mixed acceptance/rejection,
successful and unsuccessful repair, no accepted-point duplication, malformed
batch fallback, budget fallback, and unchanged Llama/Phi per-point behavior.

387 tests passed, one skipped; `git diff --check` passed. Summary prompting is
still experimental and is not part of this promotion.

## Source-Linked Outline Trial

Implemented `app/rag/outline.py`: contiguous extracted sections, stable IDs for
the current extraction, original chunk IDs and locations, full-heading search,
bounded navigation cards, and explicit omitted-section counts. This is computed
from current chunks, not generated by an LLM or persisted in a stale cache.
Repeated headings in different locations remain distinct. Heading matches are
navigation hints, never factual support or proof of absence. This does not add
semantic synonym search or infer missing chapter boundaries.

GPT/Gemma planner cards now search all extracted headings for the question,
instead of always showing only the first eight headings. Original passages
still supply answer evidence. Llama/Phi retain their previous cards because the
paired probes exposed regressions. Unit tests lock down this model boundary.

`scripts/evaluate_source_outline.py` tested four calls per model: baseline and
candidate navigation, then baseline and candidate summary. Reports are
`data/evaluations/outline-{llama,phi,gpt,gemma}.json`. All used the same book and
existing cached summaries, not independently generated ingestion per model.
One run per condition is a pilot, not a statistical accuracy estimate. Baseline
always ran first, so timing differences are confounded by warmup and ordering.

| Model | Navigation candidate | Summary candidate |
| --- | --- | --- |
| Llama 3.2 3B | Changed focused search to broad review | More specific topics, but repetitive and includes incidental author material |
| Phi-4 Mini | Returned empty document IDs | Includes incidental author/back-matter content; no reliable improvement |
| GPT-OSS 20B | Correct focused search and document retained | Added details not established by supplied notes, including eigenvalues and probability integral transform |
| Gemma 4 cloud | Correct focused search and document retained | Explicitly disclosed limited section details, but narrower topical coverage |

The existing summary frontier supplied six hierarchical nodes; the candidate
kept the book root plus four evenly spaced section notes under the same 2,400
token data budget. Total prompt estimates were 2,433 and 2,485 tokens including
instructions. Both used the same 350-word instruction. The candidate sampled
back matter and did not preserve sufficient topic breadth. It remains OFF for
all live models (`outline_details=False`); no summaries or ingestion caches were
rewritten. It is not a demonstrated summary improvement.

Manual assessment distinguishes detail supported by supplied notes from facts
that might occur elsewhere in the book. The isolated summary probes intentionally
omit downstream verification to expose writer behavior; they are not end-to-end
factual accuracy scores. The navigation baseline already succeeded for both
large models, so no navigation accuracy gain is claimed. The enabled change
removes the deterministic first-eight-heading blind spot without a demonstrated
regression in those probes.

Gemma full-pipeline checks with the new card answered logistic regression with
sources (5.61 seconds) and abstained on unsupported laptop RAM (5.32 seconds),
saved in `outline-gemma-integration.json`.

GPT full-pipeline logistic regression also passed with two sourced points
(40.58 seconds), saved in `outline-gpt-integration.json`. This is not a measured
speed improvement over prior runs. 392 automated tests passed, one skipped.

Next summary work: preserve source-linked concept/qualification records and
distinguish instructional sections from back matter before selecting detail.
Do not replace the whole-book hierarchy with a handful of sampled sections.

## Quiz Retry Recovery (October 17)

Reproduced the reported logistic-regression quiz failure on disposable copies of
the existing session. The user's original conversation was not modified.
The Retry button already uses the newly selected model. Added a JavaScript
regression covering model changes, duplicate-message prevention, and session guards.

Two backend problems were observed: schema/commentary output aborted question
generation without using its bounded repair loop, and incidental topic mentions
or unrelated concept projections supplied inadequate evidence. Generation now
retries malformed structured drafts within its existing three-attempt limit.
Explicit matching chapter boundaries narrow quiz windows; concept projection
requires actual source overlap. Reference-only sections are excluded. A failed
valid draft can trigger one scoped evidence recovery read, still followed by
normal answer-choice validation. Exhaustion reports the question number and
states that quiz progress was not saved.

Reports in `data/evaluations/` preserve failures as well as successes:

- `quiz-retry-before.json`: cloud schema echo reproduced the generic failure.
- `quiz-retry-after.json`: format repair alone did not fix cloud evidence failures.
- `quiz-retry-scoped.json`: GPT returned question 1 of 10 in 23.98 seconds;
  cloud still failed on inadequate evidence.
- `quiz-retry-final-gemma.json`: removing reference-only windows alone was insufficient.
- `quiz-retry-recovery-gemma.json`: cloud prepared all 10 questions and returned
  question 1 in 24.48 seconds with bounded evidence recovery.
- `quiz-retry-small.json`: both small models failed before evidence recovery was added.
- `quiz-retry-recovery-small.json`: with the final recovery change, Llama failed
  at question 10 of 10 (92.26 seconds) and Phi failed at question 7 of 10
  (91.61 seconds). Neither partial bank was saved. Full ten-question preparation
  remains unreliable for these models; these fixes do not establish otherwise.

These are live integration probes, not a broad factual-accuracy benchmark or a
controlled latency comparison. Randomized window order and warmup affect timing.
Passing the existing model checker does not independently establish factual accuracy.
Automated verification: 401 Python tests passed, one skipped; Retry JavaScript
regression passed.
The app was restarted and returned HTTP 200 on port 8001. No original conversation
or uploaded material was changed by the replay tests.

## Ended Quiz Clarification (October 17)

The reported GPT plain-text question was not produced by the quiz generator.
The saved routing record correctly selected clarification after the student ended
the quiz, but the free-form writer invented question 3 anyway. Lifecycle responses
now bypass the answer writer: ending acknowledges saved progress; clarification
for a closed quiz asks whether to resume or start anew. The model still interprets
intent, including misspellings; code executes its lifecycle decision.

Ended quizzes hide current controls and reject stale Next events. Explicit resume
restores the saved structured choices, including when the question ID is unchanged.
Question numbering and choices are included in resumed pending-question text.
Regression coverage includes end, ambiguous next, stale Next, and resume without
advancing the cursor or exposing the answer key.

A live GPT-OSS probe on a temporary session copy returned the end acknowledgement,
clarified "next queestion", and restored the saved answered question on explicit
resume. The user's conversation was not changed. This fixes lifecycle/formatting,
not the separate factual-quality and quiz-topic-selection limitations.

## Final-Answer Feedback Recovery (October 19)

The R quiz had nine saved answers and an ungraded tenth question. Malformed
ChoiceFeedback aborted scoring. Live replay also exposed a punctuation guard
rejecting the literal R `?` operator as a new quiz question. The guard now ignores
code spans and help-operator notation while still rejecting ordinary questions.
Structured feedback gets two bounded attempts. Exhaustion returns only the saved
answer key and an explicit explanation-unavailable notice, allowing deterministic
choice grading and completion to persist. This does not verify the answer key's
factual accuracy. Free-text assessment is unchanged; transport errors still propagate.

Tests cover malformed-output repair, final correct/incorrect submissions, no
duplicate scoring, and literal help operators. 409 tests passed, one skipped.
Live GPT replay on a disposable copy first exercised fallback completion, then
the corrected guard allowed normal explanatory feedback and ten recorded answers.
The original session was not modified.

For the Phi overview screenshot, the extracted Logistic Regression PowerPoint's
slide 20 itself contains the absolute-deviations claim; slide 19 describes squared
weights and absolute weights. Source fidelity does not establish correctness of
the source. The screenshot's narrow partial overview remains a separate limitation;
no summary improvement is claimed or enabled by this patch.
