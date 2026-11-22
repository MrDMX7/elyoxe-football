// Tifo graph phase 7: the season archive of each competition (/c/<key>/seasons/, /c/<key>/s/<season>/), the coach pages
// (/coach/<id>/) and the club's coaches block, from v1/editions/<competition>.json and v1/coaches/*.json (graph/publish.py).
// A link only where the site has the page (o.team, o.player; o.coach(kid) gives the coach's page or null, since a coach FotMob
// knows keeps his /coach/<FotMob id>/ page and the rest live at /coach/k<Tifo id>/); o.coachName(kid), o.teamName(id) and
// o.playerName(id) give the site's Arabic names where the graph has only Latin; a name with no Arabic form is shown in Latin.
"use strict";
const U = require("../src/v5/ui.js");

const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const AR = /[؀-ۿ]/;
const nm = s => AR.test(s || "") ? esc(s) : `<span class="lat">${esc(s || "")}</span>`;
const num = v => `<span class="num">${esc(v)}</span>`;
const slug = s => String(s).replace(/\//g, "-");
const link = (href, ok, text) => ok ? `<a href="${href}">${text}</a>` : text;
// the archive's Arabic name is the club's name in that season (Shabab Al Ahli was الأهلي before 2017); the site's is for a Latin one
const teamL = (t, o) => t ? link(`/t/${t.fotmob}/`, t.fotmob && o.team && o.team(t.fotmob), nm((!AR.test(t.name || "") && t.fotmob && o.teamName && o.teamName(t.fotmob)) || t.name)) : "—";
const playerL = (p, o) => {
  const n = nm((p.fotmob && o.playerName && o.playerName(p.fotmob)) || p.name);
  if (p.fotmob) return link(`/p/${p.fotmob}/`, o.player && o.player(p.fotmob), n);
  return link(`/p/k${p.tifo}/`, p.tifo && o.person && o.person(p.tifo), n);         // an old player: his archive page
};
const coachL = (c, o) => { if (!c) return ""; const href = o.coach && o.coach(c.kid); return link(href, !!href, nm((o.coachName && o.coachName(c.kid)) || c.name_ar || c.name)); };
const year = d => (d || "").slice(0, 4);
const pct = (w, m) => m ? Math.round((100 * w) / m) : 0;

// a page for a season with a champion (or a note saying why there is none) and something more to show, or for an old
// season's match list alone (RSSSF's Arab leagues: the matches, no champion known); its index rule stays table or scorers
const seasonRich = s => !!(s && ((s.champion || s.note) && ((s.table || []).length || (s.top_scorers || []).length) || (s.matches || 0) >= 10));

// a season's tournament in Arabic (graph/publish.fold_parts: 365Scores' names); def: with the article («بطل الأبيرتورا»)
const PARTS = { "apertura": "أبيرتورا", "clausura": "كلاوسورا", "torneo inicial": "البطولة الافتتاحية", "torneo final": "البطولة الختامية",
  "metropolitano": "ميتروبوليتانو", "nacional": "ناسيونال", "league": "بطولة الدوري", "copa": "الكأس", "copa de honor": "كأس الشرف",
  "copa de oro": "الكأس الذهبية", "copa campeonato": "كأس البطولة", "(yellow module)": "المجموعة الصفراء", "(green module)": "المجموعة الخضراء",
  "cup shared": "الكأس مناصفة" };
function partName(n, def) {
  const k = String(n || "").trim().toLowerCase(), ar = PARTS[k] || String(n || "").replace(/\(Amateur\)/i, "(هواة)").trim();
  return def && PARTS[k] && !/^ال/.test(ar) && !/ /.test(ar) ? "ال" + ar : ar;
}

function seasonsBody(ed, comp, o) {
  o = o || {};
  // one row a season, its champion on the line, the runner-up and the top scorer under it: a phone reads it upright (22 Nov 2026:
  // the four-column table put the scorer off the screen)
  const rows = (ed.seasons || []).map(s => {
    const top = (s.top_scorers || []).filter(p => p.rank === 1);
    const season = (o.page || seasonRich)(s) ? `<a href="/c/${comp.key}/s/${slug(s.season)}/">${num(s.season)}</a>` : num(s.season);   // o.page: a season with its page
    const end = /\//.test(s.season) ? `${String(s.season).slice(5, 9)}-06-30` : `${String(s.season).slice(0, 4)}-12-31`;
    const inPlay = !s.champion && !s.note && end >= new Date().toISOString().slice(0, 10);      // the season still being played
    const parts = (s.parts || []).filter(p => p.champion).map(p => `${esc(partName(p.name))} <b>${teamL(p.champion, o)}</b>`).join(" · ");
    const main = s.note && !s.champion ? `<span class="muted">${esc(s.note)}</span>` : (s.champion ? `<b>${teamL(s.champion, o)}</b>` : parts ? parts :
      inPlay ? '<span class="muted">الموسم الجاري</span>' : '<span class="muted">—</span>');
    const sub = [s.champion && parts, s.runner_up && `الوصيف ${teamL(s.runner_up, o)}`,
      top.length && `${inPlay ? "يتصدر الهدافين" : "الهداف"} ${top.map(p => `${playerL(p, o)}${p.value ? ` <span class="num">(${esc(p.value)})</span>` : ""}`).join(" و")}`,
      // no scorer of its own: each tournament's (Argentina's Apertura and Clausura)
      !top.length && (s.parts || []).some(p => (p.top || []).length) && `الهداف ${(s.parts || []).filter(p => (p.top || []).length).map(p =>
        `${esc(partName(p.name))} ${p.top.map(t => `${playerL(t, o)}${t.value ? ` <span class="num">(${esc(t.value)})</span>` : ""}`).join(" و")}`).join(" · ")}`].filter(Boolean).join(" · ");
    return U.row({ t: `${season} · ${main}`, sub, cls: "ssn" });
  }).join("");
  return U.grp(`كل المواسم <span class="num">${(ed.seasons || []).length}</span>`, rows) +
    '<p class="src">من قاعدة تيفو: الأبطال من 365Scores وRSSSF وويكيبيديا، والهدافين من عدّنا للأهداف وقوائم FotMob وTransfermarkt.</p>';
}

function seasonBody(s, comp, o) {
  o = o || {};
  const facts = [s.champion ? ["البطل", teamL(s.champion, o)] : s.note && ["الموسم", esc(s.note)], s.runner_up && ["الوصيف", teamL(s.runner_up, o)],
    ...(s.parts || []).filter(p => p.champion).map(p => [`بطل ${esc(partName(p.name, 1))}`, teamL(p.champion, o) + (p.runner_up ? ` <span class="muted">(الوصيف ${teamL(p.runner_up, o)})</span>` : "")]),
    ...(s.parts || []).filter(p => (p.top || []).length).map(p => [`هداف ${esc(partName(p.name, 1))}`, p.top.map(t => playerL(t, o) + (t.value ? ` <span class="muted small">${num(t.value)}</span>` : "")).join("، ")]),
    s.champion_coach && ["مدرب البطل", coachL(s.champion_coach, o)],
    s.matches && ["المباريات", num(s.matches)]].filter(Boolean);
  const people = (title, list) => (list || []).length ? U.grp(title, `<ol class="lc">${list.map(p => `<li>${playerL(p, o)}${p.value ? ` <span class="muted small">${num(p.value)}</span>` : ""}</li>`).join("")}</ol>`) : "";
  const table = (s.table || []).length ? U.grp(s.note && !s.champion ? "الترتيب لحظة التوقف" : "الترتيب النهائي", `<div class="tblw"><table class="tbl"><thead><tr><th>#</th><th class="tm">الفريق</th><th>لعب</th><th>ف</th><th>ت</th><th>خ</th><th>له</th><th>عليه</th><th>نقاط</th></tr></thead><tbody>${
    s.table.map(r => `<tr><td>${num(r[0])}</td><td>${teamL({ fotmob: r[1], name: r[2] }, o)}</td>${r.slice(3, 9).map(v => `<td>${num(v == null ? "" : v)}</td>`).join("")}<td><b>${num(r[9] == null ? "" : r[9])}</b></td></tr>`).join("")}</tbody></table></div>`) : "";
  return U.grp("", `<ul class="lc">${facts.map(f => `<li><span class="muted">${f[0]}:</span> ${f[1]}</li>`).join("")}</ul>`) + table +
    people("الهدافين", s.top_scorers) + people("أفضل لاعب", s.best_player) + people("أفضل لاعب شاب", s.best_young) + people("أفضل حارس", s.best_goalkeeper) +
    people("أفضل لاعب محلي", s.best_local) + people("أكثر صانع أهداف", s.top_assist) +
    ((s.best_coach || []).length ? U.grp("أفضل مدرب", `<p>${s.best_coach.map(c => coachL(c, o)).join("، ")}</p>`) : "") +
    ((s.motm || []).length ? U.grp("رجل المباراة", `<ol class="lc">${s.motm.map(m => `<li>${playerL({ fotmob: m[0], name: m[1], tifo: m[3] }, o)} <span class="muted small">${num(m[2])}</span></li>`).join("")}</ol>`) : "") +
    U.grp("", U.row({ href: `/c/${comp.key}/seasons/`, icon: "hist", c: "#FF9500", t: `كل مواسم ${esc(comp.name_ar)}` }));
}

function coachTotals(c) {
  return (c.spells || []).reduce((a, s) => ({ m: a.m + (s.m || 0), w: a.w + (s.w || 0), d: a.d + (s.d || 0), l: a.l + (s.l || 0) }), { m: 0, w: 0, d: 0, l: 0 });
}

// a page for a coach with 30 matches in our data or a bench at a club the site has; only the first kind is rich enough to index
const coachIndexable = c => coachTotals(c).m >= 30;
const coachPageable = (c, o) => coachIndexable(c) || (c.spells || []).some(s => s.team && o && o.team && o.team(s.team));

function coachBody(c, o) {
  o = o || {};
  const t = coachTotals(c);
  const rows = (c.spells || []).map(s => `<tr><td>${teamL({ fotmob: s.team, name: s.team_name }, o)}</td><td class="num">${esc(year(s.start))}–${esc(year(s.end))}</td><td>${num(s.m)}</td><td>${num(s.w)}</td><td>${num(s.d)}</td><td>${num(s.l)}</td><td>${num(pct(s.w, s.m))}%</td></tr>`).join("");
  return U.grp("", `<p>${num(t.m)} مباراة · ${num(t.w)} فوز · ${num(t.d)} تعادل · ${num(t.l)} خسارة · نسبة الفوز ${num(pct(t.w, t.m))}%</p>`) +
    U.grp("مسيرته التدريبية", `<div class="tblw"><table class="tbl"><thead><tr><th>الفريق</th><th>الفترة</th><th>م</th><th>ف</th><th>ت</th><th>خ</th><th>الفوز</th></tr></thead><tbody>${rows}</tbody></table></div>`) +
    '<p class="src">من قاعدة تيفو: مقاعد المدربين من FotMob وTransfermarkt وقاعدة بيانات كأس العالم، والسجل محسوب من مبارياتنا.</p>';
}

function clubCoaches(spells, o) {
  if (!spells || !spells.length) return "";
  o = o || {};
  return `<ul class="lc">${spells.slice(0, 40).map(s => `<li>${coachL(s, o)} <span class="muted small num">${esc(year(s.start))}–${esc(year(s.end))}</span> · ${num(s.m)} م · ${num(s.w)} ف · ${num(s.d)} ت · ${num(s.l)} خ</li>`).join("")}</ul>`;
}

module.exports = { slug, seasonRich, seasonsBody, seasonBody, coachBody, coachIndexable, coachPageable, clubCoaches, coachTotals };
