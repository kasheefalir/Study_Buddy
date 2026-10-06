const $ = (selector) => document.querySelector(selector);
const canvas = $("#classroom-canvas");
const ctx = canvas.getContext("2d");
ctx.imageSmoothingEnabled = false;
const tiles = new Image();
const port = location.port || (location.protocol === "https:" ? "443" : "80");
$("#room-number").textContent = "ROOM " + port;
const professor = new StudentSprite("/static/characters/professor.png");
professor.ready.catch(() => { $("#status").textContent = "Professor artwork could not load"; });
let selectedStudent = StudentCharacters.find((character) => character.id === localStorage.getItem("study-buddy-student")) || StudentCharacters[0];
let student = new StudentSprite("/static/characters/" + selectedStudent.file + ".png");
let selectionVersion = 0;
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
const life = new ClassroomLife({room: $(".room"), selectedId: selectedStudent.id, open: openDialog, name: localStorage.getItem("study-buddy-name") || ""});
$("#student-name-input").value = life.name;
$("#student-name-form").onsubmit = event => {
  event.preventDefault();
  life.name = $("#student-name-input").value.trim().slice(0, 24);
  localStorage.setItem("study-buddy-name", life.name);
  $("#character-status").textContent = life.name ? "Welcome, " + life.name + "." : "Name cleared.";
};
window.addEventListener("study-material-facts", event => life.setFacts(event.detail || {}));
function updateStudentPicker() {
  document.querySelectorAll("[data-student]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.student === selectedStudent.id));
  });
  $("#character-status").textContent = selectedStudent.name + " is your classroom student.";
}
for (const character of StudentCharacters) {
  const button = document.createElement("button");
  button.dataset.student = character.id;
  button.setAttribute("aria-label", "Choose " + character.name);
  const portrait = document.createElement("canvas");
  portrait.width = 32; portrait.height = 32; portrait.setAttribute("aria-hidden", "true");
  const label = document.createElement("span"); label.textContent = character.name;
  button.append(portrait, label); $("#character-options").append(button);
  const candidate = new StudentSprite("/static/characters/" + character.file + ".png");
  candidate.ready.then(() => candidate.draw(portrait.getContext("2d"), 0, 0)).catch(() => {button.disabled = true;});
  button.onclick = async () => {
    const version = ++selectionVersion;
    try {
      await candidate.ready;
      if (version !== selectionVersion) return;
      student = candidate; selectedStudent = character;
      localStorage.setItem("study-buddy-student", character.id);
      updateStudentPicker();
      life.setClassmates(character.id);
      if (tiles.complete && tiles.naturalWidth) drawRoom();
    } catch { $("#character-status").textContent = "This student could not load. Please try again."; }
  };
}
updateStudentPicker();
let conversationId = localStorage.getItem("study-buddy-conversation");
let busy = false;
let deviceVoice;
let conversationMessages = [];
let selectedMaterial = "";
let selectedMaterials = [];
let materialOperations = 0;
let batchSaving = false;
let sessionCreation = null;
let generalChatOnly = false;
let factsVersion = 0;
async function selectMaterial(id, name = "Selected study material") {
  selectedMaterial = id;
  if (id) generalChatOnly = false;
  $("#grounding-status").textContent = id ? "Studying: " + name : "General conversation";
  $("#clear-material").hidden = !id;
  const version = ++factsVersion;
  const ids = [...selectedMaterials];
  life.setFacts({documentId: id, documentIds: ids, facts: []});
  if (id) {
    try {
      const batches = [];
      for (const materialId of ids) {
        try { batches.push((await request("/api/materials/" + materialId + "/facts")).facts || []); }
        catch { /* Keep other ready materials available. */ }
      }
      // Interleave documents so the two classmates can represent different materials.
      const facts = [0, 1].flatMap(index => batches.map(batch => batch[index]).filter(Boolean));
      if (version === factsVersion) life.setFacts({documentId: id, documentIds: ids, facts});
    } catch { /* A removed material must not leave stale classmate facts. */ }
  }
}
async function ensureSession() {
  if (conversationId) return;
  if (!sessionCreation) sessionCreation = request("/api/conversations", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({title: "Study session", document_ids: []})}).then(data => {
    conversationId = data.conversation_id; localStorage.setItem("study-buddy-conversation", conversationId);
  }).finally(() => {sessionCreation = null;});
  await sessionCreation;
}
async function setBatch(ids, persist = true) {
  if (batchSaving) throw new Error("The session batch is still being saved. Please try again.");
  batchSaving = true;
  try {
  if (persist) {
    await ensureSession();
    const result = await request("/api/conversations/" + conversationId + "/materials", {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify({document_ids: ids})});
    $("#active-session-title").textContent = result.title || "Study session";
  }
  selectedMaterials = [...ids];
  await selectMaterial(ids[0] || "");
  $("#grounding-status").textContent = ids.length ? "Session batch: " + ids.length + " material" + (ids.length === 1 ? "" : "s") : "No materials in this session";
  $("#batch-count").textContent = ids.length + " selected for this session";
  } finally {batchSaving = false;}
}
$("#clear-material").onclick = async () => {if (!busy && !materialOperations) {try {await setBatch([]);} catch(error) {$("#chat-error").textContent = error.message;}}};
async function ensureStudyMaterial() {
  if (materialOperations) throw new Error("Wait for material preparation to finish.");
  if (!selectedMaterials.length) return;
  const items = await request("/api/materials");
  for (const id of selectedMaterials) {
    if (!items.some(item => item.id === id && item.status === "Ready")) throw new Error("A session material is missing or not ready. Check Materials.");
  }
}
const studyDesk = {x: 112, y: 214, w: 32, h: 32};
const boardBounds = {x: 64, y: 30, w: 96, h: 27};
const shelfBounds = {x: 226, y: 44, w: 32, h: 40};
// Hotspots use the same logical coordinates as the canvas furniture.
for (const [selector, bounds] of [[".desk", studyDesk], [".board", boardBounds], [".shelf", shelfBounds]]) {
  Object.assign($(selector).style, {
    left: bounds.x / canvas.width * 100 + "%",
    top: bounds.y / canvas.height * 100 + "%",
    width: bounds.w / canvas.width * 100 + "%",
    height: bounds.h / canvas.height * 100 + "%",
  });
}
const sprite = (x, y, w, h, dx, dy) => ctx.drawImage(tiles, x, y, w, h, dx, dy, w, h);

