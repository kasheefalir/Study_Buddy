// Run with Playwright available in NODE_PATH. Uses synthetic UI data only.
const {chromium} = require("playwright");
const assert = require("node:assert/strict");

(async () => {
  const browser = await chromium.launch({headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || "chrome"});
  try {
    for (const width of [1280, 390]) {
      const page = await browser.newPage({viewport: {width, height: 900}});
      await page.addInitScript(() => localStorage.setItem("study-buddy-tour-v1", "done"));
      await page.goto("http://127.0.0.1:8000/");
      await page.waitForFunction(() => typeof addMessage === "function");
      await page.evaluate(() => {
        openDialog("chat");
        document.querySelector("#messages").replaceChildren();
        addMessage("assistant", "A sourced explanation [S1]. Unknown reference [S99]. Code: `[S1]`.", [
          {label: "S1", name: "Synthetic notes", location: "Section 1", text: "A supporting passage.", variant: "generated_summary"},
        ]);
      });
      assert.equal(await page.locator(".source-citation").count(), 1);
      await page.getByRole("button", {name: "Read source S1", exact: true}).click();
      assert.equal(await page.locator(".source-passages").evaluate(el => el.open), true);
      assert.match(await page.locator(".source-passages").innerText(), /AI-generated summary \(not original text\)/);
      assert.equal(await page.evaluate(() => document.activeElement.textContent.includes("A supporting passage")), true);
      await page.evaluate(() => {
        document.querySelector("#chat-progress").hidden = false;
        document.querySelector("#chat-stage").textContent = "Finding relevant passages";
        document.querySelector("#chat-elapsed").textContent = "12s";
      });
      const progress = await page.locator("#chat-progress").boundingBox();
      assert(progress.x >= 0 && progress.x + progress.width <= width);
      await page.screenshot({path: `/tmp/study-buddy-demo-${width}.png`});
      let attempts = 0;
      await page.route("**/api/chat", route => {
        attempts++;
        return route.fulfill({status: attempts === 1 ? 503 : 200, contentType: "application/json",
          headers: {"X-Study-Error": "quiz_generation"},
          body: JSON.stringify(attempts === 1 ? {detail: "My brain hit a snag preparing this quiz. Try fewer questions or a larger model."}
            : {conversation_id: "synthetic", message: "Recovered reply", sources: []})});
      });
      await page.evaluate(async () => {
        ensureStudyMaterial = async () => {};
        ensureSession = async () => {};
        conversationId = "synthetic";
        await sendChatMessage("Quiz me", addMessage("user", "Quiz me"));
      });
      assert.match(await page.locator(".quiz-failure").innerText(), /My brain hit a snag.*larger model/s);
      await page.getByRole("button", {name: "Not delivered · Retry"}).click();
      await page.locator("#messages").getByText("Recovered reply", {exact: true}).waitFor();
      assert.equal(attempts, 2);
      assert.equal(await page.locator(".quiz-failure").count(), 0);
      assert.equal(await page.locator("#chat-progress").isVisible(), false);
      assert.equal(await page.getByRole("button", {name: "Send message", exact: true}).isEnabled(), true);
      await page.close();
    }
    console.log("Desktop/mobile citation navigation, summary disclosure, and progress layout passed.");
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
