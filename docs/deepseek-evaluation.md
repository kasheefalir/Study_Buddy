# DeepSeek R1 8B application workflow test

Date: 2026-10-13. Model: `deepseek-r1:8b`, installed ID `6995872bfe4c`.
The test used the app's FastAPI chat endpoint, real local Ollama, the user's
Data Science from Scratch PDF, and a temporary conversation store. Existing
user sessions were not changed. No production prompts or inference settings
were adjusted. Context: 16,384; output limit: 1,200 tokens per call.

## Observations

| Probe | Seconds | Outcome |
| --- | ---: | --- |
| Greeting | 109.48 | Friendly response, no retrieval. |
| Book-specific betweenness centrality question | 108.78 | General answer, zero sources, no retrieval stage. Grounding failed. |
| Explain that more simply | 115.86 | Conversational explanation, still no evidence. Used stronger unsupported wording about most traffic. |
| Exact author laptop and RAM | 96.75 | Declined to provide the specification, but did not search. Not a validated source-backed abstention. |
| Two-question multiple-choice quiz | 129.69 | Returned both questions in ordinary prose. Quiz state remained empty; no saved questions or clickable choices. |

All five requests returned HTTP 200. All five intent calls consumed exactly
1,200 output tokens, followed only by an answer call. No retrieval planner ran.
This strongly suggests the intent stage exhausts its output budget before
producing usable structured output. Raw thinking and finish reasons were not
captured, so truncation is a hypothesis, not proven by these logs alone.

The routing failure handler can set the route to clarification and proceed to a
normal writer; the writer then produces plausible text instead of exposing the
failure. This is a harness issue as well as a model-budget compatibility issue.
The earlier tiny JSON probe passed, but did not predict real intent-prompt behavior.

Ollama `ps` reported 7.8 GB loaded size, 100% GPU, at 16K context. This is not
whole-system peak memory, a universal requirement, or an 8GB-machine benchmark.
The installed quantized model's disk size was 5.2 GB.

## Conclusion and next tests

Not ready to recommend for Study Buddy's current multi-stage workflow. It can
converse, but these runs bypassed grounding and failed to enter the quiz loop.
Playback and missed-answer review could not be tested because no quiz was created.

Next: capture intent validation/finish failures explicitly, prevent those failures
from silently producing ungrounded task answers, and compare reasoning controls
or a larger model-specific output budget against this unchanged baseline.
Do not increase context or claim a better model fixes the fallback behavior.

Reproduction script: `scripts/evaluate_model_workflow.py`.
Private full results: `data/study-reviews/deepseek-workflow-20261013.json`
(ignored by Git, including source passages and saved quiz state).

## Isolated architecture experiment

The new `app/agents/deepseek/` workflow is selected only for DeepSeek. Legacy
Llama, Phi and GPT-OSS orchestration and inference files were not edited.
The first isolated greeting completed correctly in 102.32 seconds, with normal
`stop` finish reasons. That partial run was stopped during the next retrieval
turn to investigate control-stage latency; it is not a completed benchmark.
Its report is `data/study-reviews/deepseek-isolated-20261013.json`.

A direct `think: false` probe with 1,200 output tokens returned empty final
content, nonempty thinking, `eval_count=1200`, and `done_reason=length` in about
66 seconds. The installed model did not reliably disable reasoning. That
optimization was rejected. Current structured calls explicitly enable thinking
with 4,096 output tokens and reject truncation rather than falling back to chat.
Conversation calls reserve 6,144. Context stays at 16,384; these settings have
not been validated on an 8GB computer.

The schema-aware isolated run completed these live probes:

| Probe | Seconds | Outcome |
| --- | ---: | --- |
| Greeting | 74.78 | Conversation route, no sources or quiz generation. |
| Book-specific betweenness centrality | 519.71 | Retrieval ran, four passages returned, answer cited S3/S4 from Page 274. Both cited passages support the definition. |

The retrieval answer correctly described summing the proportions of shortest
paths between other node pairs that pass through a node. Two other retrieved
passages were irrelevant front matter; the writer did not cite them. The run
used two search-planning passes, then the shared grounded writer and support
check. This fixes the observed bypass for this probe, not retrieval accuracy
in general. Latency is poor: this configuration is experimental, not optimized
for everyday use. A larger reasoning budget fixes completion headroom but does
not solve the model's long deliberation at every stage.

The broad run was stopped after those completed probes; follow-up, missing-fact,
and live quiz playback were not completed in this run. Do not count them as
passes. Private report: `data/study-reviews/deepseek-isolated-schema-20261013.json`.
The evaluation script now accepts `--cases` to run expensive probes separately.

