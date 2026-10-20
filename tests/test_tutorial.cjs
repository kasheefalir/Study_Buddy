// Run with Playwright available in NODE_PATH and Study Buddy running locally.
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch({headless: true, channel: 'chrome'});
  try {
    for (const width of [1280, 390]) {
      const page = await browser.newPage({viewport: {width, height: 850}});
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.goto('http://127.0.0.1:8001/');
      const tour = page.locator('#welcome-tour');
      await tour.waitFor({state: 'visible'});
      assert.equal(await page.locator('#tour-progress').textContent(), '1 of 8');
      await page.locator('#tour-next').click();
      await page.locator('#tour-back').click();
      assert.equal(await page.locator('#tour-progress').textContent(), '1 of 8');
      for (let i = 0; i < 8; i++) {
        const box = await tour.boundingBox();
        assert(box.x >= 0 && box.y >= 0 && box.x + box.width <= width + 1);
        assert(box.y + box.height <= 851);
        if (i === 4) {
          assert.equal(await page.locator('.source-passages > summary.tour-highlight').count(), 1);
          assert.equal(await page.locator('.follow-ups.tour-highlight').count(), 0);
          assert.equal(await page.locator('[data-tour-example]').count(), 1);
          await page.screenshot({path: `/tmp/study-tour-${width}.png`});
        }
        await page.locator('#tour-next').click();
        assert.equal(await page.locator('[data-tour-example]').count(), i === 3 ? 1 : 0);
      }
      assert.equal(await page.evaluate(() => localStorage.getItem('study-buddy-tour-v1')), 'done');
      await page.reload();
      assert.equal(await tour.isVisible(), false);
      await page.locator('header [data-open="room-menu"]').click();
      await page.locator('#replay-tour').click();
      await tour.waitFor({state: 'visible'});
      // Existing source controls must be used without modifying their open state.
      await page.evaluate(() => {
        const article = document.createElement('article');
        article.id = 'test-source';
        article.innerHTML = '<details class="source-passages" open><summary>Source passages (1)</summary><p>Existing evidence</p></details>';
        document.querySelector('#messages').append(article);
      });
      for (let i = 0; i < 4; i++) await page.locator('#tour-next').click();
      assert.equal(await page.locator('#test-source summary.tour-highlight').count(), 1);
      assert.equal(await page.locator('[data-tour-example]').count(), 0);
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('.tour-highlight').count(), 0);
      assert.equal(await page.locator('#test-source details').getAttribute('open'), '');
      assert.equal(await tour.isVisible(), false);
      assert.equal(await page.locator('#room-menu').isVisible(), true);
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log('Tutorial passes desktop/mobile navigation, completion, replay, Escape, and bounds checks.');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
