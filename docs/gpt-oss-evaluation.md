# GPT-OSS baseline evaluation

Date: 2026-10-13. Installed model `gpt-oss:20b`, digest prefix
`17052f91a42e`, MXFP4. DeepSeek speed experiments are parked, not deleted.

Tested the existing app API/ChatAgent workflow with real local Ollama and the
user's Data Science from Scratch PDF. Temporary conversation storage protected
existing chats. This is a baseline, not a new GPT-OSS-specific architecture.
No live workflow, model preference, or model inference policy was changed.
Settings: low reasoning, 16,384 context, 1,200 output-token limit per call.

| Probe | Seconds | Observed result |
| --- | ---: | --- |
| Greeting | 20.42 | Natural greeting, no retrieval. Includes initial loading. |
| Betweenness centrality | 52.60 | Retrieved six passages and answered with S3, which supports the definition and example. |
| Explain more simply | 15.57 | Failed grounding route: ordinary chat, no attached sources or support check. |
| Author's exact laptop/RAM | 58.79 | Retrieved sources and declined to invent details absent from those passages. |
| Prepare two-question quiz | 178.59 | Prepared two different questions with choices; three generation/quality-check pairs indicate an extra attempt. |
| Deliberately wrong answer | 48.20 | Correctly recorded incorrect and explained the saved correct choice. |
| Next question | 33.73 | Advanced to the second prepared question, zero model calls. Significant non-generation latency remains. |
| Deliberately correct answer | 41.89 | Correctly recorded correct and completed the quiz at 1/2. |
| Missed-answer review | 3.76 | Included only question 1, preserving the correct result for question 2. |

All nine API turns returned 200; this alone is not an accuracy pass. The
follow-up bypassed grounding despite preserving the general topic. Its city-map
analogy and looser counting explanation were not checked against source text.
The missing-fact response correctly limits its claim to supplied passages; this
does not prove the entire book contains no such information.

Compared with the earlier DeepSeek narrow-fact run (519.71 seconds), GPT-OSS was
about ten times faster on that question. Different workflows and single runs
make this an observational comparison, not a controlled model benchmark.

Ollama reported 12,748,870,122 bytes allocated to GPT-OSS at 16K context, all in
GPU memory, plus approximately 370 MB for the embedding model. This is not total
system peak RAM, but it clearly does not establish suitability for an 8GB device.

## Next priorities

1. Preserve source-grounded routing for explanatory follow-ups using model-owned
   intent and recent evidence; do not patch this with greeting keyword rules.
2. Profile the 34-second prepared-question advance before adding model changes.
3. Establish comparison and pause/resume baselines before promoting a separate
   GPT-OSS architecture. Those behaviors were not tested in this run.
4. Inspect per-call truncation/finish diagnostics before changing output budgets.
   The existing shared client does not expose finish reasons in these reports.

Reproduce with `python3 -m scripts.evaluate_model_workflow --model gpt-oss:20b
--document-id 3a4c66034f8a4b6cba7320b89e254ff5
--output data/study-reviews/gpt-oss-baseline.json` (one command).
The private report is ignored by Git and contains sources, usage, and quiz state.

## GPT-specific sequential trial, 2026-10-14

Added `app/agents/gpt/` with its own router, retrieval, tutor instructions, client,
and agent policy. Dispatch is specific to GPT-OSS; Llama/Phi retain eager question
preparation and DeepSeek is unchanged. GPT uses the shared transactional quiz
engine with `prepare_all=False`. Background prefetch is deferred: this trial
generates the next question on demand, not in a background worker.

The first sequential attempt with the shared 1,200-token client failed quiz
creation with HTTP 400 after 90.11 seconds. Its final finish reason was not
recorded, so truncation is suspected, not proven. Added GPT-only 4,096-token
headroom, low reasoning, input-budget checking, and rejection of truncated or
empty completions. The retry completed with normal stop reasons.

| Retry probe | Seconds | Result |
| --- | ---: | --- |
| First question | 84.68 | One generated question, no prepared question bank. |
| Pause | 7.42 | Preserved question ID, marked paused. |
| Resume | 5.01 | Same question ID, unpaused, no advancement. |
| Wrong answer | 44.74 | Correct saved grade; generated example has an accuracy defect. |
| Next question | 51.37 | Generated/validated a distinct second question. |
| Correct answer | 41.82 | Completed at 1/2, as expected. |
| Missed review | 6.87 | Only the wrong question, but repeats the flawed explanation. |

First-question latency improved versus the earlier 178.59-second upfront run,
but these single runs have different questions/retries. Next now incurs model
generation and quality checking. Significant non-model topic-window computation
remains before quiz calls. This is not a complete performance profile.

