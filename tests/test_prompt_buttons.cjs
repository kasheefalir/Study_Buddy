const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync('app/ui/static/index.html', 'utf8');
const buttons = [...html.matchAll(/<button\b([^>]*data-prompt="([^"]*)"[^>]*)>/g)].map(match => ({
  id: /id="([^"]*)"/.exec(match[1])?.[1] || '',
  dataset: {prompt: match[2], questionId: 'saved-question'},
}));
assert.equal(buttons.length, 6);
assert.doesNotMatch(html, /data-task=/);
const nodes = {};
const context = {
  $: selector => nodes[selector] ||= {value: '', dataset: {}, focus() {}},
  document: {querySelectorAll: () => buttons},
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('app/ui/static/chat-tools.js', 'utf8'), context);
vm.runInContext('searchTranscript = () => {}; updateTokenUsage = () => {}; initChatTools();', context);
for (const button of buttons) {
  nodes['#message'] = {value: '', dataset: {nextQuestionId: 'stale'}, focus() {}};
  nodes['#task-mode'] = {value: 'quiz'};
  button.onclick();
  assert.equal(nodes['#message'].value, button.dataset.prompt);
  assert.equal(nodes['#task-mode'].value, 'auto');
  assert.equal(nodes['#message'].dataset.nextQuestionId,
    button.id === 'next-question' ? 'saved-question' : undefined);
  nodes['#message'].value = 'My unfinished question';
  nodes['#task-mode'].value = 'chat';
  button.onclick();
  assert.equal(nodes['#message'].value, 'My unfinished question');
  assert.equal(nodes['#task-mode'].value, 'chat');
}
console.log('Prompt buttons use automatic routing, preserve drafts and retain quiz event guards.');
