// «نبض الجمهور» (owner bold idea 9, 2026-10-06: «عادي خله يقرا»): how each side's fans feel during a match, from what they post
// on X — happy, angry or tense — as a live line on the match page (site/src/mood.js reads /v1/mood/<match>.json).
//
//   node news/xmood.js [--loop] [--upload] [--match <id> --force] [--dry] [--show]
//
// Which matches: live now, or kicking off within 30 min, or finished within the last 20 min, that involve an Arab national team
// or are played in a competition of an Arab country (config.competitions/countries), the Gulf Cup or the AFC club competitions.
// For each, two of X's own «Latest» searches every 3 minutes, in Arabic: each team's name without the other's (the posts that
// name one side are its fans', roughly). Read-only, like news/xreader.js: a real Edge window parked off-screen with the @Elyoxe
// session (the reader's x-cookies.json, in a profile of its own), never headless, never a click; a sign-in or rate-limit page
// stops the run, it is never worked around.
// A post's mood: words and emoji of joy, anger or nerves (MOOD below, rules only: Claude and Gemini stay off for Tifo); a post
// with none, or a tie, counts for nothing. Published per match: counts per side in 5-minute steps from kickoff and the last
// 10 minutes — never a post's text, author or link. `--loop` keeps one browser for as long as a watched match is on (4 h at
// most) and holds a lock (news/.x-mood.lock) so the Task Scheduler's every-10-minutes start (news/xmood-task.vbs) finds it busy.
'use strict';
const fs = require('fs'), os = require('os'), path = require('path'), zlib = require('zlib'), { execSync, execFileSync } = require('child_process');
const HOME = os.homedir(), HERE = __dirname, ROOT = path.join(HERE, '..');
const PW = [path.join(HOME, 'workspace/content-pipeline/node_modules/playwright-core'), 'playwright-core', 'playwright'];
let chromium; for (const p of PW) { try { chromium = require(p).chromium; break; } catch (e) {} }
const STATE = path.join(HERE, '.x-mood.json'), LOCK = path.join(HERE, '.x-mood.lock');
const PROFILE = path.join(HOME, 'workspace/automation/browse/profiles/x-mood');
const JAR = path.join(HOME, 'workspace/automation/browse/profiles/x-reader/x-cookies.json');
const BUCKET = process.env.FOOTBALL_BUCKET || 'elyoxe-football-574771023173-ap-south-1';
const DATA = 'https://d1n5aqaqkowltp.cloudfront.net';
const EVERY = 3 * 60e3, STEP = 5 * 60e3, MAX_RUN = 4 * 36e5, BEFORE = 30 * 60e3, AFTER = 20 * 60e3, WATCH_COMPS_EXTRA = [329, 10242, 525, 9469, 9470];
const a = process.argv.slice(2), arg = (k) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : null; };
const log = (...x) => console.log('[mood]', new Date().toISOString().slice(11, 19), ...x);