function chalkLine(text, x, y) {
  let line = text.replace(/\s+/g, " ").trim();
  if (ctx.measureText(line).width > 80) {
    while (line && ctx.measureText(line + "...").width > 80) line = line.slice(0, -1);
    line += "...";
  }
  ctx.fillText(line, x, y);
}

function updateContext() {
  const questions = conversationMessages.filter((message) => message.role === "user");
  const answer = conversationMessages.filter((message) => message.role === "assistant").at(-1);
  $("#context-topic").textContent = questions[0]?.content || "A fresh chalkboard.";
  $("#context-question").textContent = questions.at(-1)?.content || "Ask Professor a question to begin.";
  $("#context-answer").textContent = answer?.content || "No explanation yet.";
  $(".board").setAttribute("aria-label", questions.length
    ? "View conversation context: " + questions.at(-1).content
    : "View current conversation context");
  if (tiles.complete && tiles.naturalWidth) drawRoom();
}

function drawRoom() {
  ctx.clearRect(0, 0, 320, 288);
  // All furniture remains at its original scale. The canvas scales the whole room.
  ctx.fillStyle = "#56665325"; ctx.fillRect(20, 24, 286, 255);
  ctx.save();
  ctx.beginPath(); ctx.moveTo(16, 16); ctx.lineTo(224, 16); ctx.lineTo(224, 32); ctx.lineTo(288, 32); ctx.lineTo(288, 96); ctx.lineTo(304, 96); ctx.lineTo(304, 120); ctx.lineTo(288, 120); ctx.lineTo(288, 140); ctx.lineTo(264, 140); ctx.lineTo(264, 160); ctx.lineTo(304, 160); ctx.lineTo(304, 272); ctx.lineTo(16, 272); ctx.closePath();
  ctx.fillStyle = "#a76f56"; ctx.fill(); ctx.clip();
  for (let y = 16; y < 272; y += 16) for (let x = 16; x < 304; x += 16) sprite(48, 0, 16, 16, x, y);
  // Repeating wall panels and their timber skirting.
  for (let x = 16; x < 224; x += 64) sprite(0, 16, 64, 48, x, 16);
  sprite(128, 16, 64, 48, 224, 32);
  sprite(128, 16, 64, 48, 264, 160);
  ctx.restore();
  ctx.strokeStyle = "#83544f"; ctx.lineWidth = 3; ctx.stroke();
  // Chalkboard assembled from its frame tile and extended writing surface.
  ctx.fillStyle = "#704e58"; ctx.fillRect(64, 30, 96, 27);
  ctx.fillStyle = "#b88164"; ctx.fillRect(66, 32, 92, 23);
  ctx.fillStyle = "#3f4355"; ctx.fillRect(68, 33, 88, 21);
  ctx.fillStyle = "#596779"; ctx.fillRect(69, 34, 85, 17);
  ctx.fillStyle = "#c8d7bf"; ctx.font = "5px monospace";
  const questions = conversationMessages.filter((message) => message.role === "user");
  chalkLine(questions[0]?.content || "OUR CONVERSATION", 72, 41);
  chalkLine(questions.at(-1)?.content || "A fresh chalkboard", 72, 48);
  sprite(384, 216, shelfBounds.w, shelfBounds.h, shelfBounds.x, shelfBounds.y);
  sprite(288, 56, 32, 24, 258, 40);
  // Wall clock.
  ctx.fillStyle = "#5f5e69"; ctx.fillRect(109, 18, 10, 10);
  ctx.fillStyle = "#f7efd6"; ctx.fillRect(111, 19, 6, 8);
  ctx.fillStyle = "#5f5e69"; ctx.fillRect(114, 20, 1, 4); ctx.fillRect(114, 23, 3, 1);
  const furnishings = [
    {y: 119, draw: () => sprite(240, 144, 48, 32, 26, 87)},
    {y: 119, draw: () => {sprite(192, 80, 32, 32, 79, 87); sprite(616, 128, 16, 32, 87, 68);}},
    {y: 94, draw: () => sprite(752, 96, 16, 32, 208, 62)},
  ];
  // Six desks and chairs, using individual sprite bounds rather than atlas blocks.
  for (const y of [150, studyDesk.y]) for (const x of [32, studyDesk.x, 192]) {
    furnishings.push({y: y + 48, draw: () => {
    sprite(192, 112, 32, 32, x, y);
    sprite(192, 96, 32, 16, x, y + 27);
    ctx.fillStyle = "#6a5764"; ctx.fillRect(x + 6, y + 39, 2, 9); ctx.fillRect(x + 23, y + 39, 2, 9);
    ctx.fillStyle = "#b77c65"; ctx.fillRect(x + 7, y + 35, 17, 5);
    }});
  }
  furnishings.push(
    {y: 224, draw: () => {sprite(48, 176, 16, 32, 272, 192); sprite(64, 176, 16, 32, 288, 192);}},
    {y: 269, draw: () => sprite(96, 272, 48, 32, 252, 237)},
    {y: 148, draw: () => sprite(752, 96, 16, 32, 242, 116)},
    {y: 123, draw: () => professor.draw(ctx, 135, 93, {time: reducedMotion.matches ? 0 : performance.now()})},
    ...life.actors(ctx, student, performance.now(), reducedMotion.matches),
  );
  furnishings.sort((a, b) => a.y - b.y).forEach(item => item.draw());
}
student.ready.then(() => {
  if (tiles.complete && tiles.naturalWidth) drawRoom();
}).catch(() => { $("#status").textContent = "Student artwork could not load"; });
function animateClassroom(now) {
  life.update(now, reducedMotion.matches);
  if (!document.hidden && tiles.complete && tiles.naturalWidth) drawRoom();
  requestAnimationFrame(animateClassroom);
}
requestAnimationFrame(animateClassroom);
tiles.onload = drawRoom;
tiles.onerror = () => { $("#status").textContent = "Classroom artwork could not load"; };
tiles.src = "/tileset/tilest.png";

