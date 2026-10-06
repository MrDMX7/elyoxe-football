// X (Twitter) reader for the journal — owner 2026-09-30: «ما عدا x، ييب الاخبار browser بالفولد… اي طريقة اسهلك واوفر
// واحسن» and «عادي باي حساب». No paid API: a real Chromium, headful on its own virtual screen (never headless), signed in
// with the @Elyoxe session copied from the posting profile, opens a few source accounts per run and keeps the posts X's
// own page loads (the UserTweets responses). Read-only: it never clicks, follows, likes or posts.
//
//   node news/xreader.js [--handles a,b] [--dry]     writes news/.x-inbox.json; news.run reads and empties it
//
// Rotation: every run reads the accounts marked `every: true` plus the next `per_run` from the list (news/sources.yaml `x:`),
// so ~5 profile loads per run. Runs no more often than `min_minutes` apart, whatever calls it.
// Live first (owner 2026-10-07 «ممتاز كمل», after the Gulf Cup final's clips came hours late): while a match is on or finished
// in the last 3 h (v1/live.json), the official accounts tied to it (its clubs', federations', league's, and the broadcasters'
// with its competition in `comps:`) are read first, `hot_per_run` at a time in turn, the rotation shrinks to `live_per_run`,
// and runs may come every `live_minutes`. `--plan` prints the pick and stops.
//
// Where it runs (owner 2026-09-30: «نخلي شغلة تويتر… على اللابتوب عشان ما يخلص جرج التلفون»): the LAPTOP, every 30 min from
// Task Scheduler (news/xreader-task.vbs, hidden), Edge in a window parked off-screen; `--upload` puts the inbox at
// s3://…/state/news/x-inbox.json and the Fold's news.run reads it from there. The Fold can still run it by hand (Xvfb).
// The laptop's session comes from the Fold's reader profile: `ssh fold "node …/xreader.js --export-cookies" > <profile>/x-cookies.json`.
'use strict';
const fs = require('fs'), os = require('os'), path = require('path'), { execSync, spawn } = require('child_process');
const WIN = process.platform === 'win32', HOME = os.homedir();
const PW = [path.join(HOME, 'workspace/content-pipeline/node_modules/playwright-core'), 'playwright-core', 'playwright'];
let chromium; for (const p of PW) { try { chromium = require(p).chromium; break; } catch (e) {} }
const HERE = __dirname, INBOX = path.join(HERE, '.x-inbox.json');
// X's «rate limit» page: both readers (this and news/xmood.js) rest 45 minutes on the one session they share
const COOL = path.join(HERE, '.x-cooldown.json'), REST = 45 * 60e3;
const resting = () => { try { const c = JSON.parse(fs.readFileSync(COOL, 'utf8')); return c.until > Date.now() ? c : null; } catch (e) { return null; } };
const SRC_PROFILE = path.join(HOME, 'workspace/automation/browse/profiles/elyoxe-social');
const PROFILE = path.join(HOME, 'workspace/automation/browse/profiles/x-reader');
const BUCKET = process.env.FOOTBALL_BUCKET || 'elyoxe-football-574771023173-ap-south-1';
const DISPLAY = ':98';
const a = process.argv.slice(2), arg = (k) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : null; };
const log = (...x) => (a.includes('--export-cookies') ? console.error : console.log)('[x]', ...x);