Quality failures remain: the shorter router again treated a simplification
follow-up as conversation (12.51 seconds, zero sources). The wrong-answer example
claimed a larger probability beyond three standard deviations after increasing
sigma; standardized three-sigma tail probability does not change. Do not call
this a clean tutoring-accuracy pass or remove grounding checks. The quiz feedback
path does not run the source-grounded answer verifier used for ordinary RAG.

Private reports: `gpt-sequential.json` and `gpt-sequential-headroom.json` under
`data/study-reviews/`. The latter verifies a two-question flow only, not several
complete quizzes across materials. No existing user conversations were changed.
Regression suite: 241 passed, one skipped. Tests cover model dispatch, one-question
generation, persisted-state rollback, and GPT-only budget/truncation handling.

## Isolated native retrieval tools, 2026-10-14

`python3 -m scripts.evaluate_gpt_tools` tests a native Ollama tool loop on
Data Science from Scratch without changing live dispatch or saved conversations.
Full assistant messages are preserved between tool calls, including thinking.
Code owns search execution, selected-material scope, source IDs, and call limits.
Private checkpoint: `data/study-reviews/gpt-native-tools.json`.

| Probe | Seconds | Calls | Observed result |
| --- | ---: | ---: | --- |
| Greeting | 1.89 | 1 | Natural response; no search. |
| Betweenness definition | 9.23 | 2 | Searched; cited S1/S2 support the definition. |
| Simplify follow-up | 7.99 | 1 | Reused evidence, but added an invented analogy and omitted citations. |
| Degree/betweenness comparison | 13.94 | 2 | Searched degree, but retrieved betweenness passages; answered degree definition without supporting evidence. |
| Missing laptop/RAM detail | 12.98 | 2 | Searched and abstained rather than inventing specifications. |

All returned citation IDs existed, but this is not an entailment check: S1
discusses dissatisfaction with degree centrality without defining it. The
comparison therefore fails strict grounding despite valid IDs. The follow-up
also fails the requested source-only contract. The missing-detail answer should
ideally say the retrieved evidence did not establish it, not imply exhaustive
inspection of the entire book.

These single-run timings are promising, not an apples-to-apples benchmark:
the experiment has no downstream grounding checker and does not test quiz tools.
Do not promote it yet. Next isolate retrieval recall for degree centrality,
then test claim-level support and follow-up citations without reintroducing
competing intent routers. Keep the successful social routing and abstention
cases as regression probes. Native transcript preservation, scope enforcement,
unknown citations, and truncated responses have deterministic unit coverage.

## Neighbor reservation and separate retrieval trials, 2026-10-14

Implemented shared primary-hit reservation before neighbor expansion. Existing
overview selection and section boundaries remain unchanged. On three queries,
the previous policy retained 2/3 primary hits; the new policy retained 3/3.
Definition coverage did not change (2/3 probes); preserving hits cannot repair
ranking. `scripts/evaluate_neighbor_selection.py` compares both policies on
identical hits. Private report: `neighbor-selection.json`.

The degree query exposed a fusion failure: existing lexical ranking puts the
definition (chunk 86) first, but fused top three are 684, 674, 694. This is not
evidence that the definition is missing from ingestion or embeddings.

Separately tested SQLite FTS5/BM25 in memory, without migrating data. On these
three narrowly related probes, BM25 definition coverage was 2/3; existing lexical
ranking was 3/3. BM25 also ranked index entries above the degree definition.
No evidence here supports replacing existing retrieval with bare BM25.
`scripts/evaluate_bm25.py`; private report `sqlite-bm25.json`. Reported timings
include temporary index construction and lexical comparison, not just search.

Two native GPT follow-up trials (five turns each):

| Trial | Greeting | Fact | Follow-up | Comparison | Missing detail |
| --- | ---: | ---: | ---: | ---: | ---: |
| Reserved neighbors + evidence instructions | 2.20s | 10.58s | 8.72s | 14.01s | 12.40s |
| Above + lexical top-hit rescue, context quota 6 | 1.10s | 9.64s | 9.22s | 19.10s | 17.07s |

First trial restored follow-up citations but comparison still lacked degree
evidence. Second recovered chunk 86 and cited it in the comparison, but invented
an analogy in the follow-up, used paraphrases as quotations, and added unsupported
"control of information flow" interpretation. Both abstained on laptop details
but overstated absence from the entire book. Missing-detail output in the first
trial used a citation range that the existing simple citation regex does not
validate. Neither trial qualifies as a strict grounding pass.

Private reports: `gpt-native-evidence-policy.json` and
`gpt-native-lexical-rescue.json`. Reproduce via `scripts.evaluate_gpt_tools` with
`--evidence-policy`, optionally `--lexical-rescue`, and distinct `--output` paths.
The rescue trial changes both evidence selection and context quota; this is a
candidate workflow test, not an isolated estimate of either factor's benefit.

