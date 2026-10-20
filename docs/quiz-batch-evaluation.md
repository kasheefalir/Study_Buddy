# Quiz batching pilot - October 20, 2026

## Protocol

Compare Phi-4 Mini, GPT-OSS 20B, and Gemma 4 cloud on the same five synthetic
logistic-regression passages and a fixed five-question coverage plan. Run one,
two, and five-question preparation modes sequentially for each model. No private
uploaded material is sent to the cloud.

```sh
python3 -m scripts.evaluate_quiz_batches \
  --output data/evaluations/quiz-batches-new-run.json
```

Each mode starts with a fresh quiz. Two-at-a-time prepares questions 1-2, then 3-4,
then 5. It is bounded look-ahead using sequential generation calls, not a single
prompt asking for two questions. Each question still has its own evidence and
validation. A failed batch does not overwrite the last saved answers.

The runner uses production clients and model-specific budgets, but bypasses intent
routing and starts from a fixed coverage plan to isolate quiz generation. GPT uses
its production reasoning client. These are not identical-budget model-size
comparisons, browser tests, or independent factual-accuracy benchmarks.

The runner checks five answers, two deliberate mistakes, completion, missed-answer
review, saved-state reload, and hidden answer keys. A passing score is measured
against the model's generated key, not an independent oracle. Questions and keys
must also be inspected manually.

Run order is 1, 2, then 5. The first mode may include cold loading; later modes may
benefit from warm models. One run per condition cannot establish consistent gains.
All passages concern logistic regression; arbitrary whole-book concept clustering
is not implemented by this experiment.

## Safety and UI

The batch-size parameter is experimental and does not change live model dispatch.
Existing live defaults remain GPT one-at-a-time, Phi/Gemma all-upfront pending
evidence for a change.

For quiz generation/validation limits, the UI now says:

> My brain hit a snag with this quiz. Try again, ask for fewer questions, or try a
> larger model. A bigger model may help, but it can still make mistakes.

Connection failures retain connection-specific advice. The notice does not assert
that model size caused a failure. It is a transient application message, not added
to model history, and is removed on retry.

## Results

Raw report: `data/evaluations/quiz-batches-20261020.json` (ignored/private).
One run per condition; times include retries and may include cold loading.

| Model | Prepared at a time | Answers completed | Mechanics passed | First question | Total elapsed |
| --- | ---: | ---: | --- | ---: | ---: |
| Phi-4 Mini | 1 | 1/5 | No, question 2 failed | 9.91 s | 30.01 s |
| Phi-4 Mini | 2 | 4/5 | No, question 5 failed | 15.60 s | 77.32 s |
| Phi-4 Mini | 5 | 5/5 | Yes | 48.19 s | 70.30 s |
| GPT-OSS 20B | 1 | 5/5 | Yes | 22.58 s | 149.08 s |
| GPT-OSS 20B | 2 | 4/5 | No, question 5 failed | 23.49 s | 138.14 s |
| GPT-OSS 20B | 5 | 5/5 | Yes | 90.80 s | 138.62 s |
| Gemma 4 cloud | 1 | 5/5 | Yes | 1.60 s | 25.13 s |
| Gemma 4 cloud | 2 | 5/5 | Yes | 10.63 s | 33.67 s |
| Gemma 4 cloud | 5 | 5/5 | Yes | 8.46 s | 16.01 s |

Total elapsed sums API work in the scripted sequence, with no human reading or
answering time. Failed runs stop early and must not be interpreted as faster
completed quizzes. All successful conditions preserved completion, scored the
scripted selections as 3/5, and retained missed-answer review.

### Quality and context

- Phi's two-question mode repeated sigmoid questions immediately. Its five-question
  mode also repeated that concept; the first stem misleadingly asked what the
  sigmoid does to "estimated probabilities" rather than a real-valued score.
  Finishing did not establish reliable question quality.
- GPT's incremental mode repeated the sigmoid concept; its full-preparation mode
  repeated L1 feature selection in questions 4 and 5.
- Gemma's keys matched the core concepts in the supplied notes on manual inspection,
  but questions 4 and 5 repeated L1/L2 effects in all three modes. No independent
  blinded grading of every feedback claim was performed.
- Peak app-estimated input was 1,418-1,743 tokens per call across the nine runs.
  This is an estimate of request text, not an Ollama tokenizer measurement. No
  context-window overflow was observed on this short fixture. Larger books and
  long conversations still require separate tests.
- Two-question preparation uses the same per-question generation and checks. It
  moves waiting to batch boundaries; it does not inherently reduce model calls.

### Decision

Do not promote two-question batches from this pilot. Keep Phi's existing full
preparation and GPT's incremental mode. Gemma incremental is a viable candidate
for a faster first question, but full preparation had lower total elapsed here.
Keep its live default unchanged until repeated runs and a clear interaction
preference justify the trade-off. No factual-accuracy improvement is claimed.

The friendly failure notice is enabled. Batch sizing remains opt-in in the
evaluation runner. Regression suite: 436 passed, one skipped; desktop/mobile
failure-message and retry checks passed.