function config() {
  // the `x:` block of sources.yaml, read without a YAML library: one flow mapping per line, as the file writes them
  const y = fs.readFileSync(path.join(HERE, 'sources.yaml'), 'utf8');
  const blk = (y.split(/^x:\s*$/m)[1] || '').split(/^\S/m)[0];
  const num = (k, d) => { const m = blk.match(new RegExp('^\\s+' + k + ':\\s*(\\d+)', 'm')); return m ? +m[1] : d; };
  const accounts = [];
  for (const line of blk.split('\n')) {
    const m = line.match(/^\s*-\s*\{(.*)\}\s*(#.*)?$/); if (!m) continue;
    const o = {};
    for (const kv of m[1].matchAll(/(\w+):\s*(\[[^\]]*\]|"([^"]*)"|[^,]+)/g)) {   // `comps: [538, 329]` is a list
      const v = kv[3] !== undefined ? kv[3] : kv[2].trim();
      o[kv[1]] = v[0] === '[' ? v.slice(1, -1).split(',').map(x => x.trim()).filter(Boolean) : v;
    }
    accounts.push(o);
  }
  return { per_run: num('per_run', 4), min_minutes: num('min_minutes', 28), max_posts: num('max_posts', 20),
           live_minutes: num('live_minutes', 13), hot_per_run: num('hot_per_run', 5), live_per_run: num('live_per_run', 2), accounts };
}

const DATA = 'https://d1n5aqaqkowltp.cloudfront.net', AFTER_H = 3;
async function hotSet() {
  // the matches on now or finished in the last AFTER_H hours: goal clips come during the match, the summary after it
  const H = { teams: new Set(), comps: new Set() };
  try {
    const r = await fetch(DATA + '/v1/live.json', { signal: AbortSignal.timeout(20000) }), j = r.ok ? await r.json() : null;
    for (const m of (j && j.matches) || []) {
      const on = m.status === 'live' || m.status === 'ht' || (m.status === 'finished' && Date.now() - Date.parse(m.kickoff_utc || 0) < AFTER_H * 36e5);
      if (!on) continue;
      [m.home && m.home.id, m.away && m.away.id].forEach(t => { if (t) H.teams.add(+t); });
      if (m.comp) H.comps.add(+m.comp);
    }
  } catch (e) { log('live matches not read:', String(e.message || e).slice(0, 80)); }
  return H;
}
const ids = (x, one, many) => [].concat(x[one] ? [x[one]] : [], x[many] || []).map(Number);
const isHot = (x, H) => x.tier === 'official' && x.every !== 'true' &&
  (ids(x, 'team', 'teams').some(t => H.teams.has(t)) || ids(x, 'comp', 'comps').some(c => H.comps.has(c)));

function plan(cfg, inbox, H) {
  // the accounts of this run: `every`, then the live matches' (in turn), then the rotation; each once
  const every = cfg.accounts.filter(x => x.every === 'true'), hot = cfg.accounts.filter(x => isHot(x, H)), rest = cfg.accounts.filter(x => x.every !== 'true');
  const turn = (list, key, n) => {
    if (!list.length || n <= 0) return [];
    const c = (inbox[key] || 0) % list.length; inbox[key] = (c + n) % list.length;
    return list.slice(c, c + n).concat(list.slice(0, Math.max(0, c + n - list.length)));
  };
  const seen = new Set(), pick = [];
  for (const x of every.concat(turn(hot, 'hot_cursor', cfg.hot_per_run), turn(rest, 'cursor', hot.length ? cfg.live_per_run : cfg.per_run))) {
    if (!seen.has(x.handle.toLowerCase())) { seen.add(x.handle.toLowerCase()); pick.push(x); }
  }
  return { pick, hot };
}

function seedProfile() {
  fs.mkdirSync(PROFILE, { recursive: true });
  for (const f of fs.readdirSync(PROFILE)) if (f.startsWith('Singleton')) fs.rmSync(path.join(PROFILE, f), { force: true });
  if (WIN) return;   // the laptop's session is x-cookies.json, added to the context below
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
        const all = (L.extended_entities || L.entities || {}).media || [], media = all[0];
        out.push({ id: L.id_str || o.rest_id, text: text(o), at: new Date(L.created_at).toISOString(), handle: sn,
                   name: (u && ((u.core && u.core.name) || (u.legacy && u.legacy.name))) || sn, image: media ? media.media_url_https : null,
                   video: all.some(m => m.type === 'video'),   // news/media.py: an official post with a video can be a goal clip
                   url: `https://x.com/${sn}/status/${L.id_str || o.rest_id}` });
      }
      return;   // a quoted post inside is someone else's
    }
    for (const k in o) visit(o[k]);
  };
  visit(json);
  return out;
}

