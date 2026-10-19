const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const app = fs.readFileSync('app/ui/static/app.js', 'utf8');
const source = app.slice(app.indexOf('async function sendChatMessage('), app.indexOf('$("#message").addEventListener("keydown"'));
function element() {
  return {classList: {add() {}, remove() {}}, prepend() {}, append() {}, remove() {}, setAttribute() {},
    querySelector() { return element(); }, textContent: '', isConnected: true};
}
const elements = new Map();
const requests = [];
let retry;
const outgoing = element();
outgoing.append = button => { retry = button; };
const context = {
  busy: false, switchingModel: false, professorModel: 'llama3.2:3b',
  conversationId: 'session', selectedMaterials: ['book'], conversationMessages: [], deviceVoice: null,
  $: key => { if (!elements.has(key)) elements.set(key, element()); return elements.get(key); },
  addMessage: () => element(), document: {createElement: () => element()},
  ensureStudyMaterial: async () => {}, ensureSession: async () => {},
  request: async (url, options) => {
    requests.push(JSON.parse(options.body));
    if (requests.length === 1) throw new Error('Quiz generation failed');
    return {conversation_id: 'session', message: 'Question 1', sources: []};
  },
  localStorage: {setItem() {}}, setInterval: () => 1, clearInterval() {},
  updateQuizChoices() {}, updateContext() {}, updateTokenUsage() {}, searchTranscript() {}, refreshProfessorStatus() {},
};
vm.createContext(context);
vm.runInContext(source, context);
(async () => {
  assert.equal(await context.sendChatMessage('quiz me on logistic regression', outgoing), false);
  assert.equal(context.conversationMessages.length, 0);
  context.professorModel = 'gpt-oss:20b';
  retry.onclick();
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(requests.map(r => r.model), ['llama3.2:3b', 'gpt-oss:20b']);
  assert.equal(requests[0].message, requests[1].message);
  assert.equal(requests[0].conversation_id, requests[1].conversation_id);
  assert.equal(context.conversationMessages.filter(m => m.role === 'user').length, 1);
  context.conversationId = 'another-session';
  retry.onclick();
  assert.equal(requests.length, 2);
  console.log('Retry uses the newly selected model, preserves the request, and guards changed sessions.');
})().catch(error => { console.error(error); process.exitCode = 1; });