// ------------------------------------------------------------------ moods
const norm = (s) => String(s || '').toLowerCase().replace(/[ً-ٰٟـ]/g, '').replace(/[إأآٱ]/g, 'ا').replace(/ى/g, 'ي').replace(/ة/g, 'ه').replace(/ؤ/g, 'و').replace(/ئ/g, 'ي');
const MOOD = {
  happy: { w: ['كفو', 'كفوو', 'ابداع', 'ابدع', 'رهيب', 'روعه', 'عظمه', 'وحش', 'اسطوره', 'فخر', 'مبروك', 'الحمدلله', 'الحمد لله', 'فزنا',
               'فوز', 'بطل', 'ابطال', 'يا سلام', 'ياسلام', 'ممتع', 'تاريخي', 'احسنت', 'برافو', 'يستاهل', 'هيبه', 'تاهل', 'تاهلنا', 'فرحه', 'فرحان',
               'مبسوط', 'افضل', 'الافضل', 'عز', 'يا حلو', 'جميل'],
           e: ['😍', '🥳', '🎉', '🔥', '❤', '💚', '🤍', '💛', '💙', '👏', '💪', '😁', '😄', '🙌', '🏆', '👑', '😎', '🎊', '🤩'] },
  angry: { w: ['الحكم', 'حكم', 'ظلم', 'ظالم', 'مهزله', 'فاشل', 'فشل', 'زفت', 'خايس', 'تعبان', 'سيء', 'سيي', 'كارثه', 'فضيحه', 'اقاله', 'قهر', 'سرقه',
               'مسروق', 'خساره', 'خسرنا', 'خرب', 'خربها', 'اعتزل', 'عار', 'ضعيف', 'غبي', 'غباء', 'ارحل', 'حسبي الله', 'تبا', 'مستفز', 'حرام عليكم'],
           e: ['😡', '🤬', '😤', '💩', '👎', '🤦', '🙄', '🤮', '😠'] },
  tense: { w: ['يارب', 'يا رب', 'اللهم', 'الله يستر', 'اعصاب', 'متوتر', 'توتر', 'خايف', 'خوف', 'قلبي', 'ترجيح', 'ركلات', 'صعب', 'ضغط', 'ادعوا',
               'دعواتكم', 'يا الله', 'ياالله'],
           e: ['🙏', '🤞', '😰', '😬', '😱', '😢', '💔', '😥', '😓', '🫣', '😨'] },
};
const MW = {}; Object.keys(MOOD).forEach(k => { MW[k] = MOOD[k].w.map(norm); });
// commerce rides on match hashtags (subscriptions, tickets for sale, coupons): never a fan's mood
const SALE = ['عرض', 'اشتراك', 'السعر', 'ريال', 'درهم', 'للبيع', 'ابيع', 'ابيعهم', 'خصم', 'كود', 'تذاكر', 'تذكره', 'متجر', 'توصيل', 'سجل الحين', 'رابط'].map(norm);
// whose fans wrote it: a national team's flag or nickname (the Saudi fan who writes «هدف ثاني على الإمارات 🔥 الأخضر» is not a
// UAE fan; 2026-10-06 the UAE side read «فرحان» while 2-0 down)
const NICK = { SA: ['الاخضر', 'الصقور'], AE: ['الابيض', 'عيال زايد'], QA: ['العنابي'], KW: ['الازرق'], BH: ['الاحمر البحريني'], OM: ['الاحمر العماني'],
  IQ: ['اسود الرافدين'], JO: ['النشامى'], EG: ['الفراعنه'], MA: ['اسود الاطلس'], DZ: ['محاربي الصحراء'], TN: ['نسور قرطاج'], LY: ['فرسان المتوسط'],
  SY: ['نسور قاسيون'], PS: ['الفدائي'], LB: ['رجال الارز'], YE: ['اليمن'] };
const flag = (iso) => iso && iso.length === 2 ? String.fromCodePoint(...[...iso.toUpperCase()].map(c => 0x1F1E6 + c.charCodeAt(0) - 65)) : null;
function cheers(text, iso) {   // does the post show this side's flag or nickname?
  if (!iso) return false;
  const f = flag(iso), t = ' ' + norm(text).replace(/[^\p{L}\p{N}\s]/gu, ' ').replace(/\s+/g, ' ') + ' ';
  return (f && text.includes(f)) || (NICK[iso] || []).some(w => t.includes(' ' + norm(w) + ' '));
}
const BALL = ['منتخب', 'مباراة', 'المباراة', 'هدف', 'النهائي', 'خليجي', 'الحكم', 'جمهور', 'الجمهور', 'المدرب', 'شوط', 'كأس', 'الدوري', 'لاعب'];
function mood(text) {
  const t = ' ' + norm(text).replace(/[^\p{L}\p{N}\s]/gu, ' ').replace(/\s+/g, ' ') + ' ', s = {};
  for (const k of Object.keys(MOOD)) {
    let n = 0;
    for (const w of MW[k]) if (t.includes(' ' + w + ' ') || (w.length > 4 && t.includes(w))) n++;
    for (const e of MOOD[k].e) if (text.includes(e)) n += Math.min(2, text.split(e).length - 1);
    s[k] = n;
  }
  const best = Object.keys(s).sort((x, y) => s[y] - s[x]);
  return s[best[0]] > 0 && s[best[0]] > s[best[1]] ? best[0] : null;
}

// ------------------------------------------------------------------ which matches
function watchSet() {
  const py = `import json, config\nar = {c["iso2"] for c in config.countries() if c.get("arab")}\nprint(json.dumps({"comps": [c["id"] for c in config.competitions() if (c.get("country") or {}).get("iso2") in ar]}))`;
  const comps = new Set(WATCH_COMPS_EXTRA);
  try { JSON.parse(execFileSync(process.platform === 'win32' ? 'python' : 'python3', ['-c', py], { cwd: ROOT, timeout: 60000 }).toString()).comps.forEach(c => comps.add(c)); } catch (e) { log('watch set: competitions not read', String(e.message || e).slice(0, 80)); }
  return comps;
}
async function getJson(p) { const r = await fetch(DATA + '/' + p + '?t=' + Date.now(), { signal: AbortSignal.timeout(20000) }); return r.ok ? r.json() : null; }
async function watched(comps, nationals) {
  if (arg('--match')) { const md = await getJson('match/' + arg('--match') + '.json'); return md ? [md] : []; }
  const lv = (await getJson('live.json')) || {}, now = Date.now();
  return (lv.matches || []).filter(m => {
    if (!m.kickoff_utc || m.time_tbd) return false;
    if (!(comps.has(m.comp) || nationals.has(m.home.id) || nationals.has(m.away.id))) return false;
    const ko = Date.parse(m.kickoff_utc);
    if (m.status === 'live' || m.status === 'ht') return true;
    if (m.status === 'scheduled') return ko - now < BEFORE && now - ko < 3 * 36e5;
    if (m.status === 'finished') return now - ko < 2 * 36e5 + AFTER;   // its reactions, a little after the whistle
    return false;
  });
}

