// Tifo graph phase 7, the old matches: a page for each match of the archive (the Pro League season by season, the national
// team since 1972) from v1/matches/* (graph/publish.matches). A match FotMob knows is /m/<FotMob id>/ (when the site has no
// current page for it), any other /m/k<Tifo id>/. Only what the archive holds: the score always; scorers, cards, lineups and
// coaches where a source gave them. A link only where the site has the page (o.team, o.player, o.person, o.comp).
"use strict";
const U = require("../src/v5/ui.js");

const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const AR = /[؀-ۿ]/;
const nm = s => AR.test(s || "") ? esc(s) : `<span class="lat">${esc(s || "")}</span>`;
const num = v => `<span class="num">${esc(v)}</span>`;
const EV = { goal: "هدف", penalty_goal: "هدف من ضربة جزاء", own_goal: "هدف في مرماه", yellow: "إنذار", second_yellow: "إنذار ثاني وطرد", red: "طرد" };

const href = m => `/m/${m.id}/`;
const team = (t, o) => (t[0] && o.team && o.team(t[0]) ? `<a href="/t/${t[0]}/">${nm(t[1])}</a>` : nm(t[1]));
function player(name, key, o) {
  const shown = nm((key && !key.startsWith("k") && o.playerName && o.playerName(key)) || name);
  if (!key) return shown;
  if (key.startsWith("k")) return o.person && o.person(key) ? `<a href="/p/${key}/">${shown}</a>` : shown;
  return o.player && o.player(key) ? `<a href="/p/${key}/">${shown}</a>` : shown;
}
const minute = e => num(e[1] ? `${e[0]}+${e[1]}` : e[0]);
const seasonLink = (m, o) => {
  const c = m.comp && o.comp && o.comp(m.comp);
  if (!c) return m.season ? num(m.season) : "";
  return `<a href="/c/${c.key}/s/${String(m.season).replace(/\//g, "-")}/">${esc(c.name_ar)} ${num(m.season)}</a>`;
};

function matchBody(m, o) {
  o = o || {};
  const score = `<p class="score"><span>${team(m.h, o)}</span> ${num(m.s[0])} - ${num(m.s[1])} <span>${team(m.a, o)}</span></p>` +
    (m.pen ? `<p class="muted">ركلات الترجيح ${num(m.pen[0])} - ${num(m.pen[1])}</p>` : "") +
    (m.ht ? `<p class="muted">الشوط الأول ${num(m.ht[0])} - ${num(m.ht[1])}</p>` : "");
  const facts = [["التاريخ", num(m.date)], (m.comp || m.season) && ["البطولة", seasonLink(m, o)], m.round && ["الجولة", num(m.round)],
    m.venue && ["الملعب", nm(m.venue)], m.ref && ["الحكم", nm(m.ref)],
    m.co && m.co.h && [`مدرب ${esc(m.h[1])}`, nm(m.co.h)], m.co && m.co.a && [`مدرب ${esc(m.a[1])}`, nm(m.co.a)],
    m.motm && m.motm[0] && ["رجل المباراة", player(m.motm[0], m.motm[1], o)]].filter(Boolean);
  const ev = (m.ev || []).filter(e => EV[e[2]]);
  const evs = ev.length ? U.grp("الأحداث", `<ol class="lc">${ev.map(e => `<li>${minute(e)}' ${EV[e[2]]}: ${player(e[4], e[5], o)} <span class="muted small">(${esc((e[3] === "h" ? m.h : m.a)[1])})</span></li>`).join("")}</ol>`) : "";
  const side = (k, t) => {
    const l = (m.lu && m.lu[k]) || [];
    if (!l.length) return "";
    const row = p => `<li>${p[2] ? `<span class="num muted">${esc(p[2])}</span> ` : ""}${player(p[0], p[1], o)}</li>`;
    const st = l.filter(p => p[3] !== 0), sb = l.filter(p => p[3] === 0);
    if (!l.some(p => p[3] === 1))           // the source marked no starter (FotMob's older seasons): who played, not a lineup
      return U.grp(`شاركوا في المباراة: ${esc(t[1])}`, `<ul class="lc">${l.map(row).join("")}</ul>`);
    return U.grp(`التشكيلة: ${esc(t[1])}`, `<ul class="lc">${st.map(row).join("")}</ul>` + (sb.length ? `<p class="muted small">الاحتياط</p><ul class="lc">${sb.map(row).join("")}</ul>` : ""));
  };
  return U.grp("", score + `<ul class="lc">${facts.map(f => `<li><span class="muted">${f[0]}:</span> ${f[1]}</li>`).join("")}</ul>`) + evs + side("h", m.h) + side("a", m.a) +
    '<p class="src">من أرشيف تيفو: النتيجة والأحداث والتشكيلات من FotMob وTransfermarkt وقواعد بيانات المنتخبات وكأس العالم، حسب ما يتوفر لكل مباراة.</p>';
}

function title(m, comp) {
  return `${m.h[1]} ${m.s[0]}-${m.s[1]} ${m.a[1]}: ${comp ? `${comp.name_ar} ${m.season || ""}`.trim() : m.date} | تيفو`;
}
const indexable = m => !!((m.ev || []).length || (m.lu && Object.keys(m.lu).length));

// a season's (or a team's) matches, round by round (or year by year), each linked to its page
function listBody(ms, o, by) {
  o = o || {};
  const groups = new Map();
  for (const m of ms) {
    const k = by === "year" ? m.date.slice(0, 4) : (m.round || "");
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(m);
  }
  return [...groups].map(([k, l]) => U.grp(by === "year" ? num(k) : k ? `الجولة ${num(k)}` : "",
    `<ul class="lc">${l.map(m => `<li><a href="${href(m)}"><span class="num muted small">${esc(m.date)}</span> ${nm(m.h[1])} ${num(m.s[0])} - ${num(m.s[1])} ${nm(m.a[1])}</a></li>`).join("")}</ul>`)).join("");
}

// a club's all-matches list from the season files (v1/matches/<comp>/<season>.json): each match under both sides' ids, once
// (a match listed by two season files counts once), oldest first; only teams with at least o.min matches, none in o.skip
// (a team with its own team-<id>.json keeps that list), and, with o.keep, only the teams it accepts (those with a page)
function teamMatches(lists, o) {
  o = o || {};
  const by = new Map(), seen = new Map();
  for (const ms of lists) for (const m of ms || []) for (const side of [m.h, m.a]) {
    const id = side && side[0] != null && side[0] !== "" ? +side[0] : NaN;
    if (!Number.isFinite(id) || (o.skip && o.skip.has(id)) || (o.keep && !o.keep(id))) continue;
    if (!seen.has(id)) { seen.set(id, new Set()); by.set(id, []); }
    if (seen.get(id).has(String(m.id))) continue;
    seen.get(id).add(String(m.id)); by.get(id).push(m);
  }
  const out = new Map();
  for (const [id, ms] of by) if (ms.length >= (o.min || 1)) out.set(id, ms.sort((x, y) => String(x.date).localeCompare(String(y.date))));
  return out;
}

module.exports = { matchBody, listBody, title, indexable, href, teamMatches };
