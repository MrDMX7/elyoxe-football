/* The Arab leagues only 365Scores covers (owner 2026-10-06, item 10): Jordan, Lebanon, Syria, Libya, Sudan, Palestine, Yemen, Bahrain,
   Oman and their cups (db/scores365.py `live`: this season's table, fixtures, results and scorers in v1/s365/comp/<id>.json; each
   club's squad, games and titles in v1/s365/team/<id>.json). Their /db/league/<id>/ pages (until now the champions' history with
   the table on top) lead with the season instead: table, the next matches, the results, the scorers, then the history; and every
   club of those leagues gets a static /db/team/<id>/ page (the client page /db/team/?id= stays for the rest).
   Rows are src/days.js's (v5 markup), times printed for the UAE, Saudi Arabia, Egypt and Morocco. Called by build.cjs. */
"use strict";
const TD = require("../src/days.js");
const esc = TD.esc;

// 365 gives local UAE wall-clock times without an offset ("2026-10-08T19:00", timezoneName=Asia/Dubai): to UTC
const utcOf = s => { if (!s || !/^\d{4}-\d\d-\d\dT\d\d:\d\d/.test(s)) return null; const t = Date.parse(s.slice(0, 16) + ":00+04:00"); return isNaN(t) ? null : new Date(t).toISOString().replace(".000", ""); };
const STATUS = { 2:"scheduled", 3:"live", 4:"finished" };
// a game row [id, start, season, round, home, away, hs, as, statusGroup, lineups] as a day-list row
function row(g, N){ const st = STATUS[g[8]] || (g[6] != null ? "finished" : "scheduled"), sc = st === "finished" || st === "live";
  return { id:"365:" + g[0], utc:utcOf(g[1]), status:st, home:["365:" + g[4], N[g[4]] || ""].concat(sc && g[6] != null ? [g[6]] : []), away:["365:" + g[5], N[g[5]] || ""].concat(sc && g[7] != null ? [g[7]] : []), round:g[3], season:g[2] }; }
// the season a set of games belongs to, from its first date: August 2026 -> «2026/2027», March 2026 -> «2025/2026»
function seasonLabel(games){ const ds = games.map(g => g[1]).filter(Boolean).sort(); if (!ds.length) return ""; const y = +ds[0].slice(0, 4), m = +ds[0].slice(5, 7); return m >= 7 ? `${y}/${y + 1}` : `${y - 1}/${y}`; }

