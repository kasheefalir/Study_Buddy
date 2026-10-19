const assert = require('node:assert/strict');
const fs = require('node:fs');

const app = fs.readFileSync('app/ui/static/app.js', 'utf8');
const classroom = fs.readFileSync('app/ui/static/classroom-life.js', 'utf8');
const html = fs.readFileSync('app/ui/static/index.html', 'utf8');
assert.doesNotMatch(app, /confirmCloudSharing|cloud_consent|cloudConsent/);

const openDialog = app.slice(
  app.indexOf('function openDialog(id)'),
  app.indexOf('async function request(', app.indexOf('function openDialog(id)')),
);

assert.match(openDialog, /\$\("#" \+ id\)\.showModal\(\)/);
assert.match(openDialog, /querySelectorAll\("\[data-open\]"\)/);
assert.doesNotMatch(openDialog, /hideBubble|showBubble/);

assert.match(classroom, /button\.onclick = \(\) => this\.interact\(npc\)/);
assert.match(classroom, /else this\.open\(target\.id\)/);
assert.match(classroom, /this\.open\("classmate"\)/);

assert.match(html, /data-open="chat"/);
assert.match(html, /data-open="materials"/);
assert.match(html, /id="chat"/);
assert.match(html, /id="materials"/);
assert.match(html, /id="classmate"/);

console.log('Classroom click and proximity interactions remain connected to their dialogs.');

const vm = require('node:vm');
const dialogs = Object.fromEntries(['chat', 'materials', 'sessions'].map(id => [id, {
  id, open: false, close() { this.open = false; }, showModal() { this.open = true; },
}]));
const context = {
  life: {pause() {}},
  document: {querySelectorAll: () => Object.values(dialogs).filter(d => d.open)},
  $: selector => selector === '#message' ? {focus() {}} : dialogs[selector.slice(1)],
  loadMaterials() {}, loadSessions() {}, renderBookmarks() {}, refreshProfessorStatus() {},
};
vm.createContext(context);
vm.runInContext(openDialog.slice(0, openDialog.indexOf('document.querySelectorAll("[data-open]"')), context);
context.openDialog('chat');
context.openDialog('materials');
assert.equal(dialogs.chat.open, true);
dialogs.materials.close(); // Both the close button and native Escape close only this dialog.
assert.equal(dialogs.chat.open, true);
dialogs.chat.close();
context.openDialog('materials');
dialogs.materials.close();
assert.equal(dialogs.chat.open, false, 'Bookshelf opened from classroom must not open chat on close');
context.openDialog('chat');
context.openDialog('materials');
context.openDialog('sessions');
assert.equal(dialogs.chat.open, false);
assert.equal(dialogs.materials.open, false);
assert.equal(dialogs.sessions.open, true);
console.log('Materials preserves its parent chat; explicit navigation closes the old dialogs.');

const notes = {'#model-ram-guidance': {}, '#privacy-note': {}};
const privacyContext = {
  $: selector => notes[selector],
  professorModel: 'gemma4:31b-cloud',
  modelRamGuidance: {'gemma4:31b-cloud': 'Cloud', 'llama3.2:3b': 'Local'},
};
vm.createContext(privacyContext);
vm.runInContext(app.slice(app.indexOf('function isCloudModel('), app.indexOf('const professorModels')), privacyContext);
for (const model of ['gemma4:31b-cloud', 'other:cloud', 'other:100b-cloud']) {
  privacyContext.professorModel = model;
  privacyContext.updateModelRamGuidance();
  assert.equal(notes['#privacy-note'].textContent, 'Mind in the clouds: your chat and relevant material excerpts are sent to Ollama cloud.');
  assert.doesNotMatch(notes['#model-ram-guidance'].textContent, /undefined/);
}
assert.equal(privacyContext.isCloudModel('cloud-helper:3b'), false);
privacyContext.professorModel = 'llama3.2:3b';
privacyContext.updateModelRamGuidance();
assert.equal(notes['#privacy-note'].textContent, 'Your own quiet corner. Saved on this device.');
