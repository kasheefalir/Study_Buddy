const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/static/app.js", "utf8");
const start = source.indexOf("async function sendChatMessage(");
const end = source.indexOf('$("#message").addEventListener', start);
assert(end > start);

async function run(cancel) {
  const elements = new Map();
  const $ = (key) => {
    if (key === "#messages .quiz-failure") return null;
    if (!elements.has(key)) elements.set(key, {textContent: "", disabled: false, hidden: true});
    return elements.get(key);
  };
  const timers = new Map();
  let timerId = 0, finish, now = 0, sent;
  const pending = {
    isConnected: true,
    classList: {add() {}},
    querySelector: () => ({prepend() {}}),
    remove() { this.isConnected = false; },
  };
  const sandbox = {
    $, busy: false, switchingModel: false, professorModel: "local",
    conversationId: "session", selectedMaterials: [], conversationMessages: [],
    crypto: {randomUUID: () => "token"}, performance: {now: () => now},
    document: {createElement: () => ({setAttribute() {}})},
    localStorage: {setItem() {}}, addMessage: () => pending,
    ensureStudyMaterial: async () => {}, ensureSession: async () => {},
    updateQuizChoices() {}, updateContext() {}, updateTokenUsage() {},
    searchTranscript() {}, refreshProfessorStatus() {},
    setInterval(fn) { timers.set(++timerId, fn); return timerId; },
    clearInterval(id) { timers.delete(id); },
    async request(url, options) {
      if (url.endsWith("/activity")) return {active: true, stage: "Finding relevant passages"};
      if (url.includes("/cancel?")) {
        assert(url.endsWith("request_id=token"));
        finish(new Error("Response cancelled. You can retry when ready."));
        return {cancelled: true};
      }
      assert.equal(url, "/api/chat");
      sent = JSON.parse(options.body);
      return new Promise((resolve, reject) => {
        finish = (error) => error ? reject(error) : resolve({conversation_id: "session", message: "Done"});
      });
    },
  };
  // Success optionally invokes speech; keep it disabled.
  $("#read-aloud").checked = false;
  vm.createContext(sandbox);
  vm.runInContext(source.slice(start, end), sandbox);
  const result = sandbox.sendChatMessage("Explain this", null);
  while (!finish) await new Promise(resolve => setImmediate(resolve));
  assert.equal(sent.request_id, "token");
  assert.equal($("#chat-progress").hidden, false);
  now = 3500;
  for (const tick of timers.values()) await tick();
  assert.equal($("#chat-elapsed").textContent, "3s");
  assert.equal($("#chat-stage").textContent, "Finding relevant passages");
  assert.equal($("#cancel-response").disabled, false);
  if (cancel) await $("#cancel-response").onclick();
  else finish();
  assert.equal(await result, !cancel);
  assert.equal($("#chat-progress").hidden, true);
  assert.equal($("#chat-form button").disabled, false);
  assert.equal(timers.size, 0);
  assert.equal(sandbox.busy, false);
}

(async () => {
  await run(true);
  await run(false);
  console.log("Progress, elapsed time, cancellation, and success cleanup passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
