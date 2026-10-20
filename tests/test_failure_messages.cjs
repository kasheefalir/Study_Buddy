const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const app = fs.readFileSync("app/ui/static/app.js", "utf8");
const source = app.slice(app.indexOf("const failureMessages ="), app.indexOf("function addMessage("));
async function run() {
  for (const code of ["ollama_offline", "model_timeout", "context_limit", "quiz_feedback", "model_access", "rate_limit"]) {
    const context = vm.createContext({fetch: async () => ({
      ok: false, status: 503, headers: {get: () => code},
      json: async () => ({detail: "Misleading output limit wording"}),
    })});
    vm.runInContext(source, context);
    await assert.rejects(context.request("/api/chat"), error => {
      assert.equal(error.code, code);
      assert.equal(error.status, 503);
      assert.doesNotMatch(error.message, /Misleading|bigger|larger/);
      assert.equal(error.diagnostic, "Misleading output limit wording");
      return true;
    });
  }
  const offline = vm.createContext({fetch: async () => {throw new Error("network");}});
  vm.runInContext(source, offline);
  await assert.rejects(offline.request("/api/chat"), /Cannot reach Study Buddy/);
  console.log("Failure messages use codes, retain diagnostics, and distinguish app connectivity.");
}
run().catch(error => {console.error(error); process.exit(1);});
