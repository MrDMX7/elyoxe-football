const { chromium } = require('/root/workspace/automation/browse/node_modules/playwright-core');
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const p = b.contexts()[0].pages()[0]; await p.bringToFront();
  await p.goto('https://search.google.com/search-console/sitemaps?resource_id=' + encodeURIComponent('https://tifo.elyoxe.com/'), { waitUntil: 'domcontentloaded', timeout: 60000 });
  await p.waitForTimeout(10000);
  const inp = p.locator('input:visible').filter({ hasNot: p.locator('[aria-label*="Inspect"]') });
  const vis = await p.$$eval('input', els => els.filter(e => e.offsetWidth||e.offsetHeight).map(e => e.getAttribute('aria-label')));
  console.log('inputs', JSON.stringify(vis));
  const box = p.locator('input[aria-label="Enter sitemap URL"]:visible, input[aria-label*="sitemap"]:visible').first();
  await box.click({ timeout: 10000 }); await box.fill('sitemap.xml');
  await p.waitForTimeout(800);
  await p.locator('[role=button]:visible, button:visible').filter({ hasText: /^\s*submit\s*$/i }).first().click({ timeout: 10000 });
  await p.waitForTimeout(12000);
  console.log((await p.evaluate(() => document.body.innerText)).slice(-1500));
  await p.screenshot({ path: 'sc9.png' });
  await b.close();
})();
