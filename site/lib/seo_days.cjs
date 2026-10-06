/* «مباريات اليوم والقنوات الناقلة والمعلقين» (owner 2026-10-06, item 9): the pages a searcher lands on.
     /today/  /tomorrow/  /yesterday/      the evergreen three («مباريات اليوم», «مباريات الغد», «نتائج مباريات أمس»)
     /matches/<yyyy-mm-dd>/                 one archive page per UAE day, from the first all-day file (2026-09-30) to tomorrow
     /matches/                              the archive hub
     /t/<id>/today/                         «مباراة الهلال اليوم» for the biggest clubs and the Arab national teams
   Every match of the day grouped by competition (ours first, then the Arab leagues, the big leagues, the rest: compute/allday.py's
   order), the UAE/Saudi/Egyptian/Moroccan kick-off times in the HTML, each competition's channels per country, each match's
   channel and commentator (v1/tv/<ymd>.json), status and score. JSON-LD: BreadcrumbList, FAQPage (the visible FAQ) and a
   SportsEvent per match whose venue we know (Google's Event needs a location with an address; the other matches carry none
   rather than a guessed one). Rows are rendered by src/days.js, which the browser re-runs for live scores and a new day.
   Called by build.cjs with its helpers; returns the URLs for sitemap-days.xml. Writes through page(), so it takes whatever shell
   page() draws (v3 now, v5 later). */
"use strict";
const TD = require("../src/days.js");
const FIRST = "20260930";   // the first v1/all/<ymd>.json (and v1/tv/) the poller wrote

