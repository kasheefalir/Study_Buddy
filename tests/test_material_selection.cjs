const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('app/ui/static/app.js', 'utf8');
const start = source.indexOf('async function ensureStudyMaterial()');
const end = source.indexOf('const studyDesk', start);

async function check(items, options = {}) {
  const selected = [];
  const context = vm.createContext({
    selectedMaterials: options.selected || [], materialOperations: options.working || 0,
    request: async () => items,
    selectMaterial: async (id, name) => selected.push({id, name}),
  });
  vm.runInContext(source.slice(start, end), context);
  await vm.runInContext('ensureStudyMaterial()', context);
  return selected;
}

(async () => {
  const ready = {id: 'deck', name: 'Course.pptx', status: 'Ready'};
  assert.deepEqual(await check([ready]), []); // New sessions never inherit the library.
  assert.deepEqual(await check([ready], {selected: ['deck']}), []);
  assert.deepEqual(await check([]), []);
  await assert.rejects(check([ready], {selected: ['missing']}), /missing or not ready/);
  await assert.rejects(check([{...ready, status: 'Processing'}], {selected: ['deck']}), /not ready/);
  await assert.rejects(check([], {working: 1}), /preparation/);
  console.log('Session isolation, material readiness, and preparation guards passed.');
})().catch(error => {console.error(error); process.exitCode = 1;});
