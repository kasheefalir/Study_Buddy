# Local AI Study Buddy

Study Buddy is a study app that helps you work through your own class materials
with an AI tutor called **Professor**. Bring your notes, slides, or textbook PDFs,
then ask questions, get explanations, or practice with a quiz. It opens in your
web browser, with a small interactive classroom as your starting point.

## What You Can Do

- **Study your own materials.** Add PDFs, Word documents, PowerPoint slides, text
  files, or a public webpage to your bookshelf.
- **Ask Professor for help.** Ask a specific question, request a simpler
  explanation, or ask for a summary. You can open the source passages used in a
  material-based answer to check them yourself.
- **Practice with quizzes.** Choose a quiz length or use the default of five
  questions. Answer one question at a time, read the feedback, and ask follow-up
  questions before moving on. Review your missed answers afterward.
- **Keep your study sessions organized.** Group materials by class or topic,
  return to saved conversations, and bookmark useful explanations.
- **Choose your AI model.** Switch between installed Llama 3.2, Phi-4 Mini, and
  GPT-OSS 20B models in the app. Larger models need more computer memory.

## Your First Study Session

Once the app is set up and running:

On your first visit, Professor offers a short guided tour. Use Next and Back to
explore, or Skip tour to start immediately. Completion is remembered in this
browser. Open the classroom menu and choose **Replay tutorial**
to see it again. The tour uses no AI model calls.

1. Click the classroom bookshelf to add your materials.
2. Select the materials you want to study in the current session.
3. Click Professor to open the chat. Try "Explain the main idea in these notes"
   or "Give me a five-question quiz."
4. During a quiz, select an answer and read the explanation. Choose **Next
   question** when ready, or ask about the question you just answered.

Quizzes prepare their questions and choices before they begin, so the initial
wait can take several minutes. After preparation, Next question opens a saved
question; answer explanations still take time to generate.

## Where Your Work Lives

With the local models described in this guide, AI responses are generated on
your computer through **Ollama**, the software that runs the AI models. Your
uploaded materials and study conversations are stored locally rather than in a
Study Buddy cloud account. Bookmarked explanations are saved in your browser.

Internet access is needed for installation, model downloads, and importing
webpages. Once everything is installed, you can study local files with local
models without an internet connection. There is no automatic sync between devices.

## Things to Know

Study Buddy is still being developed. Professor can misunderstand a question,
miss relevant information, or give an incorrect answer. Check important answers
against your materials; source links help you check, but are not a guarantee of
accuracy. A short quiz will not cover every page or concept in a textbook.

Text-based documents work best. Scanned PDFs and information contained only in
images or diagrams are not currently read. Speed depends on your computer and
the selected model. GPT-OSS 20B is a higher-memory option, not an option for an
8 GB computer; performance on 8 GB machines still needs testing for the smaller
models as well.

The sections below explain installation and provide technical details for people
who want to configure or contribute to the app.

## Setup

