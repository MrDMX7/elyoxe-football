// «الجوائز» (Tifo graph phase 2, docs/superpowers/specs/2026-11-19-tifo-graph-design.md §7.6): /awards/, /awards/<key>/ and the
// «جوائزه وتكريماته» block of the player pages, from v1/awards/index.json, v1/awards/<key>.json and v1/awards/players.json
// (graph/publish.py). A winner links to his /p/ page only when the site has one; a name with no Arabic form is shown in Latin.
"use strict";
const U = require("../src/v5/ui.js");

const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const AR = /[؀-ۿ]/;
const nm = (ar, en) => ar && AR.test(ar) ? esc(ar) : `<span class="lat">${esc(en || ar || "")}</span>`;
const num = v => `<span class="num">${esc(v)}</span>`;
const RANK = { 1: "الأول", 2: "الثاني", 3: "الثالث", 4: "الرابع", 5: "الخامس" };
const GROUPS = [["world", "جوائز عالمية"], ["continent", "جوائز القارات"], ["tournament", "جوائز البطولات"], ["league", "جوائز الدوريات"],
  ["country", "جوائز الدول"], ["club", "جوائز الأندية"], ["women", "كرة القدم النسائية"]];
const KIND = { top_scorer: "هداف", best_player: "أفضل لاعب في", best_goalkeeper: "أفضل حارس في", best_young: "أفضل لاعب شاب في",
  best_coach: "أفضل مدرب في", fair_play: "اللعب النظيف في", top_assist: "أكثر صانع أهداف في", best_local: "أفضل لاعب محلي في" };
const awardName = a => nm(a.name_ar, a.name);
const indexable = a => (a.years || 0) >= 5;

function who(p, o) {
  const n = nm(p.name_ar, p.name);
  return p.fotmob && o.hasPage && o.hasPage(p.fotmob) ? `<a href="/p/${p.fotmob}/">${p.name_ar && AR.test(p.name_ar) ? esc(p.name_ar) : n}</a>` : n;
}

function indexBody(ix, o) {
  const by = {};
  (ix.awards || []).forEach(a => { (by[a.group] = by[a.group] || []).push(a); });
  return GROUPS.filter(g => (by[g[0]] || []).length).map(([g, title]) => U.grp(`${title} <span class="num">${by[g].length}</span>`,
    U.rows(by[g].map(a => ({ href: `/awards/${a.key}/`, icon: "crown", c: "#FFCC00", t: awardName(a),
      sub: `منذ ${num(a.first)} · ${num(a.years)} ${a.years > 10 ? "نسخة" : "نسخ"}` + (a.top && a.top[1] > 1 ? ` · الأكثر فوزاً ${esc(a.top[0])} (${num(a.top[1])})` : "") }))))).join("");
}

function awardBody(d, o) {
  o = o || {};
  const rows = (d.years || []).map(y => {
    const pod = y.podium || [], first = pod.filter(p => p.rank === 1), rest = pod.filter(p => p.rank > 1);
    return `<tr><td class="dim num">${esc(y.season)}</td><td class="tm">${first.map(p => who(p, o)).join("، ") || "—"}` +
      (rest.length ? `<div class="muted small">${rest.map(p => `${RANK[p.rank] || num(p.rank)}: ${who(p, o)}`).join(" · ")}</div>` : "") +
      `</td><td>${first.map(p => p.team ? nm(p.team, p.team) : "").filter(Boolean).join("، ")}</td><td class="num">${esc(first.map(p => p.value || "").filter(Boolean).join("، "))}</td></tr>`;
  }).join("");
  const table = `<div class="tblw"><table class="tbl"><thead><tr><th>السنة</th><th class="tm">الفائز</th><th>الفريق</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`;
  const most = (d.most || []).filter(m => m[1] > 1);
  return U.grp(`كل الفائزين <span class="num">${(d.years || []).length}</span>`, table, { raw: 0 }) +
    (most.length ? U.grp("الأكثر فوزاً", U.rows(most.map(m => ({ href: m[2] && o.hasPage && o.hasPage(m[2]) ? `/p/${m[2]}/` : null, icon: "crown", c: "#FFCC00",
      t: AR.test(m[0] || "") ? esc(m[0]) : `<span class="lat">${esc(m[0])}</span>`, v: `${num(m[1])} مرات` })))) : "") +
    '<p class="src">من جداول ويكيبيديا، ومطابقة الفائزين بويكي داتا وقاعدة تيفو.</p>';
}

function playerBlock(list, o) {
  if (!list || !list.length) return "";
  o = o || {};
  const rows = list.map(x => {
    const [key, season, kind, rank, comp] = x;
    if (key) {
      const a = o.award && o.award(key);
      if (!a) return null;
      return { href: `/awards/${key}/`, icon: "crown", c: rank === 1 ? "#FFCC00" : "#8E8E93", t: awardName(a), sub: `${num(season)}${rank > 1 ? " · " + (RANK[rank] || "") : ""}` };
    }
    const c = o.comp && o.comp(comp);
    if (!c || !KIND[kind]) return null;
    return { href: c.href || null, icon: "medal", c: "#34C759", t: `${KIND[kind]} ${esc(c.name_ar || "")}`, sub: `${num(season)}${rank > 1 ? " · " + (RANK[rank] || "") : ""}` };
  }).filter(Boolean);
  return rows.length ? U.grp("جوائزه وتكريماته", U.rows(rows)) : "";
}

module.exports = { indexBody, awardBody, playerBlock, indexable, awardName };
