// X (Twitter) reader for the journal — owner 2026-09-30: «ما عدا x، ييب الاخبار browser بالفولد… اي طريقة اسهلك واوفر
// واحسن» and «عادي باي حساب». No paid API: a real Chromium, headful on its own virtual screen (never headless), signed in
// with the @Elyoxe session copied from the posting profile, opens a few source accounts per run and keeps the posts X's
// own page loads (the UserTweets responses). Read-only: it never clicks, follows, likes or posts.
//
//   node news/xreader.js [--handles a,b] [--dry]     writes news/.x-inbox.json; news.run reads and empties it
//
// Rotation: every run reads the accounts marked `every: true` plus the next `per_run` from the list (news/sources.yaml `x:`),
// so ~5 profile loads per run. Runs no more often than `min_minutes` apart, whatever calls it.
'use strict';
const fs = require('fs'), path = require('path'), { execSync, spawn } = require('child_process');
const PW = ['/root/workspace/content-pipeline/node_modules/playwright-core', 'playwright-core', 'playwright'];
let chromium; for (const p of PW) { try { chromium = require(p).chromium; break; } catch (e) {} }
const HERE = __dirname, INBOX = path.join(HERE, '.x-inbox.json');
const SRC_PROFILE = '/root/workspace/automation/browse/profiles/elyoxe-social';
const PROFILE = '/root/workspace/automation/browse/profiles/x-reader';
const DISPLAY = ':98';
const a = process.argv.slice(2), arg = (k) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : null; };
const log = (...x) => console.log('[x]', ...x);