async function main() {
  if (!chromium) { console.error('playwright-core not found'); process.exit(2); }
  const rest = resting(); if (rest && !a.includes('--export-cookies')) { log('X rate-limited the session at', new Date(rest.at).toISOString().slice(11, 16), '- resting until', new Date(rest.until).toISOString().slice(11, 16)); return; }
  const cfg = config(), inbox = fs.existsSync(INBOX) ? JSON.parse(fs.readFileSync(INBOX, 'utf8')) : { cursor: 0, last_run: null, items: [], errors: {} };
  const H = arg('--handles') || a.includes('--export-cookies') ? null : await hotSet();
  const live = H ? cfg.accounts.some(x => isHot(x, H)) : false, gap = live ? cfg.live_minutes : cfg.min_minutes;
  if (H && !a.includes('--plan') && inbox.last_run && (Date.now() - Date.parse(inbox.last_run)) / 6e4 < gap) { log('ran', inbox.last_run, '- skip'); return; }
  let pick;
  if (arg('--handles')) pick = arg('--handles').split(',').map(h => cfg.accounts.find(x => x.handle.toLowerCase() === h.toLowerCase()) || { handle: h, name: h, lang: 'en', tier: 'journalist' });
  else if (H) {
    const p = plan(cfg, inbox, H); pick = p.pick;
    if (p.hot.length) log('live first:', p.hot.length, 'accounts of the matches on (competitions ' + [...H.comps].join(',') + ')');
  }
  if (a.includes('--plan')) { log('pick:', (pick || []).map(x => x.handle).join(', ')); return; }
  seedProfile(); if (!WIN) xvfb();
  const ctx = await chromium.launchPersistentContext(PROFILE, WIN ? {
    // Edge, a real window parked off-screen: never headless, never in the owner's way
    channel: 'msedge', headless: false, viewport: { width: 1280, height: 1500 }, locale: 'en-US',
    args: ['--disable-blink-features=AutomationControlled', '--mute-audio', '--window-position=-32000,-32000', '--window-size=1280,1600'],
  } : {
    executablePath: '/usr/bin/chromium', headless: false, env: Object.assign({}, process.env, { DISPLAY }),
    viewport: { width: 1280, height: 1500 }, locale: 'en-US',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled', '--mute-audio', '--window-size=1280,1600'],
  });
  if (a.includes('--export-cookies')) {   // the session, for the laptop's profile (run on the Fold; stdout only, never a file in git)
    process.stdout.write(JSON.stringify(await ctx.cookies(['https://x.com'])));
    await ctx.close(); return;
  }
  const jar = path.join(PROFILE, 'x-cookies.json');
  if (!(await ctx.cookies(['https://x.com'])).some(c => c.name === 'auth_token') && fs.existsSync(jar)) {
    await ctx.addCookies(JSON.parse(fs.readFileSync(jar, 'utf8'))); log('session added from x-cookies.json');
  }
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
        if (inbox.errors[acc.handle] === 'rate limited') {   // stop at the first one, and the mood reader rests too
          fs.writeFileSync(COOL, JSON.stringify({ at: Date.now(), until: Date.now() + REST, by: 'reader' })); log('RATE LIMITED: resting', REST / 60e3, 'min'); break;
        }
      } catch (e) { inbox.errors[acc.handle] = String(e.message || e).slice(0, 120); }
      page.off('response', onResp);
      const fresh = got.slice(0, cfg.max_posts).filter(p => !seen.has(p.id));
      // a broadcaster's post is press to the journal (its «رسمي» is not the club's), but its videos are official to news/media.py
      fresh.forEach(p => { seen.add(p.id); inbox.items.push(Object.assign(p, { lang: acc.lang || 'en', tier: acc.kind === 'broadcaster' ? 'paper' : acc.tier || 'journalist', team: acc.team || null, comp: acc.comp || null, source: acc.name || p.name })); });
      added += fresh.length;
      log('@' + acc.handle, got.length, 'posts,', fresh.length, 'new', inbox.errors[acc.handle] ? '(' + inbox.errors[acc.handle] + ')' : '');
      await page.waitForTimeout(2500 + Math.random() * 2500);   // a person's pace between profiles
    }
  } finally { await ctx.close().catch(() => {}); }
  inbox.last_run = new Date().toISOString();
  inbox.items = inbox.items.slice(-800);
  if (!a.includes('--dry')) {
    fs.writeFileSync(INBOX, JSON.stringify(inbox));
    // the whole inbox (last 800 posts) overwrites the copy in S3; news.run skips the posts it already has by id
    if (a.includes('--upload')) execSync(`aws s3 cp "${INBOX}" s3://${BUCKET}/state/news/x-inbox.json --content-type application/json --cache-control no-store --only-show-errors`, { stdio: 'inherit', timeout: 120000 });   // execSync blocks the watchdog
  }
  log('done:', added, 'new posts from', pick.length, 'accounts');
}

if (require.main === module) {
  // a run takes ~1 min (6 at worst). On 2026-10-06 one hung before its first line with Edge open (02:39) and kept the log open,
  // so every later run failed on the redirect for 4 h. Past 10 min it gives up; Playwright's exit handler kills the Edge it launched
  setTimeout(() => { console.error('[x] watchdog: still running after 10 min, giving up'); process.exit(3); }, 10 * 60e3).unref();
  main().catch(e => { console.error(e); process.exit(1); });
}
module.exports = { config, plan, isHot };