// ------------------------------------------------------------------ X
function postsOf(json) {   // every post a search result carries: id, text, time, language (reposts out)
  const out = [];
  const visit = (o) => {
    if (!o || typeof o !== 'object') return;
    if (o.__typename === 'Tweet' && o.legacy) {
      const L = o.legacy, n = o.note_tweet && o.note_tweet.note_tweet_results && o.note_tweet.note_tweet_results.result;
      if (!L.retweeted_status_result) out.push({ id: L.id_str || o.rest_id, text: (n && n.text) || L.full_text || '', at: Date.parse(L.created_at), lang: L.lang });
      return;
    }
    for (const k in o) visit(o[k]);
  };
  visit(json);
  return out;
}
async function search(page, q) {
  let got = [];
  const on = async (r) => { if (!/\/graphql\/[^/]+\/SearchTimeline\b/.test(r.url())) return; try { got = got.concat(postsOf(await r.json())); } catch (e) {} };
  page.on('response', on);
  try {
    await page.goto('https://x.com/search?q=' + encodeURIComponent(q) + '&src=typed_query&f=live', { waitUntil: 'domcontentloaded', timeout: 60000 });
    for (let i = 0; i < 24 && !got.length; i++) await page.waitForTimeout(500);
    if (/\/login|\/i\/flow/.test(page.url())) throw new Error('not signed in');
    const body = await page.locator('body').innerText().catch(() => '');
    if (!got.length && /rate limit|try again later|something went wrong/i.test(body)) throw new Error('rate limited');
    await page.mouse.wheel(0, 2400); await page.waitForTimeout(2500);   // one more page of posts, as a reader scrolls
  } finally { page.off('response', on); }
  return got;
}

// ------------------------------------------------------------------ the file a match page reads
function publish(m, st) {
  const ko = Date.parse(m.kickoff_utc), sides = { home: m.home, away: m.away }, out = { generated: new Date().toISOString(), match: m.id, ko: m.kickoff_utc, status: m.status,
    note: 'من منشورات X بالعربي عن كل فريق، تقريبي', steps: [], now: {}, total: {} };
  const z = () => ({ happy: 0, angry: 0, tense: 0, n: 0 });
  const by = {};
  for (const p of Object.values(st.posts)) {
    if (p.skip) continue;
    const b = Math.floor((p.at - ko) / STEP), k = b + '';
    by[k] = by[k] || { b, home: z(), away: z() }; const s = by[k][p.side];
    s.n++; if (p.m) s[p.m]++;
  }
  out.steps = Object.values(by).sort((x, y) => x.b - y.b).map(x => ({ b: x.b, h: [x.home.happy, x.home.angry, x.home.tense, x.home.n], a: [x.away.happy, x.away.angry, x.away.tense, x.away.n] }));
  for (const side of ['home', 'away']) {
    const t = z(), w = z(), since = Date.now() - 10 * 60e3;
    for (const p of Object.values(st.posts)) if (p.side === side && !p.skip) { t.n++; if (p.m) t[p.m]++; if (p.at >= since) { w.n++; if (p.m) w[p.m]++; } }
    out.total[side] = Object.assign({ name: sides[side].name_ar || sides[side].name }, t); out.now[side] = w;
  }
  const body = zlib.gzipSync(JSON.stringify(out));
  if (a.includes('--dry')) { log('would publish', m.id, JSON.stringify(out.total), 'steps', out.steps.length); return; }
  const f = path.join(os.tmpdir(), `tifo-mood-${m.id}.json.gz`); fs.writeFileSync(f, body);
  if (a.includes('--upload')) execSync(`aws s3 cp "${f}" s3://${BUCKET}/v1/mood/${m.id}.json --content-type "application/json; charset=utf-8" --content-encoding gzip --cache-control "public, max-age=30" --only-show-errors --region ap-south-1`, { stdio: 'inherit', timeout: 120000 });
}

// ------------------------------------------------------------------ the run
function lock() {
  try { const o = JSON.parse(fs.readFileSync(LOCK, 'utf8')); if (Date.now() - o.beat < 10 * 60e3) return false; } catch (e) {}
  fs.writeFileSync(LOCK, JSON.stringify({ pid: process.pid, beat: Date.now() })); return true;
}
const beat = () => { try { fs.writeFileSync(LOCK, JSON.stringify({ pid: process.pid, beat: Date.now() })); } catch (e) {} };
const unlock = () => { try { if (JSON.parse(fs.readFileSync(LOCK, 'utf8')).pid === process.pid) fs.unlinkSync(LOCK); } catch (e) {} };

