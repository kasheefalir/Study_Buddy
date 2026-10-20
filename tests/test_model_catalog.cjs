const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("app/ui/static/app.js", "utf8");
function element() {
  return {children: [], value: "", textContent: "", append(child) {this.children.push(child);},
    replaceChildren() {this.children = [];}};
}
const nodes = Object.fromEntries(["#professor-model", "#model-downloads", "#model-download-status"]
  .map(id => [id, element()]));
let installed = [{name: "custom:4b"}];
let state = {active: false};
const calls = [];
const context = vm.createContext({
  $: id => nodes[id], document: {createElement: element},
  professorModel: "custom:4b", switchingModel: false,
  modelLabel: name => name, isCloudModel: name => name.endsWith("-cloud"),
  request: async (url, options) => {
    calls.push({url, options});
    if (options) {state = {active: true}; return state;}
    return {models: installed, recommended: ["llama3.2:3b"], download: state};
  },
});
vm.runInContext("let catalogChecking = false; let downloadingModel = false; let modelCatalogSignature = '';\n" +
  source.slice(source.indexOf("async function refreshModelCatalog()"),
    source.indexOf("setInterval(async () => {", source.indexOf("async function refreshModelCatalog()"))), context);
(async () => {
  await vm.runInContext("refreshModelCatalog()", context);
  assert.equal(nodes["#professor-model"].value, "custom:4b");
  assert.equal(nodes["#professor-model"].children[0].disabled, true);
  const button = nodes["#model-downloads"].children[0];
  assert.match(button.textContent, /Download.*2 GB/);
  await button.onclick();
  assert.equal(JSON.parse(calls.find(call => call.options).options.body).model, "llama3.2:3b");
  assert.equal(nodes["#model-downloads"].children[0].disabled, true);
  installed.push({name: "llama3.2:3b"});
  state = {active: false};
  await vm.runInContext("refreshModelCatalog()", context);
  assert.equal(nodes["#model-downloads"].children.length, 0);
  assert.equal(nodes["#professor-model"].children[0].disabled, false);
  console.log("Dynamic picker and missing-model download controls passed.");
})().catch(error => {console.error(error); process.exitCode = 1;});