function openDialog(id) {
  life.pause();
  document.querySelectorAll("dialog[open]").forEach((dialog) => dialog.close());
  $("#" + id).showModal();
  if (id === "materials") loadMaterials();
  if (id === "sessions") loadSessions();
  if (id === "bookmarks") renderBookmarks();
  if (id === "room-menu") refreshProfessorStatus();
  if (id === "chat") $("#message").focus();
}
document.querySelectorAll("[data-open]").forEach((button) => button.addEventListener("click", () => openDialog(button.dataset.open)));
document.querySelectorAll(".session-actions [data-open]").forEach((button) => button.addEventListener("click", () => button.closest("details")?.removeAttribute("open")));
document.querySelectorAll(".close").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));

async function request(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === "string" ? error.detail : "Something went wrong. Please try again.");
  }
  return response.status === 204 ? null : response.json();
}
function addMessage(role, content, sources = [], usage = null, question = "", quizQuestion = null) {
  const article = document.createElement("article");
  article.className = role;
  article.dataset.content = content;
  const heading = document.createElement("div"), body = document.createElement("div");
  heading.className = "message-heading"; heading.textContent = role === "user" ? life.name || "You" : "Professor";
  body.className = "message-body";
  if (role === "assistant") renderExplanation(body, quizQuestion?.id ? "**Question " + quizQuestion.number + " of " + quizQuestion.total + "**\n\n" + quizQuestion.question : content);
  else body.textContent = content;
  article.append(heading, body);
  if (quizQuestion?.id) {
    article.dataset.quizId = quizQuestion.id;
    renderQuizChoices(article, quizQuestion);
  }
  if (role === "assistant" && question) addBookmarkButton(heading, {content, sources, question, conversationId});
  if (usage?.calls?.length) {
    const counts = document.createElement("small");
    counts.textContent = "Input " + tokenNumber(usage.input_tokens) + " · Output " + tokenNumber(usage.output_tokens) + " tokens";
    article.append(counts);
  }
  if (sources.length) {
    const details = document.createElement("details"), summary = document.createElement("summary");
    details.className = "source-passages"; summary.textContent = "Source passages (" + sources.length + ")"; details.append(summary);
    sources.forEach(source => {
      const p = document.createElement("p");
      p.textContent = "[" + source.label + "] " + source.name + " · " + source.location + "\n" + source.text;
      if (Number.isInteger(source.page) && /^[a-f0-9]{32}$/.test(source.document_id)) {
        const link = document.createElement("a"); link.textContent = "Open page " + source.page;
        link.href = "/api/materials/" + source.document_id + "/view#page=" + source.page;
        link.target = "_blank"; link.rel = "noopener noreferrer";
        p.append(document.createElement("br"), link);
      }
      details.append(p);
    });
    article.append(details);
  }
  $("#messages").append(article); $("#messages").scrollTop = $("#messages").scrollHeight;
  return article;
}
function renderQuizChoices(article, question, currentId = question.id) {
  article.querySelector(".quiz-choices")?.remove();
  const group = document.createElement("div");
  group.className = "quiz-choices"; group.setAttribute("role", "group");
  group.setAttribute("aria-label", "Answer choices");
  question.options.forEach((text, index) => {
    const button = document.createElement("button"), letter = document.createElement("span"), label = document.createElement("span");
    button.type = "button"; button.className = "quiz-choice";
    letter.className = "choice-letter"; letter.textContent = String.fromCharCode(65 + index);
    label.textContent = text; button.append(letter, label);
    button.disabled = question.answered || question.id !== currentId;
    if (question.answered && index === question.selected_index) {
      const selectedCorrectly = question.verdict === "correct";
      button.classList.add(selectedCorrectly ? "selected-correct" : "selected-incorrect");
      label.textContent += selectedCorrectly ? " (Your answer: correct)" : " (Your answer: incorrect)";
    }
    if (question.answered && index === question.correct_index && index !== question.selected_index) {
      button.classList.add("correct-answer"); label.textContent += " (Correct answer)";
    }
    button.onclick = async () => {
      if (busy || materialOperations || batchSaving) return;
      const answer = String.fromCharCode(65 + index);
      button.classList.add("selected-pending");
      label.textContent += " (Selected)";
      group.querySelectorAll("button").forEach(choice => { choice.disabled = true; });
      const delivered = await sendChatMessage(answer, null, "auto", question.id);
      if (!delivered) renderQuizChoices(article, question, currentId);
    };
    group.append(button);
  });
  article.querySelector(".message-body").append(group);
}
function updateQuizChoices(current) {
  document.querySelectorAll("#messages [data-quiz-id]").forEach(article => {
    const saved = conversationMessages.find(m => m.quiz_question?.id === article.dataset.quizId)?.quiz_question;
    const question = current?.id === article.dataset.quizId ? current : saved;
    if (question) renderQuizChoices(article, question, current?.id || "");
  });
  updateQuizActions(current);
}
function updateQuizActions(question) {
  const reviewReady = Boolean(question?.answered);
  $("#next-question").hidden = !reviewReady;
  $("#ask-question").hidden = !reviewReady;
  $("#message").placeholder = reviewReady ? "Ask about this question…" : "Ask a question…";
}
$("#ask-question").onclick = () => { $("#message").focus(); };
async function restoreChat() {
  if (!conversationId) return;
  busy = true; $("#chat-form button").disabled = true;
  const restoringId = conversationId;
  try {
    const data = await request("/api/conversations/" + encodeURIComponent(conversationId));
    if (conversationId !== restoringId) return;
    conversationMessages = data.messages;
    $("#active-session-title").textContent = data.title || "Study session";
    await setBatch(data.document_ids || (data.document_id ? [data.document_id] : []), false);
    updateContext();
    $("#messages").replaceChildren();
    data.messages.forEach((m, i) => {
      if (!m.quiz_selection_for) addMessage(m.role, m.content, m.sources || [], m.usage, data.messages[i - 1]?.content || "", m.quiz_question);
    });
    updateQuizChoices(data.quiz?.current_question);
    updateTokenUsage(); searchTranscript();
  } catch { $("#chat-error").textContent = "Previous conversation could not be loaded."; }
  finally { busy = false; $("#chat-form button").disabled = false; }
}
$("#chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = $("#message").value.trim();
  if (!message || busy || materialOperations || batchSaving) return;
  const outgoing = addMessage("user", message);
  $("#message").value = "";
  const task = $("#task-mode").value;
  $("#task-mode").value = "auto";
  await sendChatMessage(message, outgoing, task);
});
async function sendChatMessage(message, outgoing, task = "auto", quizQuestionId = null) {
  if (busy) return;
  busy = true; $("#chat-form button").disabled = true; $("#new-chat").disabled = true;
  outgoing?.querySelector(".retry")?.remove();
  outgoing?.classList.remove("failed");
  const quizRequest = task === "quiz" || /\b(quiz me|test me|next question)\b/i.test(message);
  const pending = addMessage("assistant", quizRequest ? "Professor is preparing your quiz response…" : selectedMaterials.length ? "Professor is reviewing relevant passages…" : "Professor is thinking…"); pending.classList.add("pending");
  pending.querySelector(".message-heading").prepend(makeStudyLoader());
  $("#chat-error").textContent = "";
  let activityTimer;
  try {
    await ensureStudyMaterial();
    await ensureSession();
    const progressSession = conversationId;
    activityTimer = setInterval(async () => {
      try {
        const progress = await request("/api/conversations/" + encodeURIComponent(progressSession) + "/activity");
        if (pending.isConnected && progress.active) {
          const content = pending.querySelector(".message-body");
          if (content) content.textContent = progress.stage + "…";
        }
      } catch { /* The chat request reports actionable failures. */ }
    }, 700);
    const data = await request("/api/chat", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({message, conversation_id: conversationId, document_ids: selectedMaterials, task, quiz_question_id: quizQuestionId})});
    pending.remove();
    conversationId = data.conversation_id; localStorage.setItem("study-buddy-conversation", conversationId);
    addMessage("assistant", data.message, data.sources || [], data.usage, message, data.quiz_question);
    conversationMessages.push({role: "user", content: message, ...(quizQuestionId ? {quiz_selection_for: quizQuestionId} : {})},
      {role: "assistant", content: data.message, sources: data.sources || [], usage: data.usage, quiz_question: data.quiz_question});
    if (data.quiz_current?.answered) conversationMessages.forEach(m => {
      if (m.quiz_question?.id === data.quiz_current.id) m.quiz_question = data.quiz_current;
    });
    updateQuizChoices(data.quiz_current);
    updateContext();
    updateTokenUsage(); searchTranscript();
    if ($("#read-aloud").checked && deviceVoice) {
      const utterance = new SpeechSynthesisUtterance(data.message);
      utterance.voice = deviceVoice; speechSynthesis.speak(utterance);
    }
    return true;
  } catch (error) {
    pending.remove(); outgoing?.classList.add("failed");
    $("#chat-error").textContent = error.message;
    if (!outgoing) return false;
    const retry = document.createElement("button"); retry.className = "retry"; retry.textContent = "Not delivered · Retry";
    const originalSession = conversationId, originalMaterial = JSON.stringify(selectedMaterials);
    retry.onclick = () => {
      if (busy) return;
      if (originalSession !== conversationId || originalMaterial !== JSON.stringify(selectedMaterials)) {
        $("#chat-error").textContent = "The study context changed. Send this question again in the current session."; return;
      }
      outgoing.remove(); $("#messages").append(outgoing);
      sendChatMessage(message, outgoing, task, quizQuestionId);
    };
    outgoing.append(retry);
    return false;
  }
  finally { clearInterval(activityTimer); busy = false; $("#chat-form button").disabled = false; $("#new-chat").disabled = false; refreshProfessorStatus(); }
}
$("#message").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("#chat-form").requestSubmit(); }
});
$("#new-chat").onclick = async () => {
  if (busy || materialOperations || batchSaving || sessionCreation) return;
  $("#task-mode").value = "auto";
  conversationId = null; localStorage.removeItem("study-buddy-conversation");
  conversationMessages = []; updateContext();
  $("#active-session-title").textContent = "New study session";
  await setBatch([], false);
  $("#messages").replaceChildren(); addMessage("assistant", "A fresh page. What would you like to work on?");
  updateQuizActions({});
  $("#chat-error").textContent = ""; $("#chat-search").value = ""; updateTokenUsage(); searchTranscript();
};