module.exports = function(X){
  const { page, write, SITE, bcLd, teamLink } = X;
  const lg365 = (cid, d) => ({ id:"365:" + cid, name_ar:d.name, src:"365", cc:"", country_ar:d.country || "" });
  const ctx = ymd => ({ ymd, keys:{}, l365:[], bc:null, tv:{}, tz:"Asia/Dubai" });
  // the current season's part of a league page: { title, desc, h1, sub, html, n } or null when 365 has nothing live
  function season(cid, d){
    const L = d.live; if (!L || !((L.table || []).length || (L.fixtures || []).length || (L.results || []).length)) return null;
    const N = d.names || {}, all = (L.results || []).concat(L.fixtures || []), cur = Math.max(...all.map(g => +g[2] || 0)), curG = all.filter(g => +g[2] === cur);
    const res = (L.results || []).filter(g => +g[2] === cur), fix = (L.fixtures || []).filter(g => !g[2] || +g[2] === cur || +g[2] > cur);
    const sl = seasonLabel(curG.length ? curG : all), lg = lg365(cid, d), ko = !!d.ko && !(L.table || []).length, today = TD.uaeYmd(0), c = ctx(today);
    const tl = id => teamLink(id);
    const rows = gs => gs.map(g => TD.row(row(g, N), lg, c)).join("");
    // by round, the next round first (fixtures) / the latest first (results)
    const byRound = (gs, h) => { const r = {}, order = []; gs.forEach(g => { const k = g[3] == null ? "—" : String(g[3]); if (!r[k]){ r[k] = []; order.push(k); } r[k].push(g); });
      return order.map(k => `<section class="grp dl"><div class="gh"><h2>${/^\d+$/.test(k) ? "الجولة " + esc(k) : esc(h)}</h2><span class="nn">${TD.nMatches(r[k].length)}</span></div><div class="card">${rows(r[k])}</div></section>`).join(""); };
    const nextR = fix.length ? fix.filter(g => g[3] === fix[0][3]) : [], restF = fix.filter(g => nextR.indexOf(g) < 0).slice(0, 20);
    const table = (L.table || []).length ? `<section class="grp"><div class="gh"><h2>الترتيب</h2><span class="nn">الموسم <span class="num">${esc(sl)}</span></span></div><div class="card"><div class="tblw"><table class="tbl"><thead><tr><th>#</th><th class="tm">الفريق</th><th>لعب</th><th>فوز</th><th>تعادل</th><th>خسارة</th><th>له</th><th>عليه</th><th>+/-</th><th>نقاط</th></tr></thead><tbody>` +
      L.table.map(r => { const gd = r[6] != null && r[7] != null ? r[6] - r[7] : null; return `<tr><td>${r[0] == null ? "" : r[0]}</td><td class="tm"><a href="${tl(r[1])}">${esc(N[r[1]] || "")}</a></td><td>${r[2] ?? ""}</td><td>${r[3] ?? ""}</td><td>${r[4] ?? ""}</td><td>${r[5] ?? ""}</td><td>${r[6] ?? ""}</td><td>${r[7] ?? ""}</td><td><bdi dir="ltr">${gd == null ? "" : (gd > 0 ? "+" : "") + gd}</bdi></td><td class="pts">${r[8] == null ? "" : Math.round(r[8])}</td></tr>`; }).join("") + "</tbody></table></div></div></section>" : "";
    const SC = L.scorers || {}, scK = Object.keys(SC);
    const lead = (k, title) => { const list = (SC[k] || []).filter(x => x && x[1]); if (!list.length) return ""; let rk = 0, last = null;
      return `<section class="grp"><div class="gh"><h2>${esc(title)}</h2></div><div class="card">${list.slice(0, 15).map((x, i) => { if (x[3] !== last){ rk = i + 1; last = x[3]; } return `<a class="ld" href="/db/athlete/?id=${x[0]}"><span class="rk">${rk}</span><span class="rt"><b>${esc(x[1])}</b><small>${esc(N[x[2]] || "")}</small></span><span class="v">${esc(x[3])}</span></a>`; }).join("")}</div></section>`; };
    const goalsK = scK.find(k => /أهداف$|الأهداف/.test(k) && !/صناعة/.test(k)) || scK[0], astK = scK.find(k => /^صناعة|التمريرات/.test(k));
    const live = curG.filter(g => g[8] === 3).length;
    const html = table + (nextR.length ? `<h2 class="sxh">المباريات الياية</h2>` + byRound(nextR, "المباريات الياية") + (restF.length ? `<details class="grp dl dz"><summary class="gh"><h2>بعدها</h2><span class="nn">${TD.nMatches(restF.length)}</span></summary><div class="card">${rows(restF)}</div></details>` : "") : "") +
      (res.length ? `<h2 class="sxh">النتائج</h2>` + byRound(res.slice(0, 30), "النتائج") : "") + (goalsK ? lead(goalsK, "الهدافين") : "") + (astK ? lead(astK, "صناع الأهداف") : "");
    const name = d.name, country = d.country || "", ns = sl ? " " + sl : "";
    const title = ko ? `${name}${ns}: المباريات والنتائج | تيفو` : `${name}${ns}: الترتيب والهدافين ومواعيد المباريات | تيفو`;
    const desc = ko ? `مباريات ${name}${country ? " في " + country : ""}${sl ? " موسم " + sl : ""}: المواعيد بتوقيت بلدك والنتائج، وكل الأبطال من أول موسم.`
      : `ترتيب ${name}${ns}${country ? " في " + country : ""}، ومواعيد المباريات بتوقيت بلدك والنتائج، والهدافين وصناع الأهداف، وكل الأبطال من أول موسم.`;
    return { title, desc, h1:name, sub:[country && esc(country), d.name_en && `<span class="lat">${esc(d.name_en)}</span>`, sl && `الموسم <span class="num">${esc(sl)}</span>`].filter(Boolean).join(" · "), html, n:curG.length, live,
      teams:[...new Set([].concat((L.table || []).map(r => r[1]), all.flatMap(g => [g[4], g[5]])))].filter(Boolean) };
  }
  // a club of those leagues: next matches, results, squad, titles (v1/s365/team/<id>.json)
  function team(t, comp){
    const N = t.names || {}, games = (t.games || []).slice(), today = TD.uaeYmd(0), c = ctx(today), lg = { id:"365:" + (comp ? comp.id : 0), name_ar:comp ? comp.name : "", src:"365" };
    N[t.id] = N[t.id] || t.name;
    const fin = games.filter(g => g[8] === 4 || (g[6] != null && g[8] !== 2)).sort((a, b) => String(b[1]).localeCompare(String(a[1]))), nxt = games.filter(g => g[8] === 2 || (g[6] == null && g[8] !== 4)).sort((a, b) => String(a[1]).localeCompare(String(b[1])));
    const blk = (h, gs, more) => gs.length ? `<section class="grp dl"><div class="gh"><h2>${esc(h)}</h2>${more || ""}</div><div class="card">${gs.map(g => TD.row(row(g, N), lg, c)).join("")}</div></section>` : "";
    const POS = {}; (t.squad || []).forEach(p => { const k = p[3] || "اللاعبين"; (POS[k] = POS[k] || []).push(p); });
    const order = ["حراسة المرمى", "حارس المرمى", "الدفاع", "الوسط", "خط الوسط", "الهجوم"], ks = Object.keys(POS).sort((a, b) => (order.indexOf(a) < 0 ? 9 : order.indexOf(a)) - (order.indexOf(b) < 0 ? 9 : order.indexOf(b)));
    const squad = ks.map(k => `<section class="grp"><div class="gh"><h2>${esc(k)}</h2><span class="nn">${POS[k].length}</span></div><div class="card">${POS[k].map(p => `<a class="row" href="/db/athlete/?id=${p[0]}"><span class="rt"><b>${esc(p[1] || p[9] || "")}</b><small>${[p[4] && esc(p[4]), p[5] > 0 && `<span class="num">${p[5]}</span> سنة`].filter(Boolean).join(" · ")}</small></span><span class="rv">${p[2] > 0 ? p[2] : ""}</span></a>`).join("")}</div></section>`).join("");
    const titles = (t.titles || []).filter(x => (x[2] || []).length).sort((a, b) => b[2].length - a[2].length);
    const tro = titles.length ? `<section class="grp"><div class="gh"><h2>ألقابه</h2><span class="nn"><span class="num">${titles.reduce((a, x) => a + x[2].length, 0)}</span> لقب</span></div><div class="card">${titles.map(x => `<div class="row"><span class="rt"><b>${esc(x[1])}</b><small>${esc(x[2].slice(0, 12).join("، "))}${x[2].length > 12 ? "…" : ""}</small></span><span class="rv">${x[2].length}</span></div>`).join("")}</div></section>` : "";
    const html = blk("المباريات الياية", nxt.slice(0, 6)) + blk("آخر النتايج", fin.slice(0, 10)) + squad + tro;
    const name = t.name, country = t.country || "", cn = comp ? comp.name : "";
    return { title:`${name}: المباريات والنتائج واللاعبين والألقاب | تيفو`, desc:`مباريات ${name}${cn ? " في " + cn : ""} بتوقيت بلدك ونتائجه، وقائمة اللاعبين${titles.length ? "، وألقابه" : ""}${country ? "، من " + country : ""}.`,
      h1:name, sub:[country && esc(country), cn && esc(cn), t.name_en && `<span class="lat">${esc(t.name_en)}</span>`].filter(Boolean).join(" · "), html, n:games.length };
  }
  return { season, team, utcOf };
};