function config() {
  // the `x:` block of sources.yaml, read without a YAML library: one flow mapping per line, as the file writes them
  const y = fs.readFileSync(path.join(HERE, 'sources.yaml'), 'utf8');
  const blk = (y.split(/^x:\s*$/m)[1] || '').split(/^\S/m)[0];
  const num = (k, d) => { const m = blk.match(new RegExp('^\\s+' + k + ':\\s*(\\d+)', 'm')); return m ? +m[1] : d; };
  const accounts = [];
  for (const line of blk.split('\n')) {
    const m = line.match(/^\s*-\s*\{(.*)\}\s*(#.*)?$/); if (!m) continue;
    const o = {}; for (const kv of m[1].matchAll(/(\w+):\s*("([^"]*)"|[^,]+)/g)) o[kv[1]] = kv[3] !== undefined ? kv[3] : kv[2].trim();
    accounts.push(o);
  }
  return { per_run: num('per_run', 4), min_minutes: num('min_minutes', 28), max_posts: num('max_posts', 20), accounts };
}

function seedProfile() {
  // copy the session (cookies + the key file that decrypts them) from the posting profile; the posting profile itself is
  // never opened here, so the screen browser can stay up while this runs
  fs.mkdirSync(path.join(PROFILE, 'Default'), { recursive: true });
  const src = path.join(SRC_PROFILE, 'Default', 'Cookies'), dst = path.join(PROFILE, 'Default', 'Cookies');
  const age = fs.existsSync(dst) ? (Date.now() - fs.statSync(dst).mtimeMs) / 36e5 : 1e9;
  if (age > 24) {
    execSync(`python3 -c "import sqlite3; s=sqlite3.connect('file:${src}?mode=ro', uri=True); d=sqlite3.connect('${dst}.new'); s.backup(d); d.close()"`);
    fs.renameSync(dst + '.new', dst);
    fs.copyFileSync(path.join(SRC_PROFILE, 'Local State'), path.join(PROFILE, 'Local State'));
    log('session copied from the posting profile');
  }
  for (const f of fs.readdirSync(PROFILE)) if (f.startsWith('Singleton')) fs.rmSync(path.join(PROFILE, f), { force: true });
}

function xvfb() {
  // the display's socket, not pgrep: `pgrep -f "Xvfb :98"` from execSync matches its own shell and always says yes
  const sock = '/tmp/.X11-unix/X' + DISPLAY.slice(1);
  if (fs.existsSync(sock)) return;
  spawn('Xvfb', [DISPLAY, '-screen', '0', '1280x1600x24', '-nolisten', 'tcp'], { detached: true, stdio: 'ignore' }).unref();
  for (let i = 0; i < 20 && !fs.existsSync(sock); i++) execSync('sleep 0.25');
}

function text(t) {   // a post's full text: long posts keep it in note_tweet
  const n = t.note_tweet && t.note_tweet.note_tweet_results && t.note_tweet.note_tweet_results.result;
  return ((n && n.text) || (t.legacy && t.legacy.full_text) || '').replace(/\s*https:\/\/t\.co\/\w+$/, '').trim();
}

function posts(json, handle) {
  // walk the UserTweets timeline; keep the account's own posts (no replies, no reposts), pinned or not
  const out = [];
  const visit = (o) => {
    if (!o || typeof o !== 'object') return;
    if (o.__typename === 'Tweet' && o.legacy && o.core) {
      const u = o.core.user_results && o.core.user_results.result, sn = (u && ((u.core && u.core.screen_name) || (u.legacy && u.legacy.screen_name))) || '';
      const L = o.legacy;
      if (sn.toLowerCase() === handle.toLowerCase() && !L.retweeted_status_result && !L.in_reply_to_status_id_str) {
        const media = ((L.extended_entities || L.entities || {}).media || [])[0];
        out.push({ id: L.id_str || o.rest_id, text: text(o), at: new Date(L.created_at).toISOString(), handle: sn,
                   name: (u && ((u.core && u.core.name) || (u.legacy && u.legacy.name))) || sn, image: media ? media.media_url_https : null,
                   url: `https://x.com/${sn}/status/${L.id_str || o.rest_id}` });
      }
      return;   // a quoted post inside is someone else's
    }
    for (const k in o) visit(o[k]);
  };
  visit(json);
  return out;
}

(async () => {
  if (!chromium) { console.error('playwright-core not found'); process.exit(2); }
  const cfg = config(), inbox = fs.existsSync(INBOX) ? JSON.parse(fs.readFileSync(INBOX, 'utf8')) : { cursor: 0, last_run: null, items: [], errors: {} };
  if (!arg('--handles') && inbox.last_run && (Date.now() - Date.parse(inbox.last_run)) / 6e4 < cfg.min_minutes) { log('ran', inbox.last_run, '- skip'); return; }
  let pick;
  if (arg('--handles')) pick = arg('--handles').split(',').map(h => cfg.accounts.find(x => x.handle.toLowerCase() === h.toLowerCase()) || { handle: h, name: h, lang: 'en', tier: 'journalist' });
  else {
    const every = cfg.accounts.filter(x => x.every === 'true'), rest = cfg.accounts.filter(x => x.every !== 'true');
    const cur = (inbox.cursor || 0) % Math.max(1, rest.length);
    pick = every.concat(rest.slice(cur, cur + cfg.per_run), rest.slice(0, Math.max(0, cur + cfg.per_run - rest.length)));
    inbox.cursor = (cur + cfg.per_run) % Math.max(1, rest.length);
  }
  seedProfile(); xvfb();
  const ctx = await chromium.launchPersistentContext(PROFILE, {
    executablePath: '/usr/bin/chromium', headless: false, env: Object.assign({}, process.env, { DISPLAY }),
    viewport: { width: 1280, height: 1500 }, locale: 'en-US',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled', '--mute-audio', '--window-size=1280,1600'],
  });
  const page = ctx.pages()[0] || await ctx.newPage();
  const seen = new Set(inbox.items.map(x => x.id)); let added = 0;
  try {
    for (const acc of pick) {
      let got = [];
      const onResp = async (r) => {
        if (a.includes('--debug') && /graphql/.test(r.url())) log('gql', r.status(), r.url().split('?')[0].split('/').slice(-1)[0]);
        if (!/\/graphql\/[^/]+\/(UserTweets|UserOriginalsTimeline)\b/.test(r.url())) return;   // X renamed it by 2026-09-30
        try { got = got.concat(posts(await r.json(), acc.handle)); } catch (e) {}
      };
      page.on('response', onResp);
      try {
        await page.goto('https://x.com/' + acc.handle, { waitUntil: 'domcontentloaded', timeout: 60000 });
        for (let i = 0; i < 20 && !got.length; i++) await page.waitForTimeout(500);
        await page.waitForTimeout(1500);
        if (/\/login|\/i\/flow/.test(page.url())) { inbox.errors[acc.handle] = 'not signed in'; log('NOT SIGNED IN'); break; }
        const body = await page.locator('body').innerText().catch(() => '');
        if (a.includes('--debug')) { await page.screenshot({ path: `/tmp/x-${acc.handle}.png` }).catch(() => {}); log('url', page.url(), '|', body.replace(/\s+/g, ' ').slice(0, 400)); }
        if (!got.length) inbox.errors[acc.handle] = /doesn.t exist|account is suspended/i.test(body) ? 'no such account' : /rate limit|try again/i.test(body) ? 'rate limited' : 'no posts seen';
        else delete inbox.errors[acc.handle];
      } catch (e) { inbox.errors[acc.handle] = String(e.message || e).slice(0, 120); }
      page.off('response', onResp);
      const fresh = got.slice(0, cfg.max_posts).filter(p => !seen.has(p.id));
      fresh.forEach(p => { seen.add(p.id); inbox.items.push(Object.assign(p, { lang: acc.lang || 'en', tier: acc.tier || 'journalist', team: acc.team || null, comp: acc.comp || null, source: acc.name || p.name })); });
      added += fresh.length;
      log('@' + acc.handle, got.length, 'posts,', fresh.length, 'new', inbox.errors[acc.handle] ? '(' + inbox.errors[acc.handle] + ')' : '');
      await page.waitForTimeout(2500 + Math.random() * 2500);   // a person's pace between profiles
    }
  } finally { await ctx.close().catch(() => {}); }
  inbox.last_run = new Date().toISOString();
  inbox.items = inbox.items.slice(-800);
  if (!a.includes('--dry')) fs.writeFileSync(INBOX, JSON.stringify(inbox));
  log('done:', added, 'new posts from', pick.length, 'accounts');
})().catch(e => { console.error(e); process.exit(1); });