Schema validation alone constrains output form; planner prompts now also include
the schema and intent examples to explain the fields. A preceding schema-implicit
run was interrupted during its greeting and is not a completed benchmark.

Regression verification: 229 Python tests passed, one skipped, plus the Node
classroom interaction checks. Dedicated tests cover dispatch isolation, model
switch history, invalid/truncated routing, source scope, separate comparison
reads, paused quiz preservation, failed-quiz rollback, and model-free prepared
question advancement. Mocked tests establish mechanics, not model accuracy.

## Speed experiments (2026-10-13)

These profiles are opt-in constructor options and evaluation scripts, not changes
to the live model factory. Llama/Phi/GPT-OSS workflows remain unchanged. Real-model
probes used the same Data Science from Scratch PDF and temporary conversations.

| Experiment | Measured result | Decision |
| --- | --- | --- |
| Combined DeepSeek intent + initial search; no routine second planner | 516.30 seconds, three calls, supported betweenness answer citing S1/S2 | No meaningful speed gain versus the earlier 519.71-second/five-call run; do not promote. |
| Llama combined controller | 2.64-5.63 seconds per probe; 1/6 strict contracts passed | Reject this combined-controller profile. |
| Phi combined controller | 1.34-5.06 seconds per probe; 1/6 strict contracts passed | Reject this combined-controller profile. |
| Exact source-read cache | Cold 0.86 seconds; warm 0.01 seconds, same four passages | Useful small saving, not the main latency fix. Remains opt-in. |
| Separate vs batched support checking | 214.42 seconds/three calls vs 149.74 seconds/one call; both returned supported/unsupported/unsupported | Retain batched checker experiment; approximately 30% faster for this stage, not proven for all answers. |
| Intent-only Llama controller | 1.01-3.77 seconds; 4/6 route/action contracts passed | Narrower responsibility helps, but pause/resume contract failures prevent promotion. |
| Intent-only Phi controller | 1.06-4.35 seconds; 4/6 route/action contracts passed | Same contract failures; follow-up subject resolution also remains unverified. |

The combined DeepSeek run generated 8,807 output tokens across intent (3,291),
writer (2,431), and support check (3,085), with substantial thinking in all three.
Fewer calls alone did not reduce the total reasoning burden. This is a single
question, not a statistically controlled speed comparison or a full quiz test.

Controller contract tests cover greeting, narrow fact, follow-up, comparison,
quiz pause, and quiz resume. Strict scoring requires search rather than overview
for narrow questions and distinct searches for comparisons. The initial loose
scores were corrected and retained in reports for audit. An incorrect explicit
pause action does not necessarily mean app state is lost: the app also pauses
an active quiz on conversational turns. These scores are not end-to-end grades.

The cache is bounded, expires after five minutes, copies results defensively,
and keys source content, material metadata, query, embedding model/index version,
and library root. It does not cache generated answers or intent. Conditional
recovery is limited to one extra search on an evidence gap and never forces an
answer. Unit tests cover both empty retrieval and failed answer support.

Loaded-model observations at 16K context were approximately 4.0 GB for Llama,
4.8 GB for Phi, and 7.8 GB for DeepSeek. These are Ollama model allocations, not
peak system RAM or minimum requirements. Keeping a second controller loaded
could increase memory pressure; no 8GB-machine claim is established.

Reproduction: `python3 -m scripts.evaluate_deepseek_speed --help`.
Private reports: `data/study-reviews/speed-controls-llama.json`,
`speed-controls-phi.json`, `speed-cache.json`, and
`speed-combined-deepseek.json` in the same ignored directory.

Checker probe: three fixed claims from the actual retrieved textbook passages:
supported betweenness definition, invented author laptop/RAM specification, and
the correct definition cited to unrelated front matter. Both methods accepted
only the first. Batched checks validate every expected verdict and reject missing
verdicts. This is not a complete answer-generation abstention test. The combined
workflow returned only one answer point, so batching would not have reduced its
single checking call. Reports: `speed-checks.json`, `speed-intent-llama.json`,
and `speed-intent-phi.json` in the same private directory.

No experimental profile was promoted to the live factory. Recommended next
experiment: broader batched-check accuracy evaluation and a bounded reasoning
policy, measuring truncation and abstention as well as time. Do not simply lower
the output cap: the earlier 1,200-token cap prevented valid final output.
Regression verification after speed changes: 236 tests passed, one skipped.