(async () => {
  if (!chromium) { console.error('playwright-core not found'); process.exit(2); }
  if (!lock()) { log('another run holds the lock'); return; }
  const t0 = Date.now(); let ctx = null, page = null;
  const watchdog = setTimeout(() => { console.error('[mood] watchdog: past the longest match window, giving up'); unlock(); process.exit(3); }, MAX_RUN + 10 * 60e3); watchdog.unref();
  try {
    const comps = watchSet(), nat = await getJson('arabs/national.json'), nationals = new Set(((nat && nat.teams) || []).map(t => t.team));
    const ISO = {}; ((nat && nat.teams) || []).forEach(t => { if (t.team && t.iso2) ISO[t.team] = t.iso2; });
    const state = fs.existsSync(STATE) ? JSON.parse(fs.readFileSync(STATE, 'utf8')) : {};
    do {
      const ms = await watched(comps, nationals);
      if (!ms.length) { log('no watched match on'); break; }
      if (!ctx) {
        fs.mkdirSync(PROFILE, { recursive: true });
        for (const f of fs.readdirSync(PROFILE)) if (f.startsWith('Singleton')) fs.rmSync(path.join(PROFILE, f), { force: true });
        ctx = await chromium.launchPersistentContext(PROFILE, { channel: 'msedge', headless: false, viewport: { width: 1280, height: 1500 }, locale: 'ar',
          args: ['--disable-blink-features=AutomationControlled', '--mute-audio', '--window-position=-32000,-32000', '--window-size=1280,1600'] });
        if (!(await ctx.cookies(['https://x.com'])).some(c => c.name === 'auth_token') && fs.existsSync(JAR)) await ctx.addCookies(JSON.parse(fs.readFileSync(JAR, 'utf8')));
        page = ctx.pages()[0] || await ctx.newPage();
      }
      for (const m of ms) {
        const st = state[m.id] = state[m.id] || { posts: {} }, names = { home: m.home.name_ar || m.home.name, away: m.away.name_ar || m.away.name };
        const pre = m.status === 'scheduled';
        for (const side of ['home', 'away']) {
          // the side's name with a football word (a bare country name brings politics, ads and airlines), without the other side
          const other = side === 'home' ? 'away' : 'home', q = `"${names[side]}" (${BALL.join(' OR ')}) -"${names[other]}" lang:ar -filter:retweets`;
          let got = [];
          try { got = await search(page, q); } catch (e) { log('stop:', e.message); throw e; }
          let fresh = 0;
          for (const p of got) {
            if (st.posts[p.id] || p.lang && p.lang !== 'ar' && p.lang !== 'und') continue;
            if (SALE.some(w => (' ' + norm(p.text).replace(/[^\p{L}\p{N}\s]/gu, ' ') + ' ').includes(' ' + w + ' '))) { st.posts[p.id] = { side, at: p.at, m: null, skip: 1 }; continue; }
            // before kickoff a reply to an account or a score is a prediction (brands run contests), not a mood
            if (pre && (/^\s*@/.test(p.text) || /\d\s*[-/:]\s*\d/.test(p.text.replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d))))) { st.posts[p.id] = { side, at: p.at, m: null, skip: 1 }; continue; }
            // the side it cheers for: its own flag or nickname keeps it, the other side's moves it there, both or neither keep the search's
            const mine = cheers(p.text, ISO[m[side].id]), theirs = cheers(p.text, ISO[m[other].id]);
            const to = theirs && !mine ? other : side;
            if (mine && theirs) { st.posts[p.id] = { side, at: p.at, m: null, skip: 1 }; continue; }
            const md = mood(p.text); st.posts[p.id] = { side: to, at: p.at, m: md }; fresh++;
            if (a.includes('--show')) log(side, md || '—', p.text.replace(/\s+/g, ' ').slice(0, 110));
          }
          log(`#${m.id} ${names[side]}: ${got.length} posts, ${fresh} new`);
          await page.waitForTimeout(4000 + Math.random() * 3000);   // a person's pace between searches
        }
        const keep = Object.entries(st.posts).sort((x, y) => y[1].at - x[1].at).slice(0, 6000); st.posts = Object.fromEntries(keep);
        publish(m, st);
      }
      fs.writeFileSync(STATE, JSON.stringify(state));
      beat();
      if (!a.includes('--loop')) break;
      await new Promise(r => setTimeout(r, EVERY));
      beat();
    } while (Date.now() - t0 < MAX_RUN);
  } finally {
    if (ctx) await ctx.close().catch(() => {});
    unlock();
  }
})().catch(e => { console.error('[mood]', e.message || e); unlock(); process.exit(1); });
