// The official accounts' video posts further back than the reader's inbox holds (owner 2026-11-19: «جميع الاهداف خلال الشهر
// الماضي … سواء من اليوتيوب او من السوشال ميديا»). news/xreader.js reads each account's latest ~20 posts in turn, so a club
// that posts 40 times on a match night, read every hour or two, left most of its goal clips unseen. This walks X's own search
// page for each official account, `from:<handle> filter:native_video since:<day>`, newest first, and keeps the posts its
// SearchTimeline responses carry (the same parse as the reader: the account's own posts, no replies, no reposts).
//
//   node news/xhistory.js [--since 2026-10-18] [--handles a,b] [--scrolls 40] [--stop-at <ISO time>] [--upload] [--dry]
//
// Read-only like the reader: it never clicks, follows, likes or posts. Its own browser profile (x-history) with the reader's
// session (x-reader/x-cookies.json), so it can run while the reader's task does. X's rate-limit page stops it at once and
// makes both readers rest (news/.x-cooldown.json, 45 min) — never run it while a match is on (the goal clips come from the
// reader then). Out: news/.x-history.json; --upload puts it at s3://…/state/news/x-history.json for news/media_backfill.py.
'use strict';
const fs = require('fs'), os = require('os'), path = require('path'), { execSync } = require('child_process');
const { config, posts } = require('./xreader.js');
const WIN = process.platform === 'win32', HOME = os.homedir();
const PW = [path.join(HOME, 'workspace/content-pipeline/node_modules/playwright-core'), 'playwright-core', 'playwright'];
let chromium; for (const p of PW) { try { chromium = require(p).chromium; break; } catch (e) {} }
const HERE = __dirname, OUT = path.join(HERE, '.x-history.json'), COOL = path.join(HERE, '.x-cooldown.json'), REST = 45 * 60e3;
const PROFILE = path.join(HOME, 'workspace/automation/browse/profiles/x-history');
const JAR = path.join(HOME, 'workspace/automation/browse/profiles/x-reader/x-cookies.json');
const BUCKET = process.env.FOOTBALL_BUCKET || 'elyoxe-football-574771023173-ap-south-1';
const a = process.argv.slice(2), arg = (k) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : null; };
const log = (...x) => console.log('[xh]', ...x);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

// The UAE first, then the Gulf, the other Arab countries, the Arabic-language accounts and the rest, each group in sources.yaml's
// order (owner 2026-11-20: the 23:00 run of 11-19 reached six European clubs before X's limit, and no UAE account).
const GULF = ['sa', 'qa', 'kw', 'bh', 'om'], ARAB = ['eg', 'iq', 'jo', 'ps', 'lb', 'sy', 'ma', 'dz', 'tn', 'ly', 'sd', 'ye'];
const rank = (x) => x.country === 'ae' ? 0 : GULF.includes(x.country) ? 1 : ARAB.includes(x.country) ? 2 : x.lang === 'ar' ? 3 : 4;
function order(accs) { return accs.map((x, i) => [x, i]).sort((p, q) => rank(p[0]) - rank(q[0]) || p[1] - q[1]).map(p => p[0]); }
// X's search answers about 50 pages a quarter-hour (that run was cut off near its 50th page, 6 minutes in): no more than BUDGET
// in any WINDOW. wait() is how long the next page waits, given when the earlier ones went out.
const BUDGET = 40, WINDOW = 15 * 60e3;
function wait(stamps, now, budget = BUDGET, win = WINDOW) {
  const recent = stamps.filter(t => now - t < win).sort((p, q) => p - q);
  return recent.length < budget ? 0 : recent[recent.length - budget] + win - now + 1000;
}
const stamps = [];
async function paced() {
  for (let w = wait(stamps, Date.now()); w > 0; w = wait(stamps, Date.now())) { log('pacing:', Math.round(w / 1000), 's'); await sleep(w); }
  stamps.push(Date.now());
}

