# Intent Ownership and Code-Owned Attribution

## Decision

Promote the separated intent/planner contract. Keep the code-bound writer as an
experiment: mechanically correct source assignment did not make its claims
reliably supported. The live grounded writer is unchanged.

## Implemented Contract

- IntentRoute alone owns conversation/retrieval/quiz/clarification and activity
  actions. Natural-language turns in the app no longer bypass this stage because
  of quiz keywords. Explicit answer selections retain their direct quiz path.
- RetrievalPlan runs only for retrieve. Its schema forbids extra fields and has
  no route, mode, or pause/resume fields. It resolves the question, selects from
  the session materials and decides whether existing evidence can be reused.
- A failed planner cannot overwrite a valid intent. Its fallback uses the intent
  query/latest message with the existing scoped material tools.
- Pause/resume preserve the pending question, options, cursor and score ledger.
  Resuming a pending question does not grade the resume request or advance it.
- Per-turn material selection no longer shrinks the saved session batch.
- The old IntentDecision schema/prompt remain for baseline experiments only.
  Legacy quiz-format mechanics remain inside the quiz subsystem; this is not a
  rewrite of every quiz interaction into the new schema.

## Routing Probes

Four existing probes repeated twice: greeting, quiz pause, return to the book,
and a noise follow-up. Local Ollama, temperature 0.2, 4K context. These are
independent stage probes, not a broad benchmark or end-to-end retrieval test.

| Version | Model | Passing turns | Calls |
| --- | --- | --- | --- |
| Initial ownership prompt | Llama 3.2 3B | 6/8 | 10 |
| Clarified reuse versus routing | Llama 3.2 3B | 8/8 | 12 |
| Same revised prompt | Phi-4 Mini | 7/8 | 11 |
| Final quiz-resume distinction | Llama 3.2 3B | 8/8 | 12 |
| Final quiz-resume distinction | Phi-4 Mini | 8/8 | 12 |

Initial Llama failures classified a repeated source explanation as conversation.
Clarifying that retrieve means source-grounded, not necessarily a new search,
recovered both probes. Phi still unnecessarily clarified one noise follow-up.
Phi also requested evidence reuse once with empty previous evidence; production
code correctly requires actual reusable evidence before taking that path.
Greetings and pauses no longer incur a second routing/planning call.

Do not compare these percentages as a controlled speed or model ranking against
older 16K runs. The schema, prompt and call graph changed.

## Attribution Experiment

Used the user's imported Data Science from Scratch chunks 445-447 and the six
existing evidence-chain questions, once per model at 4K. Compared the frozen
explicit-abstention writer against the same base instructions with one source
block per call, explanation strings only and citations appended by code. No
retrieval or evidence selector was involved, so this isolates writing rather
than claiming retrieval improved. The model never receives the assigned label
in the code-owned variant. Source text/raw traces stay in ignored local reports.

Llama: 24 calls. Both variants abstained on both missing-fact controls. Code-owned
output correctly attached the sampling answer solely to S1, whereas the original
included superfluous source references. But comparison, exception and noise
answers still added unsupported or reversed claims. Original comparison also
had an answered-with-empty-points validation error. Median per-case time was
2.98s original and 3.44s code-owned, including errors/abstentions.

Phi: 13 calls. Original abstained on both negative controls but had comparison
and qualification errors. All six code-owned cases violated the output contract
by returning insufficient_evidence with nonempty points. Execution stopped at
the first invalid source output in each case; these are errors, not successful
abstentions, and later source blocks were not evaluated. Their shorter timings
must not be interpreted as a performance gain.

This refines, rather than erases, the earlier failed simple bound-writer test:
keeping the old abstention instructions helped Llama's negative controls, but
code-owned provenance still does not establish relevance or entailment.

## Reproducibility

Scripts: evaluate_route_interruptions.py --separated,
evaluate_owned_attribution.py, and evaluate_stage_ownership.py.
Reports under ignored data/study-reviews:

- owned-routing-llama-20261013.json
- owned-routing-llama-v2-20261013.json
- owned-routing-phi4-20261013.json
- owned-attribution-llama-20261013.json
- owned-attribution-phi4-20261013.json
- owned-stateful-llama-20261013.json
- owned-stateful-phi4-20261013.json

