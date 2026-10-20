/* A read-only tour: navigation never uploads, selects materials, or calls a model. */
(() => {
  const key = "study-buddy-tour-v1";
  const dialog = document.querySelector("#welcome-tour");
  const steps = [
    [null, ".room", "Welcome to Study Buddy", "I'm Professor. Bring your class materials, and we'll work through them together. Let me show you around."],
    ["materials", "#materials", "Your bookshelf", "Add notes, slides, PDFs, or a public webpage here. Wait until an import is ready, then choose the materials for your study session."],
    ["sessions", "#create-session-form", "A place for each subject", "Create a session for a class or topic. Each session keeps its own selected materials, conversation, and quiz progress."],
    ["chat", "#message", "Ask Professor", "Ask about your material, request a simpler explanation, or try Quiz me. Quizzes default to five questions unless you ask for another number."],
    ["chat", ".source-passages > summary", "Check the source", "This Source passages control sits beneath a sourced answer. Open it to read the excerpts and see which material and page or slide they came from."],
    ["chat", ".follow-ups", "Keep the conversation going", "These shortcuts ask for a simpler explanation or start a quiz. During a quiz, answer first, then choose Next question. More study actions includes summaries and missed-answer review."],
    ["room-menu", "#professor-model", "Choose your Professor", "Choose an available model here. Larger local models need more memory. Cloud models send your chat and relevant material excerpts to Ollama cloud and need internet."],
    ["bookmarks", "#bookmarks", "Your saved concepts", "The star beside an answer saves it here as a concept. You're ready to start: open the bookshelf and add your first material. You can replay this tour from the classroom menu."]
  ];
  let index = 0, target = null, previous = null, focus = null;
  let example = null;
  function clearTarget() {
    target?.classList.remove("tour-highlight");
    example?.remove();
    example = null;
  }
  function sourceTarget() {
    const sources = document.querySelectorAll("#messages .source-passages > summary");
    if (sources.length) return sources[sources.length - 1];
    // Tour-only DOM: never add a message to saved conversation state.
    example = document.createElement("article");
    example.className = "assistant";
    example.dataset.tourExample = "true";
    const label = document.createElement("strong");
    label.textContent = "Tour example - not your material";
    const body = document.createElement("p");
    body.textContent = "A sourced answer includes a control like this one.";
    const details = document.createElement("details");
    details.className = "source-passages";
    const summary = document.createElement("summary");
    summary.textContent = "Source passages (example)";
    const passage = document.createElement("p");
    passage.textContent = "Example notes - Page 1: Plants need light to grow.";
    details.append(summary, passage);
    example.append(label, body, details);
    document.querySelector("#messages").append(example);
    return summary;
  }
  const next = document.querySelector("#tour-next");
  const back = document.querySelector("#tour-back");
  function show() {
    dialog.close();
    clearTarget();
    const [area, selector, title, copy] = steps[index];
    if (area) openDialog(area);
    else document.querySelectorAll("dialog[open]").forEach(item => item.close());
    target = selector === ".source-passages > summary" ? sourceTarget() : document.querySelector(selector);
    target?.classList.add("tour-highlight");
    target?.scrollIntoView({block: "center", behavior: "instant"});
    document.querySelector("#tour-title").textContent = title;
    document.querySelector("#tour-copy").textContent = copy;
    document.querySelector("#tour-progress").textContent = `${index + 1} of ${steps.length}`;
    back.disabled = index === 0;
    next.textContent = index === steps.length - 1 ? "Finish" : "Next";
    // Keep the bubble away from compact targets such as the chat composer.
    const rect = target?.getBoundingClientRect();
    const above = rect && rect.top > innerHeight / 2;
    dialog.style.top = above ? "16px" : "auto";
    dialog.style.bottom = above ? "auto" : "16px";
    dialog.showModal();
    next.focus();
  }
  function finish() {
    clearTarget();
    dialog.close();
    document.querySelectorAll("dialog[open]").forEach(item => item.close());
    try { localStorage.setItem(key, "done"); } catch (_) { /* Storage can be disabled. */ }
    if (previous) openDialog(previous);
    if (focus?.isConnected) focus.focus();
  }
  function start() {
    if (typeof busy !== "undefined" && busy) return;
    if (document.querySelector("#model-loading[open]")) return;
    previous = document.querySelector("dialog[open]")?.id || null;
    focus = document.activeElement;
    index = 0;
    show();
  }
  next.onclick = () => index === steps.length - 1 ? finish() : (index++, show());
  back.onclick = () => { if (index > 0) { index--; show(); } };
  document.querySelector("#tour-skip").onclick = finish;
  dialog.addEventListener("cancel", event => { event.preventDefault(); finish(); });
  document.querySelector("#replay-tour").onclick = start;
  let completed = false;
  try { completed = localStorage.getItem(key) === "done"; } catch (_) { completed = true; }
  if (!completed) window.addEventListener("load", () => {
    // Do not interrupt a restored dialog or a model switch on page load.
    if (!document.querySelector("dialog[open]")) start();
  }, {once: true});
})();