async function main() {
  if (!chromium) { console.error('playwright-core not found'); process.exit(2); }
  try { const c = JSON.parse(fs.readFileSync(COOL, 'utf8')); if (c.until > Date.now()) { log('X is resting the session until', new Date(c.until).toISOString()); return; } } catch (e) {}
  const since = arg('--since') || new Date(Date.now() - 32 * 864e5).toISOString().slice(0, 10);
  const scrolls = +(arg('--scrolls') || 40), stopAt = arg('--stop-at') ? Date.parse(arg('--stop-at')) : null;
  const cfg = config();
  let accs = order(cfg.accounts.filter(x => x.tier === 'official'));
  if (arg('--handles')) { const hs = arg('--handles').toLowerCase().split(','); accs = accs.filter(x => hs.includes(x.handle.toLowerCase())); }
  const box = fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT, 'utf8')) : { items: [], done: {} };
  const seen = new Set(box.items.map(x => x.id));
  fs.mkdirSync(PROFILE, { recursive: true });
  for (const f of fs.readdirSync(PROFILE)) if (f.startsWith('Singleton')) fs.rmSync(path.join(PROFILE, f), { force: true });
  const ctx = await chromium.launchPersistentContext(PROFILE, {
    channel: WIN ? 'msedge' : undefined, executablePath: WIN ? undefined : '/usr/bin/chromium', headless: false,
    viewport: { width: 1280, height: 1500 }, locale: 'en-US',
    args: ['--disable-blink-features=AutomationControlled', '--mute-audio', '--window-position=-32000,-32000', '--window-size=1280,1600'],
  });
  if (!(await ctx.cookies(['https://x.com'])).some(c => c.name === 'auth_token')) await ctx.addCookies(JSON.parse(fs.readFileSync(JAR, 'utf8')));
  const page = ctx.pages()[0] || await ctx.newPage();
  let limited = false;
  try {
    for (const acc of accs) {
      if (stopAt && Date.now() > stopAt) { log('stop time reached before @' + acc.handle); break; }
      const d = box.done[acc.handle.toLowerCase()];
      if (d && d.since <= since && Date.now() - Date.parse(d.at) < 12 * 36e5 && !a.includes('--again')) { log('@' + acc.handle, 'read', d.at.slice(0, 16), '- skip'); continue; }
      let got = [], pages = 0, status429 = false;
      const onResp = async (r) => {
        if (!/\/graphql\/[^/]+\/SearchTimeline\b/.test(r.url())) return;
        if (r.status() === 429) { status429 = true; return; }
        try { got = got.concat(posts(await r.json(), acc.handle)); pages++; } catch (e) {}
      };
      page.on('response', onResp);
      const q = encodeURIComponent(`from:${acc.handle} filter:native_video since:${since}`);
      try {
        await paced();
        await page.goto(`https://x.com/search?q=${q}&src=typed_query&f=live`, { waitUntil: 'domcontentloaded', timeout: 60000 });
        for (let i = 0; i < 20 && !pages; i++) await sleep(500);
        if (/\/login|\/i\/flow/.test(page.url())) { log('NOT SIGNED IN'); limited = true; break; }
        let still = 0, last = -1;
        for (let s = 0; s < scrolls && still < 3 && !status429; s++) {
          await paced();
          await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
          await sleep(2200 + Math.random() * 1800);
          if (got.length === last) still++; else { still = 0; last = got.length; }
        }
        const body = await page.locator('body').innerText().catch(() => '');
        if (status429 || /rate limit|Something went wrong. Try reloading/i.test(body) && !got.length) {
          fs.writeFileSync(COOL, JSON.stringify({ at: Date.now(), until: Date.now() + REST, by: 'history' }));
          log('RATE LIMITED at @' + acc.handle + ': stopping, both readers rest', REST / 60e3, 'min'); limited = true;
        }
      } catch (e) { log('@' + acc.handle, 'error', String(e.message || e).slice(0, 120)); }
      page.off('response', onResp);
      const vids = got.filter(p => p.video && !seen.has(p.id));
      vids.forEach(p => { seen.add(p.id); box.items.push(Object.assign(p, { lang: acc.lang || 'en', tier: acc.kind === 'broadcaster' ? 'paper' : acc.tier || 'journalist', team: acc.team || null, comp: acc.comp || null, source: acc.name || p.name })); });
      if (!limited) box.done[acc.handle.toLowerCase()] = { since, at: new Date().toISOString(), n: got.length };
      const oldest = got.map(p => p.at).sort()[0];
      log('@' + acc.handle, got.length, 'posts in', pages, 'pages,', vids.length, 'new with a video, back to', (oldest || '-').slice(0, 10));
      if (!a.includes('--dry')) fs.writeFileSync(OUT, JSON.stringify(box));
      if (limited) break;
      await sleep(6000 + Math.random() * 5000);
    }
  } finally { await ctx.close().catch(() => {}); }
  const cut = new Date(Date.parse(since) - 864e5).toISOString();
  box.items = box.items.filter(x => (x.at || '') >= cut);
  if (!a.includes('--dry')) {
    fs.writeFileSync(OUT, JSON.stringify(box));
    if (a.includes('--upload')) execSync(`aws s3 cp "${OUT}" s3://${BUCKET}/state/news/x-history.json --content-type application/json --cache-control no-store --only-show-errors`, { stdio: 'inherit', timeout: 120000 });
  }
  log('done:', box.items.length, 'posts with a video kept', limited ? '(stopped early)' : '');
}

module.exports = { order, wait };

if (require.main === module) main().catch(e => { console.error(e); process.exit(1); });