Stateful smoke runs use the real ChatAgent, the user's textbook inventory and a
temporary conversation store with a seeded pending question. They test pause,
greeting and resume at the production 16K context without altering user sessions.
Llama initially passed all three. Phi initially passed pause/greeting but routed
quiz resumption to retrieval, producing an irrelevant overview. An explicit
distinction between returning to a saved quiz and re-explaining source material
then recovered all three Phi turns (owned-stateful-phi4-v2-20261013.json).
The final prompt also passed all eight independent probes on each model; see
owned-routing-llama-final-20261013.json and owned-routing-phi4-final-20261013.json.
Across the recorded experiments and stateful checks there were 114 real model
calls, including failures. These small development probes are not evidence of
universal routing reliability. Unit suite: 195 passed, one skipped.
Unit coverage includes state preservation, choice-click bypass, rejecting
planner route fields, source-scope persistence, and attribution validation.

## Model switching feedback (2026-10-13)

The selector previously saved a browser preference without preloading. It now
awaits an empty Ollama chat request using the configured context window before
committing the selection. A Professor-head loading dialog appears after 200 ms;
there is no minimum display duration. The header names the ready model.
Failed loads preserve the previous selection. An in-process lock excludes chat
and overlapping preload requests, and stale health responses cannot overwrite
the pending UI. This lock assumes the current single-worker local deployment.

Verified both directions with installed Llama 3.2 and Phi-4 Mini in the browser:
the animated dialog appeared during loading and closed on completion. A later
warm switch completed without displaying it. Existing chats were not changed.
Unit suite: 200 passed, one skipped; JavaScript syntax and diff checks passed.
No framework dependencies, model prompts, or retrieval behavior changed here.
Preloading does not enforce an 8GB memory limit or unload other Ollama clients'
models; those remain separate resource-management concerns.

## Answered-question replay regression (2026-10-13)

The user's Phi session returned the old median question after "Next question",
with only an intent model call recorded, phase still review and cursor still 0.
This matches the resume branch: it returned pending_question regardless of phase.
The recent intent-ownership change left this transition insufficiently guarded.

The Next question UI now carries the answered question ID through a typed API
field. Code validates that ID and phase and executes the explicit next action;
it is not inferred from keywords. Editing the filled message clears the action.
Natural-language requests still use the model, with a clarified next/resume
distinction. Resuming during review no longer repeats an answered question.
Stale button events are rejected without advancing twice.

Real Phi replay used an isolated copy of the affected session and its Data Science
from Scratch PDF. Typed advancement produced question 2 and four choices. Button
advancement produced questions 2, 3, 4 and 5, four choices each, unique stems and
new question IDs, then completed after answers. The original session was unchanged.
Report: data/study-reviews/quiz-progression-phi4-20261013.json.
Script: scripts/evaluate_quiz_progression.py. Unit suite: 203 passed, one skipped.
Browser verification confirmed the action ID is set by the button and removed
when its message is edited. Updated server and browser assets are running.

These are progression checks, not an accuracy benchmark. The generated salary
question still had weak/misaligned distractors, and some option strings included
letter prefixes. Record these as outstanding generation-quality issues; the
successful progression run does not establish that every question is sound.

## Prepared quiz playback (2026-10-13)

Quizzes now prepare and persist the complete remaining question set before
displaying a new question. Preparation runs bounded single-question generation
and quality checks sequentially, including earlier prepared stems in duplicate
checks. Questions retain their choices, answer keys, IDs and source passages.
Failed preparation does not save a partially generated bank. Numbered progress
reports the question being prepared. Default length remains ten unless specified.

Explicit Next actions load the saved question without an LLM call. Assessment
still uses the stored key and generates an explanation. The final question stays
in conversation context after completion, while missed review uses recorded
outcomes. Future question banks are excluded from writer prompts and public API
responses. The UI hides Next after the final answer but retains follow-up access.

Live Phi-4 Mini test prepared five questions from the user's Data Science from
Scratch PDF in 249.78 seconds, then answered and advanced through all five to
completion. Every explicit Next action made zero model calls. The original user
session was untouched; the test used temporary conversation storage.
Report: data/study-reviews/prepared-quiz-phi4-20261013.json.
Reproduce with scripts/evaluate_quiz_progression.py --fresh and a saved session.

Verification: 208 tests passed, one skipped; JavaScript action visibility and
syntax checks passed; git diff --check passed. New tests cover reload playback,
atomic failure, resume preservation, last-question context, private bank
exclusion, progress isolation and correct missed-review selection.

Limits: upfront latency is substantial, and explanations still incur model
latency. This is a progression test using saved answer keys, not an independent
factual-accuracy benchmark. Some generated options still include letter prefixes,
and wording/distractor quality remains a separate issue. No 8GB memory benchmark
was performed. Existing quizzes prepare their remaining questions on advancement.