Only the shared neighbor fix is activated in the app. Native GPT experiments
remain isolated; no SQLite migration, re-embedding, or user-chat changes.
Next test preserving independent lexical/semantic candidates on broader held-out
queries and validate claim support/quote exactness before promoting GPT changes.
Regression suite: 247 passed, one skipped.

## Broader paired evidence audit: rejected, 2026-10-14

Completed 24 evaluation turns: 12 baseline and 12 candidate, spanning Data
Science from Scratch, Introduction to R, and Logistic Regression 2 slides.
Eight questions are answerable, three ask for missing details, and one is a
greeting. Centrality and its follow-up retain conversation state; other cases
start fresh. The first five are regression probes, seven expand coverage across
the other materials. These are single runs, not repeated statistical estimates.

Baseline is the previous isolated native-tool experiment with evidence policy
and lexical rescue, NOT the live app. Candidate uses independent top-two lexical
and semantic hits, neighbor expansion to six chunks, a structured claim audit,
literal quote/source validation, and at most one repair. Multiple variables
change together; this measures the candidate workflow, not isolated attribution.
Both use local GPT-OSS 20B, low reasoning, 4096 output headroom, 16384 context.

| Measurement | Baseline | Candidate |
| --- | ---: | ---: |
| Evaluation turns | 12 | 12 |
| Median end-to-end latency | 10.96s | 55.49s |
| Total recorded latency | 156.99s | 726.16s |
| Forced refusals on answerable cases | Not applicable (no audit gate) | 8/8 |
| Missing-detail cases | All declined requested facts, with grounding/wording defects | 3/3 forced generic refusals |
| Greeting | Natural response | Natural response |

The baseline is not an accuracy-clean winner: its follow-up changes the
betweenness calculation to a global ratio, its comparison adds unsupported
influence/control claims, and its RStudio-version refusal fabricates quotations.
Several citations use grouped, prose, or non-ASCII bracket formats. The literal
validator does not detect every such format, so zero literal flags is NOT an
accuracy or citation-format pass.

Candidate failures are unequivocal:

- Even the correct Ctrl+Enter/Run answer was blocked: first because the auditor
  altered excerpts, then because it selected S2 while the answer cited S1.
- Correct fare values were rejected for auditor copying errors. Repair then
  treated the audit error as proof that the original evidence was invalid.
- The missing-seed auditor demanded explicit source proof of absence. This
  defeats appropriate abstention rather than verifying a factual answer.
- Broad comparison queries retrieved index entries. Independent top-two ranking
  is not enough: the degree definition fell below those entries. The candidate
  lacked chunk 86 while the baseline ultimately retrieved both definitions.
- Quote checks also flag stylistic quoted terms. They establish literal matching,
  not intent to quote or semantic support; this can produce false alarms.

The candidate's valid source-ID checks caught mistakes but did not repair the
model's evidence judgment. Forced abstention is not counted as success on an
answerable case. Preserving missing-answer behavior by refusing everything is
not an acceptable tradeoff. No candidate changes are promoted to live dispatch.
The earlier shared neighbor-reservation fix remains active and unchanged.

### Preserve and avoid repeating

- Retain per-search lexical/semantic rankings and explicit fallback status as
  diagnostic improvements, and retain deterministic quote checks as test signals.
- Reject copied auditor excerpts as a mandatory production gate. The earlier
  `span-selection-results.md` already showed ID resolution avoids copy errors;
  this GPT trial confirms that copy verification can still reject useful answers.
- Next experiment should reuse code-resolved span IDs, distinguish auditor
  formatting errors from unsupported writer claims, and avoid turning malformed
  audits into instructions that the material is invalid.
- Require separate concept searches or definition-oriented evidence selection
  for comparisons; never treat index mentions as definitions. Test independently
  before combining with another audit chain.
- Keep the exact R shortcut, fare values, centrality formula, missing seed,
  missing RStudio version, and greeting as mandatory regression cases.

Private checkpoint: `data/study-reviews/gpt-evidence-broad.json` includes all
drafts, repairs, audits, evidence, ranking traces, timings, and forced-refusal
flags. Chunk IDs are diagnostic anchors, not automated semantic grading. No
copyrighted passages were added to repository fixtures. No user chats changed.

Run `python3 -m scripts.evaluate_gpt_evidence --output
data/study-reviews/gpt-evidence-NEW.json` as one command. Existing output is
protected against accidental overwrite; `--resume` skips completed cases.
Interrupted follow-ups require their preceding context to be rerun, not a fresh
conversation presented as continuation. Baseline was checkpoint-resumed after
fixing an audit input-budget argument bug, before candidate evaluation began.
Deterministic verification: 251 passed, one skipped; not a semantic-quality claim.
