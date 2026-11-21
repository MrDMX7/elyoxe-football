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
  const shown = p.name_ar && AR.test(p.name_ar) ? esc(p.name_ar) : n;
  if (p.fotmob && o.hasPage && o.hasPage(p.fotmob)) return `<a href="/p/${p.fotmob}/">${shown}</a>`;
  return p.tifo && o.person && o.person(p.tifo) ? `<a href="/p/k${p.tifo}/">${shown}</a>` : n;      // an old player: his archive page
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
  const ys = d.years || [], firsts = y => (y.podium || []).filter(p => p.rank === 1);
  // the team and value columns only when some year has one: most Wikipedia tables give neither, and two empty
  // columns on every row read as a broken table (QA 2026-11-21: 759 of 820 award pages)
  const hasTeam = ys.some(y => firsts(y).some(p => p.team)), hasVal = ys.some(y => firsts(y).some(p => p.value));
  const rows = ys.map(y => {
    const pod = y.podium || [], first = firsts(y), rest = pod.filter(p => p.rank > 1);
    // not .tm: that column style stacks every link and span (the podium broke into one word a line)
    return `<tr><td class="dim num">${esc(y.season)}</td><td><b>${first.map(p => who(p, o)).join("، ") || "—"}</b>` +
      (rest.length ? `<br><span class="muted small">${rest.map(p => `${RANK[p.rank] || num(p.rank)}: ${who(p, o)}`).join(" · ")}</span>` : "") + "</td>" +
      (hasTeam ? `<td>${first.map(p => p.team ? nm(p.team, p.team) : "").filter(Boolean).join("، ") || "—"}</td>` : "") +
      (hasVal ? `<td class="num">${esc(first.map(p => p.value || "").filter(Boolean).join("، ")) || "—"}</td>` : "") + "</tr>";
  }).join("");
  const table = `<div class="tblw"><table class="tbl"><thead><tr><th>السنة</th><th>الفائز</th>${hasTeam ? "<th>الفريق</th>" : ""}${hasVal ? "<th>الرقم</th>" : ""}</tr></thead><tbody>${rows}</tbody></table></div>`;
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

// Two awards with one Arabic name (graph/publish.py translates «Bulgarian Footballer of the Year — Women» and «— Youth» both to
// «جائزة لاعب كرة القدم البلغاري للسنة»: 68 names shared by 2-60 awards on 2026-11-21) give two pages one <title> and one <h1>.
// Each name shared by several awards gets the qualifiers its English name carries (women, youth, under-21, foreign, coach…),
// a qualifier the Arabic name already says is skipped. No made-up numbering: what stays shared is the graph's translation to fix.
// Sets a.name_ar in place; returns how many it changed.
const QUAL = [[/\bunder[- ]?(\d+)/i, m => `تحت ${m[1]} سنة`, /تحت/], [/women|female|girls|vrouwen/i, "للسيدات", /سيدات|نساء|نسائ/], [/\b(men|male)\b|\bmen's/i, "للرجال", /رجال/],
  [/youth|young|junior|talent|breakthrough|revela/i, "للشباب", /شاب|شباب|ناشئ/], [/foreign/i, "للأجانب", /أجنب/], [/goalkeeper/i, "لحراسة المرمى", /حارس|حراسة/],
  [/manager|coach/i, "للمدربين", /مدرب/], [/referee/i, "للحكام", /حكم|حكام/], [/fans'?|supporters/i, "باختيار الجماهير", /جماهير|مشجع/],
  [/players'? player/i, "باختيار اللاعبين", /اختيار اللاعبين/], [/\bmedia\b/i, "باختيار الإعلام", /إعلام/], [/east germany/i, "لألمانيا الشرقية", /الشرقية/],
  [/amateur|ameteur/i, "للهواة", /هواة/], [/schools?|colleges?|universit/i, "للمدارس والجامعات", /مدارس|جامع/], [/disabilit/i, "لذوي الإعاقة", /إعاقة/]];
function uniqueNames(awards) {
  const by = {};
  (awards || []).forEach(a => { const n = a.name_ar && AR.test(a.name_ar) ? a.name_ar : null; if (n) (by[n] = by[n] || []).push(a); });
  let changed = 0;
  Object.entries(by).filter(([, l]) => l.length > 1).forEach(([n, l]) => {
    const tail = a => String(a.name || "");   // the whole English name: «The FA Women's Football Awards — Manager of the Year»
    l.forEach(a => {
      const q = [];
      QUAL.forEach(([re, ar, has]) => { const m = tail(a).match(re); if (!m || has.test(n)) return; const t = typeof ar === "function" ? ar(m) : ar; if (!q.includes(t)) q.push(t); });
      if (q.length) { a.name_ar = n + " " + q.join(" "); changed++; }
    });
  });
  return changed;
}

module.exports = { indexBody, awardBody, playerBlock, indexable, awardName, uniqueNames };
