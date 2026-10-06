const assert = require('node:assert/strict');
const fs = require('node:fs');

const app = fs.readFileSync('app/ui/static/app.js', 'utf8');
const classroom = fs.readFileSync('app/ui/static/classroom-life.js', 'utf8');
const html = fs.readFileSync('app/ui/static/index.html', 'utf8');

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
