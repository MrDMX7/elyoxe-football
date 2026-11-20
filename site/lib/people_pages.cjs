// Tifo graph phase 7, the old players: a page for each player FotMob does not know whose record is worth one (/p/k<Tifo id>/),
// from v1/people/index.json (name, birth, national team, World Cups) and awards/players.json's k<id> entries (titles, awards).
// Only what the archive holds in full: no career totals, since the internationals before FotMob are partial.
"use strict";
const U = require("../src/v5/ui.js"), AWD = require("./awards.cjs");

const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const AR = /[؀-ۿ]/;
const num = v => `<span class="num">${esc(v)}</span>`;
const nameOf = p => (p.name_ar && AR.test(p.name_ar) ? p.name_ar : p.name) || "";

// caps and goals for his country, from the national team article's records tables (graph/load/intl_records.py)
function intlBlock(r) {
  if (!r || (r[1] == null && r[2] == null)) return "";
  const parts = [r[1] != null && `${num(r[1])} مباراة دولية`, r[2] != null && `${num(r[2])} هدف`].filter(Boolean).join(" و");
  return U.grp("مع المنتخب", `<p>${parts}${r[3] ? ` <span class="muted small">(${esc(r[3])})</span>` : ""}</p><p class="src">من سجل المنتخب في ويكيبيديا.</p>`);
}

function personBody(p, honours, o, intl) {
  o = o || {};
  const facts = [p.born && ["مواليد", num(p.born.slice(0, 4))], p.died && ["توفي", num(p.died.slice(0, 4))], p.nat && ["المنتخب", esc(p.nat)]].filter(Boolean);
  const wc = (p.wc || []).length ? U.grp("في كأس العالم", `<div class="tblw"><table class="tbl"><thead><tr><th>النسخة</th><th>مباريات</th><th>أهداف</th></tr></thead><tbody>${
    p.wc.map(r => `<tr><td>${num(r[0])}</td><td>${num(r[1])}</td><td>${num(r[2])}</td></tr>`).join("")}</tbody></table></div>`) : "";
  return (facts.length ? U.grp("", `<ul class="lc">${facts.map(f => `<li><span class="muted">${f[0]}:</span> ${f[1]}</li>`).join("")}</ul>`) : "") +
    intlBlock(intl) + AWD.playerBlock(honours, o) + wc +
    '<p class="src">من أرشيف تيفو: الألقاب والجوائز من ويكيبيديا وRSSSF وعدّنا، وكأس العالم من قاعدة بيانات كأس العالم (Fjelstul).</p>';
}

const title = p => `${nameOf(p)}: ألقابه وجوائزه ومشاركاته في كأس العالم | تيفو`;
// indexed when there is more than one line to read: two titles or awards, or a World Cup
const indexable = (p, honours) => (p.wc || []).length > 0 || (honours || []).filter(h => h[3] === 1).length >= 2;

module.exports = { personBody, intlBlock, title, indexable, nameOf };