Choose **[Mac](#mac-first-time-setup)** or **[Windows](#windows-first-time-setup)**.
Each section includes everything: Python (runs the app), Ollama (runs the AI),
and Study Buddy itself. No coding experience is needed. This is a guided setup,
not yet a one-click installer. Linux does not yet have a tested beginner setup guide.

Keep internet connected and allow several gigabytes of free disk space; the
default AI model alone is about 2 GB. Installation can take several minutes.
Paste each numbered step's code into the specified terminal, press Enter, and
wait for it to finish. **Stop if a command fails.** Do not paste the next step
until the error is resolved. Installers may ask for permission or a password.
Use these download steps for a **new installation**, not to overwrite an existing
Study Buddy folder or its saved data.

### Mac: First-Time Setup

1. **Install Ollama's desktop app.** Open [Ollama for Mac](https://ollama.com/download/mac)
   and choose **Download manually** if the page shows a terminal command.
   Open the download, move Ollama to **Applications** if prompted, then open
   **Ollama** and finish its setup. Leave it running. You do not need to chat
   inside Ollama; Study Buddy will use it in the background.

2. **Install Python.** On [Python's Mac downloads page](https://www.python.org/downloads/macos/),
   choose a **Python 3.13** release and download its **macOS installer**.
   Open the installer and follow its steps. This avoids installing Homebrew.
   Skip this if `python3.13 --version` already works in Terminal.

3. **Download Study Buddy.** On [GitHub](https://github.com/kasheefalir/Study_Buddy),
   choose **Code > Download ZIP**. Double-click the ZIP and move the extracted
   **Study_Buddy-main** folder to your **Desktop**. Keep that folder there.
   If it already exists, do not replace it: see
   [Already Have Study Buddy Installed?](#already-have-study-buddy-installed).

4. **Set up and launch.** Open a new **Terminal** using Spotlight. Paste this
   whole block and press Enter. The `&&` joins stop it if a command fails.

```bash
cd "$HOME/Desktop/Study_Buddy-main" &&
python3.13 -m venv .venv &&
.venv/bin/python -m pip install -r requirements.txt &&
.venv/bin/python -m app.install_command &&
bash start-mac.command
```

5. Leave Terminal open. Wait for the server address, then open
   **http://127.0.0.1:8000** in your browser (or the address printed in Terminal).
   First startup downloads the default AI model if needed.
   Next time, open a fresh Terminal and type **`study buddy`** from any folder.

If you renamed the extracted folder, type `cd `, drag the folder from Finder
into Terminal, and press Enter instead of using the first line. Then run the
remaining commands. If you already have a compatible Python 3.11 or newer
installed under `python3`, you can use that in place of `python3.13`.

**Already use Git?** Instead of the ZIP download, run this in Terminal, then use
the setup commands above starting at `python3.13 -m venv .venv`:

```bash
cd "$HOME/Desktop" && git clone https://github.com/kasheefalir/Study_Buddy.git && cd Study_Buddy
```

### Windows: First-Time Setup

A bundled Windows installer is available as an unsigned preview. It removes the
separate Python setup and terminal steps. Download **StudyBuddy-Windows-Installer**
from the [successful Windows build](https://github.com/kasheefalir/Study_Buddy/actions/runs/39475990583),
extract the artifact ZIP, and run `StudyBuddy-Windows-Setup.exe`.
GitHub may require sign-in to download build artifacts. See
[Windows installer status and instructions](docs/windows-installer.md) for limitations.
The source-download instructions below remain available.

1. **Install Ollama's desktop app.** Open [Ollama for Windows](https://ollama.com/download/windows)
   and choose **Download manually** if the page shows a terminal command.
   Run the downloaded installer, then open **Ollama** from Start and finish
   its setup. Leave it running. You do not need to chat inside Ollama.

2. **Install Python.** Open **PowerShell** from Start and paste this command.
   Accept the installer prompts and wait for it to finish:

```powershell
winget install --id Python.Python.3.13 --exact --source winget
```

   **Prefer a download, or winget isn't available?** Visit
   [Python for Windows](https://www.python.org/downloads/windows/), choose a
   **Python 3.13** release, and run the Windows installer matching your computer.
   Enable **Add Python to PATH** when offered and keep the Python launcher enabled.
   Skip installation if `py -3.13 --version` already works.

3. **Download Study Buddy.** On [GitHub](https://github.com/kasheefalir/Study_Buddy),
   choose **Code > Download ZIP**. Right-click the ZIP, choose **Extract All**,
   and move the extracted **Study_Buddy-main** folder to your **Desktop**.
   Do not run the app from inside the ZIP or replace an existing project folder.

4. **Set up and launch.** Close your terminal application completely, then reopen
   **PowerShell** (not Command Prompt). Paste this whole block and press Enter.
   It finds your Desktop even if Windows stores it in OneDrive, and stops if a
   setup command fails.

```powershell
& {
    $ErrorActionPreference = "Stop"
    Set-Location (Join-Path ([Environment]::GetFolderPath("Desktop")) "Study_Buddy-main")
    py -3.13 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Python setup failed. Check Python installation." }
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Package installation failed." }
    .\.venv\Scripts\python.exe -m app.install_command
    if ($LASTEXITCODE -ne 0) { throw "Shortcut registration failed." }
    .\start-windows.bat
}
```

5. Leave PowerShell open. Wait for the server address, then open
   **http://127.0.0.1:8000** in your browser (or the address printed in PowerShell).
   First startup downloads the default AI model if needed.
   Next time, open a fresh terminal and type **`study buddy`** from any folder.
   If Windows still cannot find `study`, sign out and back in once.

If `py` is not found but `python --version` reports a compatible Python 3.11 or
newer, replace `py -3.13` with `python`. No PowerShell execution-policy changes
or environment activation are required.

**Already use Git?** Instead of downloading the ZIP, run these commands in
PowerShell, one at a time. Stop if any command fails:

```powershell
Set-Location ([Environment]::GetFolderPath("Desktop"))
git clone https://github.com/kasheefalir/Study_Buddy.git
```

Then use step 4, changing `"Study_Buddy-main"` to `"Study_Buddy"`.
Do not overwrite an existing project folder.

### Already Have Study Buddy Installed?

After updating your project files to this version, open a terminal in your
existing project folder. If the app already runs and its `.venv` environment
is present, you only need to register the command:

On Mac:

```bash
.venv/bin/python -m app.install_command
```

On Windows, in Command Prompt:

```bat
.venv\Scripts\python.exe -m app.install_command
```

Close and reopen your terminal application, then run `study buddy` from any
folder. Registration does not change your saved materials or conversations.
If `.venv` is missing, follow the first-time setup for your operating system.

### Open the App and Start Studying

1. Leave the terminal window open. The launcher starts Ollama if necessary,
   downloads the default model if missing, and loads Professor. A model download
   may sit at the download message without showing a percentage; it can take
   several minutes or longer.
2. Wait for `Professor is loaded` and then `Uvicorn running on
   http://127.0.0.1:8000`. The second message confirms the web server has started.
3. Open [Study Buddy](http://127.0.0.1:8000) in your browser. This address points
   to your own computer, not a public website. The browser may not open automatically.
4. Click the bookshelf, import a material, and wait until it is ready. The first
   PDF or webpage import may also download a smaller search model,
   `nomic-embed-text`. Then click Professor and ask a question or start a quiz.

You only need the default model to begin. The Professor model selector discovers
chat-capable models registered in Ollama and refreshes automatically. Embedding-only
models and unavailable retired entries are excluded. Missing recommended models
have a **Download** button with an approximate size; progress appears in the menu,
and you can retry a failed download. The menu downloads additional models only
when you click.
Cloud recommendations have a **Set up** button instead; they still require
internet and Ollama account access, and send chat and relevant excerpts to the cloud.
Other discovered models can be selected, but have not all been tested with Study
Buddy's general workflow. GPT-OSS 20B needs substantially more memory and is not
intended for an 8 GB computer.

### Reopen or Stop Study Buddy

After the first setup, open a terminal and type `study buddy` from any folder.
You do not need to activate Python, reinstall packages, or navigate to the
project folder. Open the same browser address after the server starts.

Keep the project folder in place: the command remembers its location and Python
environment. If you move or rename the folder, recreate `.venv`, install the
packages, and repeat command registration from the new location. Do not delete
the `data` folder, which holds your materials and conversations. Each computer
needs its own initial setup; downloading a ZIP alone does not install the command.

The original launchers remain available as a fallback: run
`bash start-mac.command` on Mac or `start-windows.bat` in Windows Command Prompt
from the project folder. On Windows you can also double-click the batch file;
use Command Prompt if its window closes before you can read an error.

To stop the app, click its terminal window and press **Ctrl+C** (Control+C on
Mac, not Command+C). Closing the browser tab does not stop the server. The
launcher stops any Ollama service it started; an already-running Ollama service
is left running. Saved materials and conversations remain in the project folder.
The model stays loaded for up to 30 minutes after startup or the latest chat
request, and loads again when needed.

### Troubleshooting

| What you see | What to try |
| --- | --- |
| `python3`, `python`, or `py` is not found, or Windows opens the Store | Finish installing Python, then close and reopen the terminal. On Windows, try `py --version`; if that works, use `py -m venv .venv`. Otherwise check the installer's command/PATH options. |
| `requirements.txt` or a start script cannot be found | Your terminal is in the wrong folder. Return to the extracted project folder containing those files using the Mac or Windows steps above. |
| `Missing app dependencies` or `No module named ...` | From the project folder, rerun `.venv/bin/python -m pip install -r requirements.txt` on Mac, or `.venv\Scripts\python.exe -m pip install -r requirements.txt` on Windows. If `.venv` is missing, first repeat the environment-creation step. |
| Ollama is missing, not running, or cannot be reached | Install and open the Ollama application, then restart Study Buddy. Installing a Python package called `ollama` is not a substitute. |
| `study` is not found | Complete command registration, then quit and reopen your terminal application. On Windows, sign out and back in if needed. The original start scripts still work from the project folder. |
| Registration says another `study` command exists | The installer will not replace another program. Use the original start script, or resolve that command conflict before repeating registration. Existing shell aliases/functions can also take precedence; the installer does not remove them. |
| `study buddy` cannot find the project or Python | If you moved the project, repeat setup and registration in the new folder. Keep the project and its `.venv` environment together. |
| The download fails | Check your internet connection and free disk space, then restart the launcher. Model downloads need internet even though later local-file study can work offline. |
| The browser says it cannot connect | Keep the terminal open and wait for `Uvicorn running`. Use the exact address printed there. If the terminal shows an error, fix that error first. |
| Mac says `Permission denied` for the start script | From the project folder, run `chmod +x start-mac.command`, then `./start-mac.command`. If macOS shows a security warning instead, verify the download source; do not disable system security protections. |
| Replies or quiz preparation are slow | Wait for the progress message to finish, close unneeded memory-heavy apps, and use a smaller installed model. Preparing a whole quiz can take several minutes. |

**Port already in use:** another app or another Study Buddy instance is using
the address. If Study Buddy is already running, use its existing browser page.
Otherwise, choose another port without stopping an unrelated program.

On Mac, after command registration, from any folder:

```bash
BUDDY_PORT=8001 study buddy
```

On Windows, from Command Prompt:

```bat
set BUDDY_PORT=8001
study buddy
```

Then open [Study Buddy on port 8001](http://127.0.0.1:8001). Use the same port
on later launches to keep access to that browser's saved bookmarks.

If you need help, share the exact error text and whether you are on Mac or
Windows. Remove personal information before sharing logs or screenshots.
These steps match the launch scripts; they are not a claim that a fresh install
has been tested on every Mac and Windows configuration.

### Existing Development Mac Shortcut

The original development Mac already has a shell function named `study`, so
`study buddy` continues to work there unchanged. The new registration step gives
other computers the same command without copying that device-specific function.
Registration does not remove existing aliases or functions. If replacing the old
shortcut, remove its source line from your shell configuration yourself after
registering the new command.

## Technical Reference

The sections below are optional for everyday use. Developers can also open
interactive API documentation at [localhost /docs](http://127.0.0.1:8000/docs)
while the app is running (adjust the port if needed).

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
For material-backed chat answers, Professor links explanations to source labels.
When the model resolves a request as requiring source evidence, that requirement
survives retrieval planning. An empty retrieval gets one model-directed retry;
if no passages reach the writer, the app reports the retrieval gap instead of
answering from memory. Follow-up evidence checks receive the resolved question.
The optional general reflection pass does not rewrite source-checked answers.
The existing intent decision can reuse prior original passages for a follow-up;
reuse is allowed only if their text still matches the currently selected files.
The source writer receives a compact question/evidence packet, not the transcript
or session summaries. Its existing retry now receives rejected claims and specific
feedback, retaining supported points and identifying partial answers when needed.
This replaces the generic regeneration step; it does not add another review loop.
The app validates the labels and supplies the actual passage text to a focused
model check that attempts to remove unsupported explanations. If none pass, the answer
acknowledges the evidence gap. Invalid structured answers get one retry.
This checks up to four points sequentially per draft, with at most one repaired
draft (ten model calls total for writing and verification). It reduces unsupported
additions; it does not guarantee that the model interprets every passage correctly.
Each check sees just one point and its cited evidence, deduplicated within that
check. Duplicate or missing verdicts fail validation. See
`docs/grounding-evaluation.md` for observed limitations and the opt-in live test;
passing mocked unit tests is not evidence of model-level answer accuracy.
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
windows by matching terms. Before the first question is displayed, the app prepares
and saves the question set, including choices, answer keys and source passages.
Preparation uses sequential, bounded model calls rather than one full-book prompt.
The Next question button loads the next saved question without a model call;
answer explanations still use the model. Existing quizzes prepare their remaining
questions on advancement. No ever-growing book summary is sent back to the model.
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
`OLLAMA_THINK=true` or `false` explicitly controls thinking for models that support
that setting; leave it unset to use the model default. Check Ollama's `/api/show`
thinking metadata before disabling it: thinking-only variants do not support
`false`. Reasoning consumes output tokens, so these models may need a larger
`RESPONSE_TOKENS` budget and can be substantially slower in the multi-call workflow.

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
