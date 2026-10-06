# Local AI Study Buddy

On this Mac, run `study buddy` from a new terminal. The launcher starts a local
Ollama service if necessary, downloads the configured model if missing, preloads
it, and starts the app. Ollama and the Python dependencies must already be installed.
First-time model downloads require internet access. Open http://127.0.0.1:8000.
Use `BUDDY_PORT=8001 study buddy` if another server occupies port 8000.

Ctrl+C stops the app and any Ollama process started by this launcher; an existing
Ollama service is left running. The model stays warm for 30 minutes after startup
or the latest chat request and reloads on demand afterward.

A local-first study assistant powered by Ollama. Phase 1 provides a working chat API,
bounded conversation memory, local JSON persistence, and a minimal browser client.

## Required Downloads

1. Python 3.11+.
2. [Ollama for macOS or Windows](https://ollama.com/download). Install the
   application/runtime once before starting Study Buddy. The launcher needs the
   `ollama` command available in your terminal, or an already-running Ollama service.
3. Python packages listed in `requirements.txt`, installed with pip during setup.
4. `llama3.2:3b` model weights. The launcher downloads these automatically on first
   use if missing; no separate manual model download is required.

Ollama is a system dependency, not a pip dependency. Installing a Python package
named `ollama` does not install the runtime; this app communicates with the
runtime directly through its local HTTP API.

## Setup

Install Python and Ollama from the list above first, then install the Python
dependencies and start the app:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
chmod +x start-mac.command
./start-mac.command
```

On Windows, activate the virtual environment and run `start-windows.bat`. Open
<http://127.0.0.1:8000>. Interactive API documentation is at `/docs`.

## Frontend API

### Grounded Study Materials

Upload a PPTX, DOCX, TXT, or Markdown file, or add a public HTML/plain-text URL
through the bookshelf. Successful imports are confirmed and added to the current
session batch. Check existing library materials to include them. Clear batch
returns to general chat. Resuming a session restores its own material selection.

PowerPoint extraction includes text, tables, grouped text shapes, and speaker
notes with slide numbers. It does not perform OCR or interpret diagrams.
URL imports fetch a single public page, not an entire site, and do not run
JavaScript or sign into websites. Private network URLs are rejected.

Original uploads stay in data/documents. Each material has an archive directory
containing the extracted passages and chunks; URL archives also contain raw
response bytes, response metadata, and retrieval decision logs. Reimports retain
prior artifacts in a versions directory. Removing a material deletes its archive
too. Existing conversation source excerpts remain in the saved conversation.

For a session with materials, Ollama chooses a search, overview or no retrieval.
Local retrieval supplies bounded passages drawn only from that session's batch.
Professor explains and reasons from
that evidence, distinguishing illustrative examples from source claims. Raw
passages remain inspectable. This bounded planning step does not browse or run
arbitrary tools. Answers and citations are model-generated, not independently
verified. General explanations use the conversational tutor, with an optional
batch-scoped material-tool call. Material quizzes use the incremental window,
question and feedback flow described below. There is no automatic answer rewrite.
Word DOCX body paragraphs and table text are extracted with paragraph references;
headers, footnotes and images are not read. Text PDFs support page citations and
hybrid keyword/embedding retrieval; scanned pages still require OCR.

Classmates receive deterministic excerpts from the selected material with source
locations. Their hover/click interactions do not invoke the model.

Send a first message without a conversation ID:

```json
POST /api/chat
{"message": "What is regularization?"}
```

The response contains `conversation_id` and `message`. Include that ID in later calls
to preserve context. `GET /api/health` reports Ollama and model availability.

## Configuration

### Chat and saved concepts

### Session Batches and Material Quizzes

Create a named session from Study sessions, then check the library files that
belong to its batch. Uploading and successfully importing a file adds it to the
active session. A new session starts with no files; switching restores its own
batch, transcript, notes and quiz state. Files remain reusable across sessions.
Deleting a library file removes it globally; sessions still referring to it
report it as missing rather than silently using another file.

The tutor can select a bounded `search_materials` or `review_materials` operation
over the session's batch only. Tool decisions and returned passages are stored
in `data/study-reviews`. No arbitrary URLs, code execution or cross-session
material access is permitted through these operations.

Quizzes default to five multiple-choice questions; explicit totals (1-50, including natural-language
requests) override the default. "One question at a time" does not mean one total.
Completed study overviews supply chapter-level concepts and original passages
for quizzes. Until an overview is ready, material text is divided into overlapping
three-passage windows in code. A short
quiz samples windows across documents and throughout each document; it does not
claim to review every page or cover every concept. A requested subject filters
windows by matching terms. Each question generates a small saved summary and one
question from its window, on demand. Startup needs two model calls (request
interpretation and the first window), not a full-book scan. Next question needs
one generation call. No ever-growing book summary is sent back to the model.
Schema, instructions, references and student text are checked against the input
budget, preserving the configured reply reserve and safety margin. Each call's
estimated context and actual usage are shown in token details.
Questions support short-answer and multiple-choice formats; pending answer keys
stay on the server. Clickable A-D choices show green for the correct answer and
red for a wrong selection, with text labels as well as color. Graded states survive
refresh; stale question submissions are rejected without changing progress.
Before grading free-form messages, a bounded intent call
distinguishes answers, hints, quiz changes and discussion. Clear option selections
are treated as answers; format-change requests regenerate the ungraded question
without changing the score. Preferences persist for subsequent questions. Feedback says
Correct or Incorrect, with a deeper explanation for mistakes. Hints and uncertain
assessments do not count as attempts. Missed answers, explanations and sources are
saved in the session's quiz results. Review missed answers replays those records
without model calls. Next question advances only after assessment; the final
assessment shows the score. Starting another quiz replaces the quiz state, while
the full conversation transcript remains saved.
Changing or reimporting the batch resets its quiz plan. Ingestion shows a pixel
book animation and confirms readiness, passage count and extraction limitations.

After a new import, a background overview worker summarizes bounded sections,
then reduces those into chapter summaries and a book overview. It saves each
completed node, concept list, original chunk references and model usage in
`data/documents/<id>/overview.json`. Full extracted content remains intact.
The cache is tied to the extracted content fingerprint and archived on reimport.
Existing materials expose Prepare study overview in My materials; preparation can
be paused and resumed, including after a server restart. Ready to search is
independent of overview completion. Progress reports actual completed nodes;
chapter/book reductions are included in the total. Only one overview runs at a
time, and it yields between calls when a conversation is active. A running model
call may still briefly delay chat. Preparation is not OCR or factual verification.
Chat preparation also reports its current backend stage beside the pixel-book
loader. Summary retrieval uses complete short sources when they fit; otherwise it
expands a complete cached summary-tree frontier within budget rather than sampling
chapters. Missing overviews are queued and partial coverage remains explicit.

`app/agents/prompts/retrieval.md` defines source selection, reading strategies and
task-specific success criteria. After reading, a model-driven sufficiency check
may request one additional search or overview within its selected source scope.
This adds one model call, not an unbounded scan. The writer gets evidence and
scope, not the planner's speculative notes. Packing reports omissions separately
from retrieval coverage. This is a bounded assistance loop, not a correctness
guarantee: small models can still select poorly or make unsupported claims.
When a selected batch or unfinished quiz exists, `intent_router.md` gives the
latest message a quick first read. Greetings and ordinary conversation bypass
retrieval; a new request can pause the old activity while its saved state remains
available. Router failure falls back to the normal agent path.

Professor's stable role lives in `app/agents/prompts/professor.md`. Separate
Markdown prompts define quiz, simplify, conversation recap and material summary
tasks. Role and task instructions stay separate from the conversation-context
data package, reference excerpts, recent messages and current student message.

Chat buttons prepare a draft and select its activity; the Activity menu can
override automatic routing. `/api/chat` accepts `task`: `auto` (default), `chat`,
`quiz`, `simplify`, `summary_conversation`, or `summary_material`. Retry retains
the original task. Recaps do not retrieve documents; material summaries do.
Hints and non-quiz tasks preserve the pending quiz question.

Outgoing messages appear immediately. Failed requests leave a visible retry
action. The transcript supports search, previous/next matches, jump to latest,
and locally bundled sanitized Markdown formatting. Follow-up buttons prepare a
draft without submitting it or replacing an existing draft.

Star an explanation to save its text and source passages as a concept. Concepts
can be renamed and removed from Saved concepts in the classroom menu or chat.
Bookmarks use browser localStorage: they are specific to this browser and origin
(including port), are not synced, and are not sent as model context.

Chat responses and stored assistant messages include `usage`: actual Ollama
input/output token counts and per-call stages for study planning and answering
(older replies may include verification). Missing counts remain null. Session totals include only recorded,
completed replies, not failed requests or older untracked messages. These are
cumulative processing counts, not remaining context capacity or a token budget.

Full conversation history is saved locally. Ordinary replies pack up to
`MAX_HISTORY_MESSAGES` recent messages, saved study notes, a rolling model-written
summary, and relevant source passages into an estimated input budget. Older history
is summarized in bounded batches when eight additional messages leave the recent
window or token pressure removes recent messages. Summary text and its covered
message count persist per session. Summary failures retain existing memory and
recent context; the original transcript is never replaced by its summary.

`CONTEXT_WINDOW` defaults to 16384; `RESPONSE_TOKENS` defaults to 1200. The packer
also leaves a 512-token margin, allocates reference space before recent history,
and preserves the current question. Excessively large current questions or auxiliary
study prompts return an explicit error instead of silently slicing JSON. Token
estimates use UTF-8 size and word/punctuation counts, not an exact model tokenizer.
Actual Ollama usage remains separate. Chat's token details show the last packing
estimate, reply reserve, passage count and summarized-message count.

Quiz topic, turn count and
pending question are saved per conversation and survive reloads and note edits.
"Stop the quiz" clears that state; a new conversation starts independently.

### Environment

Webpage imports now keep the original HTML, `clean_content.json` (Trafilatura
article sections), and `full_content.json` (broad page text). Both views are
indexed with section headings and final source URLs. Search combines keyword
rankings and local Ollama embeddings; summaries and quiz planning prefer clean
article text. If cleaning fails, full text remains available. Reimport old links
to build the new index. Reimport archives prior extractions and vectors.

The first webpage or PDF import downloads `nomic-embed-text` through Ollama; set
`EMBEDDING_MODEL` to change it. Vectors are saved locally in `embeddings.json`
and checked against the current content before use. If embeddings are unavailable,
keyword search continues and the material displays a warning. This is a local
vector index intended for a small library, not a separate vector database service.
Imports fetch one supplied public URL, not linked pages or JavaScript-rendered
content. Original snapshots and clean/full text are accessible from My Materials.

Material preparation also makes one bounded local-model call to generate two
short classmate facts from sampled extracted passages. Facts and source locations
are cached in each material's `facts.json`; hovering or interacting with classmates
never calls the model. The active session batch controls which facts are shown.
Reimport regenerates them and archives the old version. Existing materials need
Reimport to create facts. A fact-generation failure leaves the material searchable
and is shown in the ingestion confirmation. Generation token counts are saved as
`facts_usage` in material metadata, separate from conversation totals. Source IDs
are validated, but AI paraphrases are not independently fact-checked.

My Materials polls import status while open and shows per-item extraction,
indexing, classmate-fact preparation, readiness, failure, and interruption states.
An indeterminate progress bar represents stages without a measurable percentage.
Multi-file uploads show a queue and continue after individual failures. PDF extraction
shows pages processed, and semantic indexing shows passages processed.

PDFs use pypdf to preserve physical page numbers and available outline headings.
They use keyword plus local semantic retrieval and retain the original file.
Source passages include links to their PDF pages. Blank/unreadable pages are counted;
image-only PDFs request OCR, which is not implemented. Password-protected files need
an unlocked copy. Equations, tables, and images may not extract faithfully. Limits
are 2000 pages and 10 million extracted characters per PDF. Reimport previously
saved PDFs to make them searchable.

Environment variables: `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`,
`MAX_HISTORY_MESSAGES`, `CONTEXT_WINDOW`, `RESPONSE_TOKENS`, `EMBEDDING_MODEL`, and `BUDDY_DATA_DIR`.

## Response Review Loop

Set `RESPONSE_REVIEW_ENABLED=true` before starting the server to enable the experimental
bounded draft, review, and repair loop for normal teaching and material-summary replies.
It is OFF by default: live tests with llama3.2:3b falsely rejected supported answers.
Validate reviewer quality before enabling it for students. The definition of done is in
`app/agents/prompts/response_review.md`: follow the current request, use the intended
sources, support source-attributed claims, avoid needless clarification, and explain
limitations honestly. The model can accept, revise, or request another retrieval.

One review is added to a passing draft. A repair adds at most one retrieval-planning
call, one rewrite, and one final review. Every call is context-budgeted and successful
turns include all calls in token accounting. Brief review findings are stored with
the final conversation message; they are not reused as source facts. A failed final
review returns a retry error instead of publishing the rejected draft. Failed turns
are not added to the transcript or its token totals. Quiz generation and grading
retain their existing structured checks and are not rewritten by this loop.

Reflection is a model self-check, not independent factual verification. It adds
latency and can wrongly accept or reject an answer, especially with small models.
Adapters without structured-output support report review as unavailable.

## Test

```bash
python3 -m pytest
```
