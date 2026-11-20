// Tifo graph phase 7, the old players: a page for each player FotMob does not know whose record is worth one (/p/k<Tifo id>/),
// from v1/people/index.json (name, birth, national team, World Cups) and awards/players.json's k<id> entries (titles, awards).
// Only what the archive holds in full: no career totals, since the internationals before FotMob are partial.
"use strict";
const U = require("../src/v5/ui.js"), AWD = require("./awards.cjs");

const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const AR = /[؀-ۿ]/;
const num = v => `<span class="num">${esc(v)}</span>`;
const nameOf = p => (p.name_ar && AR.test(p.name_ar) ? p.name_ar : p.name) || "";

function personBody(p, honours, o) {
  o = o || {};
  const facts = [p.born && ["مواليد", num(p.born.slice(0, 4))], p.died && ["توفي", num(p.died.slice(0, 4))], p.nat && ["المنتخب", esc(p.nat)]].filter(Boolean);
  const wc = (p.wc || []).length ? U.grp("في كأس العالم", `<div class="tblw"><table class="tbl"><thead><tr><th>النسخة</th><th>مباريات</th><th>أهداف</th></tr></thead><tbody>${
    p.wc.map(r => `<tr><td>${num(r[0])}</td><td>${num(r[1])}</td><td>${num(r[2])}</td></tr>`).join("")}</tbody></table></div>`) : "";
  return (facts.length ? U.grp("", `<ul class="lc">${facts.map(f => `<li><span class="muted">${f[0]}:</span> ${f[1]}</li>`).join("")}</ul>`) : "") +
    AWD.playerBlock(honours, o) + wc +
    '<p class="src">من أرشيف تيفو: الألقاب والجوائز من ويكيبيديا وRSSSF وعدّنا، وكأس العالم من قاعدة بيانات كأس العالم (Fjelstul).</p>';
}

const title = p => `${nameOf(p)}: ألقابه وجوائزه ومشاركاته في كأس العالم | تيفو`;
// indexed when there is more than one line to read: two titles or awards, or a World Cup
const indexable = (p, honours) => (p.wc || []).length > 0 || (honours || []).filter(h => h[3] === 1).length >= 2;

module.exports = { personBody, title, indexable, nameOf };