module.exports = async function(X){
  const { get, pool, write, page, esc, SITE, CACHE, fs, path, bcLd, comps, BCBY, LG365, matchSum, details, matchPages, logoOk, ogOf, teamPages, byTeam, S_TEAMS } = X;
  const t0 = Date.now(), out = { urls:[], pages:0, events:0, bytes:0 };
  const today = TD.uaeYmd(0), tomorrow = TD.shift(today, 1), yesterday = TD.shift(today, -1);
  const days = []; for (let d = FIRST; d <= tomorrow; d = TD.shift(d, 1)) days.push(d);
  // a finished day's files never change again: kept in cache/days/ after the first read (the hourly build fetches ~4 files, not 2 a day forever)
  const CD = path.join(CACHE, "days"); fs.mkdirSync(CD, { recursive:true });
  const cached = async (p, ymd) => { const f = path.join(CD, p.replace(/\//g, "-")); const old = ymd < yesterday;
    if (old && fs.existsSync(f)) try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch (e){}
    const j = await get(p, 2); if (j && old) fs.writeFileSync(f, JSON.stringify(j)); return j; };
  const docs = {}, tvs = {};
  await pool(days, 6, async d => { const [a, t] = await Promise.all([cached(`all/${d}.json`, d), cached(`tv/${d}.json`, d)]); docs[d] = a; tvs[d] = (t && t.matches) || {}; });
  const keys = {}; comps.forEach(c => { keys[c.id] = c.key; });
  const l365 = [...LG365].map(Number);
  const ctxOf = d => ({ ymd:d, keys, l365, bc:BCBY, tv:tvs[d], tz:"Asia/Dubai", hasPage:id => matchPages.has(String(id)), logoOk });
  const ld0 = (name, url) => bcLd([["مباريات اليوم", "/today/"], name && [name, url]]);

  // ---- the parts of a day page
  const featured = doc => { const all = []; ((doc && doc.leagues) || []).forEach(lg => (lg.matches || []).forEach(m => all.push([lg, m]))); return all; };
  const nm = t => (t && t[1]) || "";
  const venueOf = id => { const m = details.get(+id) || details.get(String(id)) || matchSum.get(+id); return m && m.venue && (m.venue.name_ar || m.venue.name_en || m.venue.name) ? m.venue : null; };
  const compName = lg => lg.name_ar || lg.name || "";
  // a SportsEvent per match with a known venue (our competitions): name, start/end, status, place with address, teams, organizer, image
  const event = (lg, m) => { const id = String(m.id); if (!/^\d+$/.test(id)) return null; const v = venueOf(id); if (!v || !m.utc) return null;
    const H = nm(m.home), A = nm(m.away), t = Date.parse(m.utc), vn = v.name_ar || v.name_en || v.name;
    const st = { postponed:"https://schema.org/EventPostponed", cancelled:"https://schema.org/EventCancelled" }[m.status] || "https://schema.org/EventScheduled";
    const teams = [{ "@type":"SportsTeam", name:H }, { "@type":"SportsTeam", name:A }], played = m.status === "finished" && m.home[2] != null;
    const city = String(v.city || "").split(",")[0].trim();   // FotMob cuts the city at 32 characters («Ciudad de Córdoba, Provincia de »)
    const addr = Object.assign({ "@type":"PostalAddress" }, city ? { addressLocality:city } : {}, v.in_uae ? { addressCountry:"AE" } : v.country ? { addressCountry:v.country } : {});
    if (!addr.addressLocality && !addr.addressCountry) addr.streetAddress = vn;   // Google wants an address; the stadium's name is the one we have
    return { "@context":"https://schema.org", "@type":"SportsEvent", name:`${H} ضد ${A}`, url:`${SITE}/m/${id}/`, startDate:m.utc, ...(m.tbd ? {} : { endDate:new Date(t + 2 * 36e5).toISOString().replace(".000", "") }), sport:"Football",
      eventStatus:st, eventAttendanceMode:"https://schema.org/OfflineEventAttendanceMode", location:{ "@type":"StadiumOrArena", name:vn, address:addr },
      image:[ogOf(id)], description:[played ? `انتهت ${H} ${m.home[2]} - ${m.away[2]} ${A}` : `${H} ضد ${A}`, compName(lg)].join(" · "), homeTeam:teams[0], awayTeam:teams[1], competitor:teams, performer:teams,
      organizer:{ "@type":"SportsOrganization", name:compName(lg), url:keys[lg.id] ? `${SITE}/c/${keys[lg.id]}/` : SITE } }; };
  const chanText = (lg, m, ctx) => { const c = TD.chan(m, ctx, true); const tvT = c ? [c.ch && `على ${c.ch}`, c.v && `ويعلّق عليها ${c.v}`].filter(Boolean).join(" ") : "";
    if (tvT) return tvT;
    const per = TD.ZONES.map(z => { const e = BCBY[z[0]] && BCBY[z[0]][String(lg.id)]; return e && e.b && e.b.length ? `في ${z[1]} على ${e.b[0][0]}` : ""; }).filter(Boolean);
    return per.length ? per.join("، ") : ""; };
  const sc = m => `<span class="num" dir="rtl">${m.home[2]} - ${m.away[2]}</span>`;
  // the day's headline matches: ours first, one per competition, nothing postponed or cancelled
  const headline = (doc, past) => { const seen = {}, out = [], all = featured(doc).filter(([lg, m]) => past ? m.status === "finished" && m.home[2] != null : !/postponed|cancelled|abandoned/.test(m.status));
    for (const pass of [x => x[0].ours || x[1].ours, x => TD.isArab(x[0]), () => true]) for (const x of all){ if (out.length >= 3) break; if (seen[x[0].id] || !pass(x)) continue; seen[x[0].id] = 1; out.push(x); }
    return out; };
  function intro(d, doc, kindWord, past){
    const c = TD.counts(doc), top = headline(doc, past);
    if (!c.n) return `<p class="intro">ما في مباريات منشورة لهاليوم للحين.</p>`;
    const lines = top.map(([lg, m]) => past ? `${esc(nm(m.home))} ${sc(m)} ${esc(nm(m.away))} في ${esc(compName(lg))}`
      : `${esc(nm(m.home))} ضد ${esc(nm(m.away))} في ${esc(compName(lg))}${m.utc && !m.tbd ? ` (<span class="num">${TD.hm(m.utc, "Asia/Dubai")}</span> بتوقيت الإمارات)` : ""}`);
    return `<p class="intro">${past ? "نتائج" : "جدول"} مباريات ${esc(kindWord)} ${esc(TD.fullDate(d))}: ${TD.nMatches(c.n)} في <span class="num">${c.leagues}</span> بطولة.${lines.length ? ` ${past ? "أبرز النتائج" : "أبرزها"} ${lines.join("، و")}.` : ""}${past ? "" : " ومع كل مباراة توقيتها في الإمارات والسعودية ومصر والمغرب، والقناة الناقلة والمعلق لما ينعلن."}</p>`;
  }
  function faq(d, doc, kindWord, past, ctx){
    const c = TD.counts(doc), all = featured(doc), qa = [];
    if (c.n) qa.push([past ? `كم مباراة انلعبت يوم ${TD.fullDate(d, true)}؟` : `كم مباراة ${kindWord || "يوم " + TD.fullDate(d, true)}؟`, `يوم ${TD.fullDate(d)} ${past ? "انلعبت" : "فيه"} ${TD.nMatches(c.n, true)} في ${c.leagues} بطولة، من الدوريات العربية والكبيرة لين البطولات القارية والودية.`]);
    const top = past ? [] : headline(doc, false).filter(([lg, m]) => m.status === "scheduled" || m.status === "live" || m.status === "ht").slice(0, 2);
    top.forEach(([lg, m]) => { const t = chanText(lg, m, ctx), H = nm(m.home), A = nm(m.away);
      if (t) qa.push([`وين تنقل مباراة ${H} و${A}؟`, `مباراة ${H} و${A} في ${compName(lg)}: ${t}.`]);
      if (m.utc && !m.tbd) qa.push([`متى مباراة ${H} و${A}؟`, `${TD.fullDate(TD.ymdIn(m.utc, "Asia/Dubai"))} ${TD.clocksText(m.utc)}.`]); });
    const voices = []; all.forEach(([lg, m]) => { const x = TD.chan(m, ctx, true); if (x && x.v && voices.length < 4) voices.push(`${x.v} على ${nm(m.home)} و${nm(m.away)}${x.ch ? " (" + x.ch + ")" : ""}`); });
    if (voices.length) qa.push([past ? `منو علّق على مباريات ${TD.dayMonth(d)}؟` : `منو يعلّق على مباريات ${kindWord}؟`, `${voices.join("، و")}.`]);
    else if (!past && d >= today) qa.push([`متى ينزل جدول المعلقين؟`, `جدول القنوات الناقلة والمعلقين ينزل عادة بعد نص الليل بتوقيت الإمارات، ويطلع في الصفحة أول ما ينزل.`]);
    return qa;
  }
  const faqHtml = qa => qa.length ? `<section class="grp faq"><div class="gh"><h2>أسئلة عن المباريات</h2></div><div class="card">${qa.map(q => `<details><summary>${esc(q[0])}</summary><p>${esc(q[1])}</p></details>`).join("")}</div></section>` : "";
  const faqLd = qa => qa.length ? { "@context":"https://schema.org", "@type":"FAQPage", mainEntity:qa.map(q => ({ "@type":"Question", name:q[0], acceptedAnswer:{ "@type":"Answer", text:q[1] } })) } : null;
  const nav = (d, kind) => { const L = (h, t, on) => on ? `<span aria-current="page">${t}</span>` : `<a href="${h}">${t}</a>`;
    if (kind !== "date") return `<nav class="dnav" aria-label="الأيام">${L("/yesterday/", "أمس", kind === "yesterday")}${L("/today/", "اليوم", kind === "today")}${L("/tomorrow/", "بكرة", kind === "tomorrow")}${L("/matches/", "كل الأيام")}</nav>`;
    const p = TD.shift(d, -1), n = TD.shift(d, 1);
    return `<nav class="dnav" aria-label="الأيام">${p >= FIRST ? `<a href="/matches/${TD.iso(p)}/" rel="prev">${esc(TD.dayMonth(p))}</a>` : ""}<span aria-current="page">${esc(TD.dayMonth(d))}</span>${n <= tomorrow ? `<a href="/matches/${TD.iso(n)}/" rel="next">${esc(TD.dayMonth(n))}</a>` : ""}${L("/today/", "مباريات اليوم")}${L("/matches/", "كل الأيام")}</nav>`; };
  function dayPage(d, kind){
    const doc = docs[d]; if (!doc) return false;
    const ctx = ctxOf(d), c = TD.counts(doc), past = d < today, full = TD.fullDate(d);
    const W = { today:["مباريات اليوم", "اليوم"], tomorrow:["مباريات الغد", "بكرة"], yesterday:["نتائج مباريات أمس", "أمس"], date:["مباريات", d === today ? "اليوم" : d === tomorrow ? "بكرة" : d === yesterday ? "أمس" : ""] }[kind];
    const h1 = `${W[0]} ${full}`, p = kind === "date" ? `/matches/${TD.iso(d)}/` : `/${kind}/`;
    const title = kind === "today" ? `مباريات اليوم ${full} والقنوات الناقلة والمعلقين | تيفو` : kind === "tomorrow" ? `مباريات الغد ${full} والقنوات الناقلة والمعلقين | تيفو`
      : kind === "yesterday" ? `نتائج مباريات أمس ${full} | تيفو` : past ? `نتائج مباريات ${full} | تيفو` : `مباريات ${full}: المواعيد والقنوات الناقلة والمعلقين | تيفو`;
    const what = `${TD.nMatches(c.n, true)} في ${c.leagues} بطولة`;
    const desc = past ? `نتائج مباريات ${kind === "yesterday" ? "أمس " : ""}${full}: ${what} بالنتيجة النهائية، والقنوات اللي نقلتها والمعلقين.`
      : `جدول مباريات ${kind === "today" ? "اليوم " : kind === "tomorrow" ? "الغد " : ""}${full}: ${what} بتوقيت الإمارات والسعودية ومصر والمغرب، مع القنوات الناقلة والمعلقين والنتائج مباشرة.`;
    const qa = faq(d, doc, W[1] || TD.dayMonth(d), past, ctx);
    const evs = []; featured(doc).forEach(([lg, m]) => { if (evs.length < 60){ const e = event(lg, m); if (e) evs.push(e); } });
    const dctx = { keys:Object.fromEntries(((doc.leagues || []).filter(lg => lg.ours && keys[lg.id]).map(lg => [lg.id, keys[lg.id]]))), l365, tv:tvs[d] };
    const body = `<p class="crumbs"><a href="/matches/">جدول المباريات</a></p><h1 id="dh1">${esc(h1)}</h1><p class="season"><span id="dsub">${TD.nMatches(c.n)} في <span class="num">${c.leagues}</span> بطولة · المواعيد بتوقيت بلدك</span></p>` +
      `<div class="sx" id="days" data-ymd="${d}" data-kind="${kind}">${nav(d, kind)}${intro(d, doc, W[1] || "", past)}` +
      (d >= today ? `<div class="seg dfil" id="dfil" role="group" aria-label="اعرض"><button type="button" data-f="all" aria-pressed="true">الكل</button><button type="button" data-f="live" id="dflive" aria-pressed="false"${c.live ? "" : " hidden"}>مباشر الحين<span class="num">${c.live || ""}</span></button><button type="button" data-f="arab" aria-pressed="false">العرب</button></div>` : "") +
      `<div id="dlist">${TD.body(doc, ctx)}</div>${faqHtml(qa)}<p class="lk"><a class="btn" href="/commentators/">منو يعلّق اليوم وبكرة؟</a> <a class="btn" href="/watch/">وين تنقل كل بطولة</a> <a class="btn" href="/week/">مباريات الأسبوع</a></p></div>` +
      `<script type="application/json" id="dctx">${JSON.stringify(dctx).replace(/</g, "\\u003c")}</script>`;
    const html = page({ path:p, page:"days", nav:"home", title, desc, body, ld:[ld0(kind === "date" ? `مباريات ${TD.dayMonth(d)}` : W[0], p), faqLd(qa)].filter(Boolean).concat(evs), noindex:!c.n });
    write(p.slice(1) + "index.html", html); out.pages++; out.events += evs.length; out.bytes += Buffer.byteLength(html);
    if (c.n) out.urls.push(p); return true;
  }
  [["today", today], ["tomorrow", tomorrow], ["yesterday", yesterday]].forEach(([k, d]) => dayPage(d, k));
  days.forEach(d => dayPage(d, "date"));

  // ---- /matches/: every day, newest first, with its count
  { const rows = days.slice().reverse().filter(d => docs[d]).map(d => { const c = TD.counts(docs[d]); return `<a class="row" href="/matches/${TD.iso(d)}/"><span class="rt">${esc(TD.fullDate(d))}${d === today ? " <small>اليوم</small>" : d === tomorrow ? " <small>بكرة</small>" : d === yesterday ? " <small>أمس</small>" : ""}</span><span class="rv num">${c.n}</span></a>`; }).join("");
    const html = page({ path:"/matches/", page:"days", nav:"home", title:"جدول مباريات كرة القدم يوم بيوم: المواعيد والنتائج والقنوات | تيفو", desc:"كل مباريات كل يوم: المواعيد بتوقيت الإمارات والسعودية ومصر والمغرب، والنتائج، والقنوات الناقلة والمعلقين. مباريات اليوم وبكرة وأمس وأرشيف الأيام اللي فاتت.",
      ld:[bcLd([["جدول المباريات", "/matches/"]])], body:`<h1>جدول المباريات يوم بيوم</h1><p class="season">من ${esc(TD.fullDate(FIRST))} لين بكرة</p><div class="sx">${nav(today, "today")}<section class="grp"><div class="gh"><h2>الأيام</h2><span class="nn">عدد المباريات</span></div><div class="card">${rows}</div></section></div>` });
    write("matches/index.html", html); out.pages++; out.urls.push("/matches/"); }

  // ---- «مباراة <فريق> اليوم»: the biggest clubs and the Arab national teams (ids that have a team page)
  const BIG = X.bigTeams || [];
  const docToday = docs[today], docTom = docs[tomorrow], ctxT = ctxOf(today);
  const findIn = (doc, id) => { for (const lg of (doc && doc.leagues) || []) for (const m of lg.matches || []) if (+m.home[0] === id || +m.away[0] === id) return [lg, m]; return null; };
  // a fixture or result from the site's own files, drawn by the same renderer (its day and the competition above it)
  const mBlock = (h, m) => { const lg = { id:m.comp, name_ar:m.comp_name_ar || X.R.compName(X.index, m.comp), ours:true }, row = TD.fromMatch(m);
    return `<section class="grp dl"><div class="gh"><h2>${esc(h)}</h2><span class="nn">${esc(lg.name_ar || "")}</span></div><div class="card">${TD.row(row, lg, ctxT)}</div></section>`; };
  let nT = 0;
  for (const id of BIG){
    if (!teamPages.has(id) || !S_TEAMS[id]) continue;
    const nat = !!(S_TEAMS[id].country && S_TEAMS[id].country.national), tn0 = S_TEAMS[id].name_ar || S_TEAMS[id].name; if (!tn0) continue;
    const tn = nat ? "منتخب " + tn0 : tn0;   // searchers write «مباراة منتخب الإمارات اليوم»
    const hit = findIn(docToday, id), nextM = !hit && byTeam.get(id) ? byTeam.get(id).ms.filter(m => m.status === "scheduled" && Date.parse(m.kickoff_utc) > Date.now()).sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc))[0] : null;
    const lastM = byTeam.get(id) ? byTeam.get(id).ms.filter(m => m.status === "finished" && m.score).sort((a, b) => b.kickoff_utc.localeCompare(a.kickoff_utc))[0] : null;
    let lead = "", block = "", qa = [], evs = [];
    if (hit){ const [lg, m] = hit, opp = +m.home[0] === id ? nm(m.away) : nm(m.home), ct = chanText(lg, m, ctxT);
      block = `<section class="grp dl"><div class="gh"><h2>${esc(compName(lg))}</h2></div><div class="card">${TD.row(m, lg, ctxT)}</div>${TD.bcLine(lg.id, ctxT)}</section>`;
      lead = m.status === "finished" && m.home[2] != null ? `لعب ${esc(tn)} اليوم ${esc(TD.fullDate(today))} ضد ${esc(opp)} في ${esc(compName(lg))}، وانتهت ${esc(nm(m.home))} ${sc(m)} ${esc(nm(m.away))}.`
        : `${esc(tn)} يلعب اليوم ${esc(TD.fullDate(today))} ضد ${esc(opp)} في ${esc(compName(lg))}${m.utc && !m.tbd ? "، " + esc(TD.clocksText(m.utc)) : ""}${ct ? "، " + esc(ct) : ""}.`;
      qa = [[`متى مباراة ${tn} اليوم؟`, m.utc && !m.tbd ? `${tn} ضد ${opp} ${TD.clocksText(m.utc)}.` : `${tn} ضد ${opp}، والساعة ما تحددت للحين.`]].concat(ct ? [[`وين تنقل مباراة ${tn} اليوم؟`, `مباراة ${tn} و${opp}: ${ct}.`]] : []);
      const e = event(lg, m); if (e) evs.push(e); }
    else {
      lead = `${esc(tn)} ما يلعب اليوم ${esc(TD.fullDate(today))}.` + (nextM ? ` مباراته الياية ضد ${esc(nextM.home.id === id ? (nextM.away.name_ar || nextM.away.name) : (nextM.home.name_ar || nextM.home.name))} ${esc(TD.fullDate(TD.ymdIn(nextM.kickoff_utc, "Asia/Dubai")))}${nextM.time_tbd ? "" : "، " + esc(TD.clocksText(nextM.kickoff_utc))}.` : "");
      if (nextM) block = mBlock("مباراته الياية", nextM);
      if (nextM) qa = [[`متى مباراة ${tn} الياية؟`, `${tn} يلعب ${TD.fullDate(TD.ymdIn(nextM.kickoff_utc, "Asia/Dubai"))}${nextM.time_tbd ? "" : " " + TD.clocksText(nextM.kickoff_utc)}.`]];
    }
    if (lastM) block += mBlock("آخر نتيجة", lastM);
    const tomHit = !hit && findIn(docTom, id);
    if (tomHit) block += `<section class="grp dl"><div class="gh"><h2>بكرة: ${esc(compName(tomHit[0]))}</h2></div><div class="card">${TD.row(tomHit[1], tomHit[0], ctxOf(tomorrow))}</div></section>`;
    const p = `/t/${id}/today/`;
    const html = page({ path:p, page:"days", nav:"", title:`مباراة ${tn} اليوم: الموعد والقناة الناقلة والمعلق | تيفو`, desc:`موعد مباراة ${tn} اليوم ${TD.fullDate(today)} بتوقيت الإمارات والسعودية ومصر والمغرب، والقناة الناقلة والمعلق، والنتيجة مباشرة.`,
      ld:[bcLd([[tn, `/t/${id}/`], ["مباراة اليوم", p]]), faqLd(qa)].filter(Boolean).concat(evs),
      body:`<p class="crumbs"><a href="/t/${id}/">${esc(tn)}</a></p><h1>مباراة ${esc(tn)} اليوم</h1><p class="season">${esc(TD.fullDate(today))}</p><div class="sx" id="days" data-ymd="${today}" data-kind="team">${nav(today, "today")}<p class="intro">${lead}</p>${block}${faqHtml(qa)}<p class="lk"><a class="btn" href="/t/${id}/">كل مباريات ${esc(tn)}</a> <a class="btn" href="/today/">كل مباريات اليوم</a></p></div><script type="application/json" id="dctx">${JSON.stringify({ keys, l365, tv:tvs[today] }).replace(/</g, "\\u003c")}</script>` });
    write(p.slice(1) + "index.html", html); out.pages++; out.urls.push(p); nT++;
  }
  console.log(`day pages: ${out.pages} (${days.length} days, ${nT} team pages), ${out.events} SportsEvents, ${(out.bytes / 1e6).toFixed(1)} MB, ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  return out;
};