let materialSnapshot = "";
let materialRefreshing = false;
function materialProgress(item) {
  const labels = {extracting: "Reading and extracting text", indexing: "Building searchable passages", embedding: "Preparing meaning-based search (first use may download a model)", facts: "Text is searchable · preparing classmate facts", ready: "Ready for Professor", interrupted: "Import interrupted · retry Import", failed: "Import failed · retry Import", stored: "Saved · waiting for import"};
  const group = document.createElement("div"); group.className = "material-progress";
  group.setAttribute("role", "status");
  if (item.importing) group.append(makeStudyLoader());
  const text = document.createElement("span"); text.textContent = labels[item.import_stage] || item.status;
  group.append(text);
  if (item.importing) {
    const meter = document.createElement("progress"); meter.setAttribute("aria-label", text.textContent);
    if (["extracting", "embedding"].includes(item.import_stage) && item.import_total > 0) {
      meter.max = item.import_total; meter.value = item.import_completed || 0;
      text.textContent += " · " + meter.value + "/" + meter.max + (item.import_stage === "extracting" ? " pages" : " passages");
    }
    group.append(meter);
  }
  return group;
}
async function loadMaterials(onlyChanged = false) {
  if (onlyChanged && materialRefreshing) return;
  materialRefreshing = true;
  try {
    await ensureSession();
    const items = await request("/api/materials");
    const snapshot = JSON.stringify([items, selectedMaterials, busy, materialOperations]);
    if (onlyChanged && snapshot === materialSnapshot) return;
    materialSnapshot = snapshot;
    if (life.documentId && !items.some(item => item.id === life.documentId)) life.setFacts({documentId: null, facts: []});
    $("#material-list").replaceChildren();
    $("#material-status").textContent = items.length ? items.length + " materials in your library" : "Your shelf is ready for its first book.";
    $("#batch-count").textContent = selectedMaterials.length + " selected for this session";
    items.forEach((item) => {
      const li = document.createElement("li"), info = document.createElement("div"), link = document.createElement("a"), status = document.createElement("small"), remove = document.createElement("button");
      li.dataset.materialId = item.id;
      link.textContent = item.name; link.href = item.url || "/api/materials/" + item.id + "/download";
      if (item.url) { link.target = "_blank"; link.rel = "noopener noreferrer"; }
      status.textContent = [item.status === "Ready" ? item.chunk_count + " searchable passages" : "", item.error, item.warning].filter(Boolean).join(" · "); info.append(link, materialProgress(item), status);
      const actions = document.createElement("div"); actions.className = "material-actions";
      if (item.status === "Ready") {
        const prep = item.overview || {status: "not_started"};
        const preparing = ["queued", "preparing"].includes(prep.status);
        const overviewStatus = document.createElement("div"); overviewStatus.className = "material-progress";
        const overviewLabel = document.createElement("span");
        overviewLabel.textContent = prep.status === "ready" ? "Study overview ready" : preparing ? "Preparing study overview" : "Ready to search · Study overview " + (prep.status === "paused" ? "paused" : "not prepared");
        if (preparing) {
          overviewStatus.append(makeStudyLoader());
          const meter = document.createElement("progress"); meter.setAttribute("aria-label", "Study overview preparation");
          if (prep.total) {meter.max = prep.total; meter.value = prep.completed; overviewLabel.textContent += " · " + prep.completed + "/" + prep.total + " sections and summaries";}
          overviewStatus.append(meter);
        }
        overviewStatus.append(overviewLabel); info.append(overviewStatus);
        if (prep.error) {const error = document.createElement("small"); error.textContent = prep.error; info.append(error);}
        if (prep.status !== "ready") {
          const prepare = document.createElement("button"); prepare.textContent = preparing ? "Pause overview" : prep.status === "paused" ? "Resume overview" : "Prepare study overview";
          prepare.disabled = !!materialOperations;
          prepare.onclick = async () => {
            prepare.disabled = true;
            try {await request("/api/materials/" + item.id + "/overview" + (preparing ? "/pause" : ""), {method: "POST"}); await loadMaterials();}
            catch(error) {$("#material-status").textContent = error.message; prepare.disabled = false;}
          };
          actions.append(prepare);
        }
        const study = document.createElement("input"); study.type = "checkbox"; study.checked = selectedMaterials.includes(item.id);
        study.setAttribute("aria-label", "Include " + item.name + " in this session");
        study.disabled = busy || !!materialOperations || item.importing;
        study.onchange = async () => {
          study.disabled = true;
          try {await setBatch(study.checked ? [...selectedMaterials, item.id] : selectedMaterials.filter(id => id !== item.id));}
          catch(error) {study.checked = !study.checked; $("#material-status").textContent = error.message;}
          finally {study.disabled = false;}
        };
        const label = document.createElement("label"); label.append(study, " In this session"); actions.append(label);
      }
      if (item.extraction_saved) {
        const extracted = document.createElement("a"); extracted.textContent = "Extracted text";
        extracted.href = "/api/materials/" + item.id + "/extraction"; actions.append(extracted);
        if (typeof item.clean_extraction === "boolean") {
          for (const [view, title] of [["clean", "Article text"], ["full", "Full page text"]]) {
            const source = document.createElement("a"); source.textContent = title;
            source.href = "/api/materials/" + item.id + "/extraction?view=" + view; actions.append(source);
          }
        }
      }
      if (["pdf", "pptx", "docx", "txt", "md", "url"].includes(item.kind)) {
        const process = document.createElement("button"); process.textContent = item.status === "Ready" ? "Reimport" : "Import";
        process.disabled = busy || !!materialOperations || item.importing;
        process.onclick = async () => {if (busy || materialOperations) return; process.disabled = true; try {await importMaterial(item); await loadMaterials();} catch(error) {$("#material-status").textContent = error.message;} finally {process.disabled = false;}};
        actions.append(process);
      }
      if (item.kind === "url" && item.snapshot_saved) {
        const raw = document.createElement("a"); raw.textContent = "Original page";
        raw.href = "/api/materials/" + item.id + "/snapshot"; actions.append(raw);
      }
      info.append(actions);
      remove.textContent = "×"; remove.className = "icon"; remove.setAttribute("aria-label", "Remove " + item.name);
      remove.disabled = !!materialOperations || item.importing;
      remove.onclick = async () => {
        if (busy || materialOperations) return;
        if (!confirm("Remove " + item.name + " from this device?")) return;
        try { await request("/api/materials/" + item.id, {method: "DELETE"}); await setBatch(selectedMaterials.filter(id => id !== item.id)); await loadMaterials(); }
        catch (error) { $("#material-status").textContent = error.message; }
      };
      li.append(info, remove); $("#material-list").append(li);
    });
  } catch (error) { $("#material-status").textContent = error.message; }
  finally {materialRefreshing = false;}
}
setInterval(() => {if ($("#materials").open) loadMaterials(true);}, 1000);
$("#file-input").onchange = async (event) => {
  if (busy || materialOperations) {event.target.value = ""; return;}
  const input = event.target; input.disabled = true;
  materialOperations++;
  const queued = [...input.files].map(file => {
    const row = document.createElement("li"); row.textContent = file.name + " · Queued";
    $("#import-queue").append(row); return {file, row};
  });
  try {
    for (const {file, row} of queued) {
      try {
      if (file.size > 25 * 1024 * 1024) throw new Error(file.name + " exceeds 25 MB.");
      row.replaceChildren(makeStudyLoader(), document.createTextNode(file.name + " · Uploading to this device"));
      $("#material-status").textContent = "Saving " + file.name + "…";
      const item = await request("/api/materials/upload?name=" + encodeURIComponent(file.name), {method: "POST", body: file});
      row.remove(); await loadMaterials();
      if (["pdf", "pptx", "docx", "txt", "md"].includes(item.kind)) await importMaterial(item);
      } catch(error) {row.textContent = file.name + " · " + error.message; if (!row.isConnected) $("#import-queue").append(row);}
    }
    await loadMaterials();
  } catch (error) { $("#material-status").textContent = error.message; }
  finally {materialOperations--; input.disabled = false; input.value = ""; await loadMaterials();}
};
$("#url-form").onsubmit = async (event) => {
  event.preventDefault(); const button = $("#url-form button"); button.disabled = true;
  if (busy || materialOperations) {button.disabled = false; return;}
  materialOperations++;
  try {
    const item = await request("/api/materials/url", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({url: $("#material-url").value})});
    await importMaterial(item);
    $("#material-url").value = ""; await loadMaterials();
  } catch (error) { $("#material-status").textContent = error.message; }
  finally {materialOperations--; button.disabled = false; await loadMaterials();}
};
function updateVoices() {
  deviceVoice = window.speechSynthesis?.getVoices().find((voice) => voice.localService && voice.lang.startsWith("en"));
  $("#read-aloud").disabled = !deviceVoice;
  $("#voice-status").textContent = deviceVoice ? "Device voice: " + deviceVoice.name : "No local English voice is available in this browser.";
}
async function importMaterial(item) {
  materialOperations++;
  $("#ingestion-confirmation").textContent = "";
  const row = [...$("#material-list").children].find(node => node.dataset.materialId === item.id);
  if (row) {
    row.querySelector(".material-progress")?.replaceWith(materialProgress({...item, importing: true, import_stage: "extracting"}));
    row.querySelectorAll("button, input").forEach(control => {control.disabled = true;});
  }
  $("#ingestion-progress").hidden = false;
  $("#ingestion-detail").textContent = "Preparing " + item.name + " and classmate study facts…";
  try {
  $("#material-status").textContent = "Importing " + item.name + "…";
  const result = await request("/api/materials/" + item.id + "/process", {method: "POST"});
  $("#material-status").textContent = result.error || result.status;
  if (result.status !== "Ready") throw new Error(result.error || "No searchable text was found.");
  await setBatch([...new Set([...selectedMaterials, item.id])]);
  $("#ingestion-confirmation").textContent = item.name + " is ready: " + result.chunk_count + " searchable passages. Added to this session. " + (result.facts_count === 2 ? "Two classmate facts are ready. " : "Classmate facts unavailable; you can still study this material. ") + (result.warning || "");
  } catch(error) {$("#ingestion-confirmation").textContent = item.name + ": " + error.message; throw error;}
  finally {materialOperations--; $("#ingestion-progress").hidden = true;}
}
function makeStudyLoader() {const icon = document.createElement("span"); icon.className = "study-loader"; icon.setAttribute("aria-hidden", "true"); return icon;}
if (window.speechSynthesis) speechSynthesis.onvoiceschanged = updateVoices;
$("#stop-speech").onclick = () => window.speechSynthesis?.cancel();
initChatTools(); updateVoices(); restoreChat();
let checkingProfessor = false;
async function refreshProfessorStatus() {
  if (checkingProfessor) return;
  checkingProfessor = true;
  try {
    const {ollama} = await request("/api/health");
    $("#professor-model").textContent = ollama.model;
    let state, text, detail;
    if (!ollama.connected) {state = "offline"; text = "Professor is offline"; detail = "Ollama is not reachable";}
    else if (!ollama.model_available) {state = "missing"; text = "Professor needs a model"; detail = "Configured model is not installed";}
    else if (ollama.model_loaded === true) {state = "ready"; text = "● Professor is ready"; detail = "Loaded locally in Ollama";}
    else if (ollama.model_loaded === false) {state = "idle"; text = "Professor is resting"; detail = "Installed · loads when you send a question";}
    else {state = "unknown"; text = "Professor status unconfirmed"; detail = "Installed · loaded state unavailable";}
    $("#status").textContent = text; $("#status").dataset.state = state; $("#model-state").textContent = detail;
  } catch {
    $("#status").textContent = "Cannot reach Professor"; $("#status").dataset.state = "offline";
    $("#model-state").textContent = "Backend connection unavailable";
  } finally {checkingProfessor = false;}
}
refreshProfessorStatus();
setInterval(() => {if (!document.hidden) refreshProfessorStatus();}, 15000);
document.addEventListener("visibilitychange", () => {if (!document.hidden) refreshProfessorStatus();});

