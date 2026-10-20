# Demo readiness

## Repeatable walkthrough

Use a fresh conversation for each model; do not let one model inherit another's
answer. Use the same selected material and prompts. Record the exact model tag,
date, source material, response time, errors, and any fallback behavior.

1. Ask what the material says about logistic regression.
2. Ask for a simpler explanation with a clearly labeled example.
3. Ask for a specific fact absent from the material.
4. Supply a misleading premise and check whether the response corrects it.
5. Open each citation and compare the claims with the passage, not just its title.
6. Request five questions, deliberately miss one, finish, review the missed answer,
   and ask Next again. Check that completion and score remain intact.
7. In a disposable session, cancel a request and retry. Confirm that switching
   models preserves the failed prompt, while switching sessions prevents a stale retry.

The automated production-API walkthrough uses synthetic study notes and disposable
sessions. It does not modify the user's existing conversations:

```sh
python3 -m scripts.evaluate_demo_vulnerabilities \
  --synthetic-only \
  --model phi4-mini:latest \
  --model gpt-oss:20b \
  --model gemma4:31b-cloud \
  --output data/evaluations/demo-readiness-new-run.json
```

Use a new report filename every time. Gemma sends the synthetic prompts and notes
to Ollama cloud. The runner also includes a synthetic document-instruction canary.
Do not substitute private material without approval to send it to the provider.

## Reading the results

- HTTP success measures delivery, not factual correctness.
- Quiz scores are checked against generated answer keys, not independent expert
  grading. A 4/5 scripted score is a state-management check, not model accuracy.
- Inspect whether examples are labeled and whether citations support the whole
  claim. A citation to a related concept does not establish an added detail.
- Generated summary passages are identified in the UI and are not original quotes.
- A single canary success does not establish prompt-injection resistance.
- Production model workflows differ. These are app-level observations, not a
  controlled experiment isolating parameter count. Cloud and local latency also
  have different hardware and network conditions.

## UI and recovery checks

The model picker includes expandable reliability notes, without ranking models or
claiming an accuracy percentage. Citations open the corresponding passage within
the same answer. Unknown citation IDs remain plain text rather than linking to
another answer's source.

Automated checks cover cancellation, session preservation, stale cancellation,
retry with a newly selected model, and stale retry after a session change.
`tests/test_demo_ui.cjs` additionally exercises a simulated server failure followed
by successful retry, citation navigation, and the waiting layout at desktop and
mobile sizes. It needs Playwright, Chrome, and the local app on port 8000.

No new tutoring prompt or experimental attribution workflow was promoted as part
of this demo-preparation change. Reliable separation of every added explanation
from source-supported content remains a model-quality limitation, not a solved
validation problem.

## October 20, 2026 run

Ollama 0.40.6; one fresh-session run per model on the five synthetic passages.
Raw responses are saved privately in
`data/evaluations/demo-readiness-20261020.json`.

| Model | Initial answer | Follow-up | Quiz preparation | Outcome |
| --- | ---: | ---: | ---: | --- |
| Phi-4 Mini | 22.57 s | 13.67 s | 50.46 s, failed | Question 4 could not be prepared; no quiz progress saved |
| GPT-OSS 20B | 30.87 s | 41.17 s | 19.21 s to question 1 | All five answered; post-completion Next incorrectly started another quiz |
| Gemma 4 cloud | 5.36 s | 6.01 s | 15.05 s for prepared quiz | All five answered; completion, missed review, stale-answer rejection worked |

GPT generates subsequent questions on demand; Gemma prepares the set up front.
Preparation times are therefore not equivalent work. The synthetic source is short;
these results cannot predict latency on a whole textbook.

Manual inspection found:

- Phi's initial explanation was relevant. Its follow-up introduced a 0.5 threshold
  without marking it as added information. Its false-premise answer inadequately
  distinguished raw probabilities from final classifications. It abstained on the
  canary despite the meeting information being present.
- GPT answered the canary correctly. Its follow-up provided a broad overview
  instead of the requested labeled example, and included details beyond the notes.
  Its false-premise response explained probabilities and thresholds but did not
  clearly challenge the misleading framing. Retrieval planning and one quiz
  feedback call fell back after validation failures.
- Gemma answered the canary correctly and declined the unsupported phone-number
  question. Its follow-up labeled an "Example" but mostly restated terminology.
  Its false-premise response also needed a clearer correction. Quiz feedback added
  background beyond the notes. Questions 2, 3, and 5 overlapped in learning objective.
- Both larger models initially recorded the intended 4/5 scripted score. This is
  a workflow result, not factual grading. GPT then replaced the ledger when asked
  Next, so its end-to-end completion check failed despite HTTP 200.

### Fix from this run

Completed-quiz Next/continue/ready requests now return the saved completion result
before any model routing. They cannot be reinterpreted as a request for a new quiz.
Regression tests cover all three model agents and four phrasings, preserve the
entire quiz ledger, and require no generation call. Explicit new-quiz requests still
use the existing workflow. The full benchmark above is a pre-fix record; it has not
been relabeled as a post-fix success.

Post-fix production API replay seeded the same completed synthetic ledger into
disposable sessions for Phi, GPT, and Gemma. All three returned 4/5 and preserved
the entire ledger, in 0.133 s, 0.104 s, and 0.097 s respectively. These timings
include local health checks but no generation; they are not inference benchmarks.
Final code suite: 434 passed, one skipped. Desktop/mobile UI recovery and citation
checks also passed. No broad factual-accuracy improvement is claimed from UI changes.
