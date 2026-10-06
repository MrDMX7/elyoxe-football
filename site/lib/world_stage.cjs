/* The encyclopedia's indexable player pages (owner 2026-10-06, item 10): /db/player/<id>/ for the world players (db/world.py:
   v1/world/players.json + v1/player/<id>/profile.json) who have no /p/ page, in a scope that earns a page:
     a senior match in 2025/26 or 2026/27 (or the 2025 / 2026 calendar seasons), or an Arabic Wikipedia lead; thin profiles
     (no season, no trophy, no lead) stay on the client page /db/player/?id=.
   A separate stage, not part of out/: the hourly build calls it at the end, and it writes only the pages whose content changed
   into cache/world/delta/, which the runner uploads with `aws s3 cp` (the main `sync --delete` excludes db/player/[0-9]*), so
   ~10,000 pages are never rewritten or re-listed each hour. State in cache/world/ (not shared between machines):
     profiles.json       trimmed profiles of the pages in scope (one file: 20k small files are slow to read on Windows)
     meta.json           the data generation each profile was read under; profiles are re-read only after db/world.py or
                         db/fotmob_profiles.py publish a new generation, FETCH per run
     manifest.json       per page: [content hash, shell (asset) version, last written ms, content changed day]; the runner
                         promotes manifest.next.json to it after a good upload (a failed upload is redone next hour)
     delta/              this run's changed pages     delete.txt   pages that left the scope (S3 keys), guarded at 5 %
   Budgets per run (env), since every upload costs ~0.43 s from the laptop (measured 2026-10-06, whatever the concurrency):
   TIFO_WORLD_NEW new pages (1500), TIFO_WORLD_CHG changed pages (1500: a template change re-draws all ~10k, so it takes a few
   runs), TIFO_WORLD_FETCH profiles (12000), TIFO_WORLD_SHELL pages re-drawn only because the shell changed, oldest first and only
   when 3 days old (1000). A page keeps the hashed assets it was written with (/assets/ is never pruned). Returns the URLs (with
   lastmod) for sitemap-players.xml and the nationality hubs. */
"use strict";
const crypto = require("crypto");
const RECENT = /^(2025\/2026|2026\/2027|2025|2026)$/;
const POS = { "goalkeeper":"حارس مرمى", "keeper":"حارس مرمى", "center back":"قلب دفاع", "centre back":"قلب دفاع", "centre-back":"قلب دفاع", "left back":"ظهير أيسر", "right back":"ظهير أيمن", "left wing-back":"ظهير أيسر",
  "right wing-back":"ظهير أيمن", "defensive midfielder":"وسط دفاعي", "central midfielder":"وسط", "attacking midfielder":"وسط هجومي", "left midfielder":"وسط أيسر", "right midfielder":"وسط أيمن",
  "left winger":"جناح أيسر", "right winger":"جناح أيمن", "striker":"مهاجم", "centre-forward":"مهاجم", "center forward":"مهاجم", "second striker":"مهاجم ثاني", "defender":"مدافع", "midfielder":"وسط", "forward":"مهاجم", "attacker":"مهاجم" };
const posAr = p => { if (!p) return ""; const s = String(p).trim(); return /[؀-ۿ]/.test(s) ? s : POS[s.toLowerCase()] || ""; };
const FOOT = { left:"اليسرى", right:"اليمنى", both:"الثنتين" };
const sha = s => crypto.createHash("sha1").update(s).digest("hex").slice(0, 16);
const dayOf = ms => new Date(ms + 4 * 36e5).toISOString().slice(0, 10);

