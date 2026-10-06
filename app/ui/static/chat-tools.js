function renderExplanation(element, content) {
  // Only inert formatting survives; remote images and model-authored links do not.
  element.innerHTML = DOMPurify.sanitize(marked.parse(content), {
    ALLOWED_TAGS: ["p", "strong", "em", "code", "pre", "h1", "h2", "h3", "h4", "ul", "ol", "li", "blockquote", "table", "thead", "tbody", "tr", "th", "td", "br", "hr"],
    ALLOWED_ATTR: [],
  });
  element.classList.add("formatted");
}

function tokenNumber(value) {
  return Number.isInteger(value) ? value.toLocaleString() : "unavailable";
}

function updateTokenUsage() {
  const replies = conversationMessages.filter(m => m.role === "assistant");
  const tracked = replies.filter(m => Number.isInteger(m.usage?.input_tokens) && Number.isInteger(m.usage?.output_tokens));
  const total = tracked.reduce((sum, m) => sum + m.usage.input_tokens + m.usage.output_tokens, 0);
  $("#token-summary").textContent = tracked.length ? "Session tokens: " + total.toLocaleString() + " · " + tracked.length + "/" + replies.length + " replies tracked" : "Token usage: no recorded replies";
  const panel = $("#token-breakdown"); panel.replaceChildren();
  const latest = replies.at(-1)?.usage;
  if (latest?.context) {
    const c = latest.context, p = document.createElement("p");
    p.textContent = "Latest context estimate: " + tokenNumber(c.estimated_input_tokens) + " / " + tokenNumber(c.input_budget) + " input tokens · " + c.reply_reserved + " reserved for reply · " + c.material_passages + " passages · " + c.recent_messages + " recent messages · " + c.summarized_messages + " older messages summarized";
    panel.append(p);
  }
  for (const call of latest?.calls || []) {
    const p = document.createElement("p");
    p.textContent = call.stage + " · " + call.model + ": " + tokenNumber(call.input_tokens) + " in / " + tokenNumber(call.output_tokens) + " out";
    if (call.context) p.textContent += " · estimated context " + tokenNumber(call.context.estimated_input_tokens) + "/" + tokenNumber(call.context.input_budget) + " · reply reserve " + tokenNumber(call.context.reply_reserved);
    panel.append(p);
  }
  const note = document.createElement("p");
  note.textContent = "Actual Ollama counts for completed replies, including study planning and any earlier selection or verification calls. Inputs include history, notes and source passages. Session totals are cumulative work, not context-window occupancy. Failed requests and older untracked replies are excluded.";
  panel.append(note);
}

let transcriptMatches = [], transcriptMatch = -1;
function searchTranscript(step = 0) {
  const query = $("#chat-search").value.trim().toLowerCase();
  document.querySelectorAll("#messages article").forEach(article => article.classList.remove("search-match"));
  transcriptMatches = query ? [...document.querySelectorAll("#messages article:not(.pending)")].filter(a => a.dataset.content?.toLowerCase().includes(query)) : [];
  transcriptMatch = step ? (transcriptMatch + step + transcriptMatches.length) % transcriptMatches.length : 0;
  const active = transcriptMatches[transcriptMatch];
  if (active) { active.classList.add("search-match"); active.scrollIntoView({block: "nearest"}); }
  $("#search-count").textContent = query ? (active ? transcriptMatch + 1 : 0) + "/" + transcriptMatches.length : "";
  $("#search-prev").disabled = $("#search-next").disabled = !transcriptMatches.length;
}

function readBookmarks() {
  try {
    const items = JSON.parse(localStorage.getItem("study-buddy-bookmarks") || "[]");
    return Array.isArray(items) ? items.filter(item => typeof item.content === "string" && typeof item.title === "string") : [];
  } catch { return []; }
}
function writeBookmarks(items) {
  try { localStorage.setItem("study-buddy-bookmarks", JSON.stringify(items)); return true; }
  catch { $("#bookmark-status").textContent = $("#chat-error").textContent = "Bookmarks could not be saved. Browser storage may be full."; return false; }
}
function bookmarkKey(item) { return JSON.stringify([item.conversationId, item.question, item.content]); }
function addBookmarkButton(heading, item) {
  const button = document.createElement("button"); button.className = "bookmark-button";
  const key = bookmarkKey(item); button.dataset.bookmarkKey = key;
  button.onclick = () => {
    const items = readBookmarks(), existing = items.findIndex(saved => bookmarkKey(saved) === key);
    if (existing >= 0) items.splice(existing, 1);
    else items.push({...item, id: crypto.randomUUID(), title: item.question.slice(0, 100)});
    if (writeBookmarks(items)) syncBookmarkButtons();
  };
  heading.append(button); syncBookmarkButtons(button);
}
function syncBookmarkButtons(single = null) {
  const keys = new Set(readBookmarks().map(bookmarkKey));
  for (const button of single ? [single] : document.querySelectorAll(".bookmark-button")) {
    const saved = keys.has(button.dataset.bookmarkKey);
    button.textContent = saved ? "★" : "☆";
    button.title = saved ? "Remove saved concept" : "Save concept";
    button.setAttribute("aria-label", button.title); button.setAttribute("aria-pressed", String(saved));
  }
}
function renderBookmarks() {
  const list = $("#bookmark-list"); list.replaceChildren();
  const items = readBookmarks(); $("#bookmark-status").textContent = items.length ? "" : "No saved concepts yet.";
  for (const item of [...items].reverse()) {
    const section = document.createElement("section"), title = document.createElement("input"), details = document.createElement("details"), summary = document.createElement("summary"), body = document.createElement("div"), remove = document.createElement("button");
    title.value = item.title; title.maxLength = 100; title.setAttribute("aria-label", "Concept title");
    title.oninput = () => {
      const saved = readBookmarks(); const target = saved.find(s => s.id === item.id);
      if (target) {target.title = title.value.trim() || item.title; writeBookmarks(saved);}
    };
    summary.textContent = "Read concept"; renderExplanation(body, item.content); details.append(summary, body);
    for (const source of item.sources || []) {
      const p = document.createElement("p"); p.textContent = "[" + source.label + "] " + source.name + " · " + source.location + "\n" + source.text; details.append(p);
    }
    remove.textContent = "Remove";
    remove.onclick = () => { if (writeBookmarks(readBookmarks().filter(s => s.id !== item.id))) {renderBookmarks(); syncBookmarkButtons();} };
    section.append(title, details, remove); list.append(section);
  }
}
function initChatTools() {
  const searchToggle = $("#search-toggle");
  const searchPanel = $("#transcript-search");
  searchToggle.onclick = () => {
    const opening = searchPanel.hidden;
    searchPanel.hidden = !opening;
    searchToggle.setAttribute("aria-expanded", String(opening));
    if (opening) $("#chat-search").focus();
  };
  $("#chat-search").oninput = () => searchTranscript();
  $("#search-prev").onclick = () => searchTranscript(-1);
  $("#search-next").onclick = () => searchTranscript(1);
  $("#latest-message").onclick = () => {$("#messages").scrollTop = $("#messages").scrollHeight;};
  document.querySelectorAll("[data-prompt]").forEach(button => button.onclick = () => {
    if (!$("#message").value.trim()) {
      $("#message").value = button.dataset.prompt;
      $("#task-mode").value = button.dataset.task;
    }
    $("#message").focus();
  });
  searchTranscript(); updateTokenUsage();
}
