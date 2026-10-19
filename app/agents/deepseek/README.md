# DeepSeek workflow

Selected automatically for `deepseek-r1:8b` at `main.selected_agent`.
Llama 3.2, Phi-4 Mini, and GPT-OSS still use the existing `ChatAgent` unchanged.
No global prompt or inference setting is mutated when the user switches models.

## Responsibilities

- `agent.py`: owns turn orchestration, pause/resume state, and atomic persistence.
- `planning.py`: model-owned intent and validated JSON tool-call schemas. Invalid
  JSON gets one repair attempt; failure never falls through to ordinary chat.
- `search.py`: a separate search planner runs only for retrieval intent. Code
  executes only `search` and `overview`, within the selected material IDs. Two
  rounds of at most four calls, at most eight unique passages. Comparisons can
  search each concept separately. Sources retain original metadata and labels.
- `client.py`: DeepSeek-only reasoning budget, transport, and completion checks.
  Structured calls reserve 4,096 tokens; conversation calls reserve 6,144.
  Thinking is explicitly enabled: the installed tag continued reasoning even
  with `think: false` in a live probe, exhausting a 1,200-token budget.
  Input accounting reserves that output space
  plus a 512-token margin within the configured context. Transport timeout is at
  least 240 seconds per call. These are initial test settings, not performance
  guarantees or whole-request latency limits.

This uses schema-constrained JSON actions rather than assuming this Ollama tag
supports native function calling. The model requests reads; code validates and
executes them. Retrieved content cannot change the chosen conversation route.

## Shared components

The vector index, embedding retriever, document reader, conversation store,
prepared quiz bank, grading ledger and source-support writer remain shared.
They run with the DeepSeek client, not the legacy client. The quiz subsystem
still owns its internal question-generation and quiz-specific intent calls.
This isolates the top-level architecture without duplicating those stateful
contracts. Source-support checks are retained, not assumed unnecessary because
the model is larger. They do not guarantee factual accuracy.

No reasoning text is stored. Usage records capture finish reason, reasoning
character count, and token reserves. A truncated or empty completion raises an
explicit error before saving the turn. There is no automatic downgrade to
another model or general-knowledge answer.

## Verification

`tests/test_deepseek_workflow.py` covers dispatch isolation, invalid routing,
pause-state preservation, source scope, and truncation. The existing model-switch
test checks history continuity across all four choices.

Live evaluation uses `scripts/evaluate_model_workflow.py` and temporary sessions.
Private results are kept under ignored `data/study-reviews/`. See
`docs/deepseek-evaluation.md` for observations, not just test pass counts.
