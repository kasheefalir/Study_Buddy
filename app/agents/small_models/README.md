# Small-model experiments

This folder contains Llama 3.2 3B and Phi-4 Mini workflow experiments plus the
small production-safe ID constraint helper. GPT-OSS and DeepSeek are unchanged.

`source_constraints.py` is used by production structured retrieval planning for
these small models only. It restricts document IDs to the supplied session scope
in both the decoding schema and post-parse validation. IDs are not renamed or
inserted into answer text. Intent, quiz generation, retrieval ranking, the writer
and its existing grounding checks remain unchanged. No additional model calls.
The experimental workflows below are not enabled in the live application.

`workflow.py` uses two model calls: a structured part planner, then a grouped
answer writer. Code owns short material aliases, question IDs, evidence labels,
retrieval execution and reference rendering. Each answer part may select only
its own evidence IDs through a dynamic JSON-schema enum. No semantic checker or
automatic retry is added. Unverified support and optional extra context carry
explicit notes in the result object; these notes are not yet wired into the UI.

Run from the repository root with the local materials and Ollama available:

```sh
python3 -m scripts.evaluate_small_grouped --output data/study-reviews/small-grouped-new.json
```

The report contains private uploaded text; do not commit it. Use a fresh filename.
The fixed case set supplies intent and selected material, so it does not test
conversation routing, quiz state or multiple-material selection. Both models
currently use the same experimental prompts to isolate their behavior.

Valid source IDs prove that references resolve, not that claims are supported.
See `docs/small-query-planning-results.md` for outcomes and promotion decisions.

## Exact-quote trial

`quoted_trial.py` preserves the earlier grouped experiment unchanged. It uses
`SOURCE_001` material aliases only in planner control metadata and
`PASSAGE_001` references in writer metadata, structurally separate from passage
text. Material aliases and search queries are not passed to the writer.
Each question focus must be an exact original-question span. The complete
question accompanies each independent writer call. Code combines answers,
attaching exact quotes without another model synthesis pass.

Every accepted claim must have a nonempty verbatim substring of its cited,
in-scope passage. Unknown IDs, missing quotes and paraphrased quotes fail
validation. This verifies quote provenance, not semantic entailment. Generated
overview quotations remain generated-summary evidence, not original-book quotes.

```sh
python3 -m scripts.evaluate_small_grouped --quoted --output data/study-reviews/quoted-new.json
python3 -m scripts.evaluate_small_grouped --quoted --oracle-parts --output data/study-reviews/quoted-oracle-new.json
```

The second command uses human-defined fixture parts to diagnose writer failures;
it is not a production planner and must not be reported as automatic success.
Exact span matching does not prove the planner covered every request or preserved
its meaning. No strict-quote workflow is enabled live: observed false refusals
and decomposition failures prevent promotion.