let viewingSession = null;
let sessionRequestVersion = 0;
async function loadSessions() {
  const version = ++sessionRequestVersion;
  viewingSession = null; $("#session-detail").hidden = true; $("#session-list").replaceChildren();
  $("#sessions-status").textContent = "Loading study sessions…";
  try {
    const sessions = await request("/api/conversations");
    if (version !== sessionRequestVersion) return;
    $("#sessions-status").textContent = sessions.length ? "Saved on this device" : "Your first conversation will appear here.";
    for (const session of sessions) {
      const li = document.createElement("li"), button = document.createElement("button"), meta = document.createElement("small");
      button.className = "session-open";
      button.textContent = session.title; button.setAttribute("aria-pressed", "false");
      meta.textContent = session.message_count + " messages · " + (session.document_ids || []).length + " materials · " + new Date(session.updated_at).toLocaleDateString();
      const remove = document.createElement("button");
      remove.className = "session-delete"; remove.type = "button"; remove.textContent = "Delete";
      remove.setAttribute("aria-label", "Delete session: " + session.title);
      remove.title = "Delete this study session";
      remove.onclick = () => deleteSession(session.id, session.title, remove);
      button.append(meta); li.append(button, remove); $("#session-list").append(li);
      button.onclick = async () => {
        const current = ++sessionRequestVersion;
        $("#session-detail").hidden = true; viewingSession = null;
        try {
          const data = await request("/api/conversations/" + session.id);
          if (current !== sessionRequestVersion) return;
          viewingSession = session.id;
          $("#session-title").textContent = session.title; $("#session-memory").value = data.memory || "";
          $("#session-messages").replaceChildren();
          data.messages.forEach(message => {
            const p = document.createElement("p"); p.textContent = (message.role === "user" ? "You: " : "Professor: ") + message.content;
            $("#session-messages").append(p);
          });
          $("#session-list").querySelectorAll(".session-open").forEach(item => item.setAttribute("aria-pressed", String(item === button)));
          $("#session-detail").hidden = false; $("#sessions-status").textContent = "";
        } catch (error) {if (current === sessionRequestVersion) $("#sessions-status").textContent = error.message;}
      };
    }
  } catch (error) {if (version === sessionRequestVersion) $("#sessions-status").textContent = error.message;}
}
$("#session-memory-form").onsubmit = async event => {
  event.preventDefault();
  if (!viewingSession) return;
  if (busy) {$("#sessions-status").textContent = "Wait for Professor's reply before saving notes."; return;}
  const id = viewingSession;
  const button = $("#session-memory-form button"); button.disabled = true;
  try {
    await request("/api/conversations/" + id + "/memory", {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify({memory: $("#session-memory").value})});
    if (viewingSession === id) $("#sessions-status").textContent = "Study notes saved for this session.";
  } catch (error) {$("#sessions-status").textContent = error.message;}
  finally {button.disabled = false;}
};
$("#resume-session").onclick = async () => {
  if (!viewingSession) return;
  if (busy || materialOperations || batchSaving || sessionCreation) {$("#sessions-status").textContent = "Wait for preparation or Professor's reply before switching sessions."; return;}
  conversationId = viewingSession; localStorage.setItem("study-buddy-conversation", conversationId);
  $("#message").value = ""; $("#task-mode").value = "auto"; $("#chat-error").textContent = ""; $("#chat-search").value = "";
  await restoreChat(); openDialog("chat");
};
$("#delete-session").onclick = async () => {
  if (!viewingSession) return;
  await deleteSession(viewingSession, $("#session-title").textContent, $("#delete-session"));
};
let sessionDeleting = false;
async function deleteSession(id, title, button) {
  if (sessionDeleting) return;
  if (busy || materialOperations || batchSaving || sessionCreation) {
    $("#sessions-status").textContent = "Wait for the current operation before deleting a session."; return;
  }
  if (!window.confirm('Delete "' + title + '" and its conversation, notes, and quiz progress? Uploaded materials will remain.')) return;
  sessionDeleting = true; button.disabled = true;
  try {
    await request("/api/conversations/" + id, {method: "DELETE"});
    if (conversationId === id) await $("#new-chat").onclick();
    await loadSessions();
    $("#sessions-status").textContent = "Session deleted. Uploaded materials kept.";
  } catch (error) {$("#sessions-status").textContent = error.message;}
  finally {button.disabled = false; sessionDeleting = false;}
}
$("#create-session-form").onsubmit = async event => {
  event.preventDefault(); if (busy || materialOperations || batchSaving || sessionCreation) return;
  try {
    const data = await request("/api/conversations", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({title: $("#new-session-title").value.trim() || "Study session", document_ids: []})});
    conversationId = data.conversation_id; localStorage.setItem("study-buddy-conversation", conversationId);
    $("#message").value = ""; $("#task-mode").value = "auto";
    await restoreChat(); openDialog("materials");
  } catch(error) {$("#sessions-status").textContent = error.message;}
};
