# GPT-OSS workflow

Selected only for `gpt-oss:20b` by `app.main.selected_agent`.

- `agent.py`: GPT-specific policy using shared chat/storage mechanics.
- `client.py`: low reasoning, 4,096-token output headroom, fail-closed completion checks.
- `router.md`: model-owned intent and quiz transitions.
- `retrieval.md`: source query planning; cannot override intent.
- `professor.md`: conversational tutor instructions.

New quizzes generate and validate only the current question. Next generates the
following question using the saved topic plan and prior questions. Existing
fully prepared quizzes remain usable when switching models. Background prefetch
is not implemented in this first trial; Next may require a model wait.

The shared quiz engine still owns numbering, correct-answer matching, duplicate
checks, source windows, missed-answer review, and save-on-success behavior. A
failed generation does not advance persisted progress. Llama/Phi keep their
existing eager preparation. DeepSeek retains its own existing architecture.

Source answer checks remain enabled. Shorter instructions are not a reason to
remove grounding or rely on assistant prose as evidence. The live-model trial
still misrouted a simplification follow-up to conversation; that limitation is
tracked in `docs/gpt-oss-evaluation.md`.

## Isolated evidence experiment

`evidence_trial.py` is not wired into the live agent. It preserves independent
keyword/vector candidates and audits draft claims against their sources. Code
checks source IDs, quotation text, and audit excerpts; semantic support is still
a model judgment, not a guarantee. `scripts/evaluate_gpt_evidence.py` compares it
with the previous native-tool experiment across three local materials. It allows
one repair, records rejected drafts, and records forced abstentions separately.
No existing user conversations, model settings, or indexes are changed.

Promotion requires manually checking the answers, preserving missing-information
abstention, avoiding new false refusals, and measuring the latency cost. Valid
quotation strings or a model audit's approval alone do not constitute a pass.

Status: **rejected for production** after the broad trial. The audit/repair chain
forced refusals on all eight answerable probes. See the evaluation ledger before
revisiting it. Do not enable this module merely because its unit tests pass.