module.exports = async function(X){
  const { get, page, esc, SITE, CACHE, fs, path, bcLd, finalize, written, NAMES_AR, FMN, WP, PH, phHtml, colors, teamPages, playerPages, S_TEAMS, ASSET_V } = X;
  const env = (k, d) => +(process.env[k] || d);
  const NEW = env("TIFO_WORLD_NEW", 1500), CHG = env("TIFO_WORLD_CHG", 1500), FETCH = env("TIFO_WORLD_FETCH", 12000), SHELL = env("TIFO_WORLD_SHELL", 1000), SHELL_AGE = 3 * 864e5;
  const t0 = Date.now(), DIR = path.join(CACHE, "world"), DELTA = path.join(DIR, "delta"), rj = (f, d) => { try { return JSON.parse(fs.readFileSync(path.join(DIR, f), "utf8")); } catch (e){ return d; } };
  fs.mkdirSync(DIR, { recursive:true }); fs.rmSync(DELTA, { recursive:true, force:true }); fs.mkdirSync(DELTA, { recursive:true });
  const W = await get("world/players.json"), WI = (await get("world/index.json", 2)) || {};
  if (!W || !(W.players || []).length){   // the published pages stay as they are: same manifest, nothing to upload or delete
    const m0 = rj("manifest.json", {}); fs.writeFileSync(path.join(DIR, "manifest.next.json"), JSON.stringify(m0)); fs.writeFileSync(path.join(DIR, "delete.txt"), "");
    Object.keys(m0).forEach(id => written(`/db/player/${id}`)); console.error("world stage: no world/players.json; kept the published pages");
    return { urls:Object.keys(m0).map(id => ({ u:`/db/player/${id}/`, lm:m0[id][3] })), stats:{ skipped:true } }; }
  const gen = `${W.generated || ""}|${X.fmGen || ""}`;
  const CLUB = {}; (WI.clubs || []).forEach(c => { CLUB[c[0]] = c[1]; });
  const prof = rj("profiles.json", {}), meta = Object.assign({ done:{} }, rj("meta.json", {})), man = rj("manifest.json", {});
  // scope, measured 2026-10-06 on all 64,642 profiles: of 61,679 world players 15,513 have /p/; of the other 46,166, 37,305 played in
  // 2025/26-2026/27 but only 9,881 of those (or with an Arabic Wikipedia lead) carry an Arabic name. Arabic search needs the Arabic name,
  // so the Latin-only 27,425 stay on the client page until names/build_names.py names them (the scope grows with it).
  const AR = /[؀-ۿ]/, hasAr = p => AR.test(p[1] || "") || !!((NAMES_AR[p[0]] || {}).ar);
  const cand = W.players.filter(p => !playerPages.has(String(p[0])) && hasAr(p)), byId = {}; cand.forEach(p => { byId[p[0]] = p; });
  // ---- 1. profiles: never read under this generation first (new players), then the rest, FETCH per run
  const need = cand.filter(p => meta.done[p[0]] !== gen).sort((a, b) => (meta.done[a[0]] ? 1 : 0) - (meta.done[b[0]] ? 1 : 0)).slice(0, FETCH).map(p => p[0]);
  let fetched = 0, failed = 0;
  const trim = p => ({ bio:p.bio || {}, s:(((p.career || {}).senior || {}).seasons || []).map(s => s.slice(0, 7)), n:(((p.career || {}).national || (p.career || {})["national team"] || {}).seasons || []).map(s => s.slice(0, 7)),
    t:(p.trophies || []).filter(t => (t[4] || []).length).map(t => [t[0], t[1], t[3], t[4]]) });
  const scoped = (id, t) => { const apps = t.s.filter(s => RECENT.test(String(s[0]))).reduce((a, s) => a + (+s[3] || 0), 0); return apps > 0 || !!WP[id]; };
  const thin = (id, t) => !t.s.length && !t.t.length && !WP[id];
  await X.pool(need, 48, async id => { const p = await get(`player/${id}/profile.json`, 2); if (!p){ failed++; return; } fetched++; const t = trim(p); meta.done[id] = gen;
    if (scoped(id, t) && !thin(id, t)) prof[id] = t; else delete prof[id]; });
  for (const id of Object.keys(prof)) if (!byId[id]) delete prof[id];   // left the world list, or got a /p/ page
  // ---- 2. render every page in scope; write the new and the changed (budgets above)
  const inScope = Object.keys(prof), clubOf = id => +(byId[id] || [])[3] || +(prof[id].bio || {}).team || 0;
  const mates = {}; inScope.forEach(id => { const c = clubOf(id); if (c) (mates[c] = mates[c] || []).push(id); });
  const nameOf = id => { const a = (NAMES_AR[id] || {}).ar, w = (byId[id] || [])[1]; return a || (w && /[؀-ۿ]/.test(w) ? w : "") || ""; };
  const latin = id => (byId[id] || [])[2] || ((prof[id] || {}).bio || {}).name || "";
  const tname = (id, fb) => (S_TEAMS[id] && S_TEAMS[id].name_ar) || (FMN.teams || {})[id] || (CLUB[id] && /[؀-ۿ]/.test(CLUB[id]) ? CLUB[id] : "") || fb || CLUB[id] || "";
  const tlink = (id, fb) => { const n = tname(id, fb); if (!id) return esc(n); const h = teamPages.has(+id) ? `/t/${id}/` : `/db/club/?id=${id}`; return `<a href="${h}">${/[؀-ۿ]/.test(n) ? esc(n) : `<span class="lat">${esc(n)}</span>`}</a>`; };
  const eur = v => v >= 1e6 ? `<span class="num">€${Math.round(v / 1e5) / 10}</span> مليون` : `<span class="num">€${Math.round(v / 1e3)}</span> ألف`;
  const ageOf = born => { if (!born || born < "1900") return null; const b = Date.parse(born), n = new Date(); let a = n.getUTCFullYear() - +born.slice(0, 4); if (n.getUTCMonth() + 1 < +born.slice(5, 7) || (n.getUTCMonth() + 1 === +born.slice(5, 7) && n.getUTCDate() < +born.slice(8, 10))) a--; return isNaN(b) ? null : a; };
  function body(id){
    const t = prof[id], b = t.bio || {}, nm = nameOf(id), la = latin(id), club = clubOf(id), cn = (FMN.countries || {})[b.cc] || "", pos = posAr(b.pos), age = ageOf(b.born);
    const title = nm || la, wiki = WP[id];
    const bio = [pos && ["المركز", esc(pos)], age != null && ["العمر", `<span class="num">${age}</span> سنة <small class="num">${esc(b.born)}</small>`], b.h && ["الطول", `<span class="num">${b.h}</span> سم`], b.foot && FOOT[b.foot] && ["القدم", FOOT[b.foot]],
      cn && ["الجنسية", esc(cn)], club && ["النادي", tlink(club)], b.shirt && ["الرقم", `<span class="num">${b.shirt}</span>`], b.mv && ["القيمة السوقية", eur(b.mv)], b.contract && ["نهاية العقد", `<span class="num">${esc(String(b.contract).slice(0, 7))}</span>`], b.loan && ["الحالة", "معار"]].filter(Boolean);
    const seasons = t.s.filter(s => s[1] || s[2]), tot = seasons.reduce((a, s) => [a[0] + (+s[3] || 0), a[1] + (+s[4] || 0)], [0, 0]);
    const tbl = (rows, h) => rows.length ? `<section class="grp"><div class="gh"><h2>${h}</h2></div><div class="card"><div class="tblw"><table class="tbl"><thead><tr><th>الموسم</th><th class="tm">الفريق</th><th>مباريات</th><th>أهداف</th><th>صناعة</th><th>التقييم</th></tr></thead><tbody>` +
      rows.map(s => `<tr><td>${esc(s[0])}</td><td class="tm">${tlink(s[1], s[2])}</td><td>${s[3] ?? ""}</td><td>${s[4] ?? ""}</td><td>${s[5] ?? ""}</td><td>${s[6] ? esc(s[6]) : ""}</td></tr>`).join("") + "</tbody></table></div></div></section>" : "";
    const tro = t.t.length ? `<section class="grp"><div class="gh"><h2>ألقابه</h2><span class="nn"><span class="num">${t.t.reduce((a, x) => a + x[3].length, 0)}</span> لقب</span></div><div class="card">${t.t.map(x => `<div class="row"><span class="rt"><b>${esc(x[2] || "")}</b><small>${tname(x[0], x[1]) ? esc(tname(x[0], x[1])) + " · " : ""}${esc(x[3].join("، "))}</small></span><span class="rv">${x[3].length}</span></div>`).join("")}</div></section>` : "";
    const mm = (mates[club] || []).filter(x => x !== id).sort((a, c) => (prof[c].s[0] ? +prof[c].s[0][3] || 0 : 0) - (prof[a].s[0] ? +prof[a].s[0][3] || 0 : 0)).slice(0, 12);
    const mateHtml = mm.length ? `<section class="grp"><div class="gh"><h2>لاعبين في ${esc(tname(club))}</h2></div><div class="card">${mm.map(x => `<a class="row" href="/db/player/${x}/"><span class="rt"><b>${nameOf(x) ? esc(nameOf(x)) : `<span class="lat">${esc(latin(x))}</span>`}</b><small>${esc(posAr((prof[x].bio || {}).pos))}</small></span></a>`).join("")}</div></section>` : "";
    const lead = wiki && wiki[1] ? `<p class="pwiki">${esc(wiki[1].length > 700 ? wiki[1].slice(0, wiki[1].lastIndexOf(" ", 690)) + "…" : wiki[1])} <a href="https://ar.wikipedia.org/wiki/${encodeURIComponent(String(wiki[0]).replace(/ /g, "_"))}" rel="noopener">ويكيبيديا</a></p>` : "";
    const n = (k, w) => k === 1 ? w[0] + (w[3] ? " " + w[3] : "") : k === 2 ? w[1] : `${k} ${k >= 3 && k <= 10 ? w[2] : w[0]}`;   // 1 · 2 · 3-10 · 11+
    const sum = seasons.length ? `<p class="intro">${esc(title)} ${pos ? esc(pos) + " " : ""}${club ? "في " + esc(tname(club)) : ""}${cn ? "، من " + esc(cn) : ""}${age != null ? "، عمره " + age + " سنة" : ""}. لعب ${n(tot[0], ["مباراة", "مباراتين", "مباريات", "وحدة"])}${tot[1] ? ` وسجّل ${n(tot[1], ["هدف", "هدفين", "أهداف", "واحد"])}` : ""} في ${n(seasons.length, ["موسم", "موسمين", "مواسم", "واحد"])}.</p>` : "";
    const html = `<p class="crumbs"><a href="/db/">الموسوعة</a>${club ? "، " + tlink(club) : ""}</p>${nm ? `<h1>${esc(nm)}</h1>` : `<h1 class="lat">${esc(la)}</h1>`}<p class="season">${[pos && esc(pos), club && esc(tname(club)), cn && `<a href="/db/players/${esc(String(b.cc).toLowerCase())}/">${esc(cn)}</a>`, nm && la && `<span class="lat">${esc(la)}</span>`].filter(Boolean).join(" · ")}</p>` +
      `<div class="sx">${sum}${lead}${bio.length ? `<section class="grp"><div class="gh"><h2>بطاقته</h2></div><div class="card"><dl class="bio">${bio.map(r => `<div><dt>${r[0]}</dt><dd>${r[1]}</dd></div>`).join("")}</dl></div></section>` : ""}` +
      tbl(seasons, "مسيرته موسم بموسم") + tbl(t.n.filter(s => s[1] || s[2]), "مع المنتخب") + tro + mateHtml + `<p class="src">المسيرة والبطاقة من FotMob${lead ? "، والنبذة من ويكيبيديا" : ""}. <a href="/db/player/?id=${id}">مبارياته وانتقالاته في الموسوعة</a></p></div>`;
    const person = Object.assign({ "@context":"https://schema.org", "@type":"Person", name:title, url:`${SITE}/db/player/${id}/`, jobTitle:"لاعب كرة قدم" }, nm && la ? { alternateName:la } : {}, b.born && b.born >= "1900" ? { birthDate:b.born } : {},
      b.h ? { height:{ "@type":"QuantitativeValue", value:b.h, unitCode:"CMT" } } : {}, cn ? { nationality:{ "@type":"Country", name:cn } } : {}, club ? { affiliation:{ "@type":"SportsTeam", name:tname(club) } } : {}, PH[id] ? { image:`${SITE}/v1/ph/${id}.webp` } : {});
    return { title:`${title}: مسيرته وأرقامه${club ? " مع " + tname(club) : ""} | تيفو`, desc:`${title}${pos ? "، " + pos : ""}${club ? " في " + tname(club) : ""}${cn ? " من " + cn : ""}${age != null ? "، عمره " + age + " سنة" : ""}: مسيرته موسم بموسم بالمباريات والأهداف${t.t.length ? "، وألقابه" : ""}${wiki ? "، ونبذة من ويكيبيديا" : ""}.`,
      html, ld:[bcLd([["الموسوعة", "/db/"], club && teamPages.has(+club) && [tname(club), `/t/${club}/`], [title, `/db/player/${id}/`]]), person], club };   // a crumb needs an indexable page: the club's only when it has one
  }
  const next = {}, now = Date.now(), urls = [], fresh = []; let nNew = 0, nChg = 0, nShell = 0, nKeep = 0, bytes = 0;
  const shellOld = inScope.filter(id => man[id] && man[id][1] !== ASSET_V && now - man[id][2] > SHELL_AGE).sort((a, b) => man[a][2] - man[b][2]), shellOK = new Set(shellOld.slice(0, SHELL));
  // new pages first (the best known first: a Wikipedia lead, then the most matches in 2025/26-2026/27), then the ones written
  // longest ago: a page held back by a budget is the first one written next run
  const apps = id => prof[id].s.filter(s => RECENT.test(String(s[0]))).reduce((a, s) => a + (+s[3] || 0), 0) + (WP[id] ? 1e4 : 0);
  const order = inScope.slice().sort((a, b) => (man[a] ? man[a][2] : 0) - (man[b] ? man[b][2] : 0) || (man[a] || man[b] ? 0 : apps(b) - apps(a)));
  for (const id of order){
    const P = body(id), h = sha(P.title + P.desc + P.html + JSON.stringify(P.ld)), m = man[id];
    const isNew = !m, changed = m && m[0] !== h, shell = m && !changed && shellOK.has(id);
    if (isNew && nNew >= NEW) continue;   // the first run spreads the backlog over a few hours; out of scope until written
    if (changed && nChg >= CHG){ next[id] = m; urls.push({ u:`/db/player/${id}/`, lm:m[3] }); written(`/db/player/${id}`); continue; }   // a template change re-draws every page: over a few runs
    if (isNew || changed || shell){
      const html = finalize(page({ path:`/db/player/${id}/`, page:"ref", title:P.title, desc:P.desc, ld:P.ld, art:colors[P.club] ? [colors[P.club], [colors[P.club][1] || colors[P.club][0], colors[P.club][0]]] : null, heroExtra:PH[id] ? phHtml(id, PH[id], colors[P.club]) : "", body:P.html }));
      const f = path.join(DELTA, "db/player", id, "index.html"); fs.mkdirSync(path.dirname(f), { recursive:true }); fs.writeFileSync(f, html); bytes += html.length;
      next[id] = [h, ASSET_V, now, changed || isNew ? dayOf(now) : m[3]]; if (isNew) nNew++; else if (changed) nChg++; else nShell++; if (isNew || changed) fresh.push(`/db/player/${id}/`);
    } else { next[id] = m; nKeep++; }
    urls.push({ u:`/db/player/${id}/`, lm:next[id][3] }); written(`/db/player/${id}`);
  }
  // pages that left the scope: deleted from S3 by the runner, unless that is more than 5 % of them (a data glitch, not a decision)
  const gone2 = Object.keys(man).filter(id => !next[id]);   // a page already published is never held back by the NEW budget, so these left the scope
  const guard = gone2.length > Math.max(50, Object.keys(man).length * .05);
  if (guard){ console.error(`world stage: ${gone2.length} pages would leave the scope (more than 5 %); kept this run`); gone2.forEach(id => { next[id] = man[id]; urls.push({ u:`/db/player/${id}/`, lm:man[id][3] }); written(`/db/player/${id}`); }); }
  fs.writeFileSync(path.join(DIR, "delete.txt"), guard ? "" : gone2.map(id => `db/player/${id}/index.html`).join("\n"));
  fs.writeFileSync(path.join(DIR, "profiles.json"), JSON.stringify(prof)); fs.writeFileSync(path.join(DIR, "meta.json"), JSON.stringify(Object.assign(meta, { gen, at:new Date().toISOString() })));
  fs.writeFileSync(path.join(DIR, "manifest.next.json"), JSON.stringify(next));
  const st = { candidates:cand.length, fetched, failed, waiting:cand.filter(p => meta.done[p[0]] !== gen).length, scope:inScope.length, pages:Object.keys(next).length, new:nNew, changed:nChg, shell:nShell, kept:nKeep, deleted:guard ? 0 : gone2.length, mb:+(bytes / 1e6).toFixed(1), s:+((Date.now() - t0) / 1000).toFixed(1) };
  console.log("world stage:", JSON.stringify(st));
  // the nationality hubs build.cjs writes into out/ (/db/players/<cc>/): every published page, by country, then club
  const hubs = {}; Object.keys(next).forEach(id => { const t = prof[id]; if (!t) return; const cc = (t.bio || {}).cc || "XXX", club = clubOf(id);
    (hubs[cc] = hubs[cc] || []).push([id, nameOf(id) || latin(id), club, tname(club), posAr((t.bio || {}).pos)]); });
  return { urls, fresh, stats:st, hubs };
};
