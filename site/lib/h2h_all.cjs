// Tifo graph: every meeting of two teams in every competition the archive holds (v1/h2h-all/<a>-<b>.json, graph/publish.h2h) —
// the block on the head-to-head pages, the pages for pairs FotMob never listed, and each team's record against every opponent.
// A team is its FotMob id or k<Tifo id>; the pair key is the two sorted as text, its counts read from the first one's side.
"use strict";
const U = require("../src/v5/ui.js");

const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const AR = /[؀-ۿ]/;
const nm = s => AR.test(s || "") ? esc(s) : `<span class="lat">${esc(s || "")}</span>`;
const num = v => `<span class="num">${esc(v)}</span>`;
const key = (a, b) => [String(a), String(b)].sort().join("-");
const mlink = (id, o, text) => (o.match && o.match(id) ? `<a href="/m/${id}/">${text}</a>` : text);

function pairBody(d, o) {
  o = o || {};
  const [a, b] = d.names;
  const sum = `<p>${num(d.n)} مواجهة من ${num(d.first.slice(0, 4))}: ${nm(a)} ${num(d.w[0])} فوز، تعادل ${num(d.w[1])}، ${nm(b)} ${num(d.w[2])} فوز. الأهداف ${num(d.goals[0])} - ${num(d.goals[1])}.</p>`;
  const comps = (d.by_comp || []).length > 1 ? `<div class="tblw"><table class="tbl"><thead><tr><th>البطولة</th><th>مواجهات</th><th>${nm(a)}</th><th>تعادل</th><th>${nm(b)}</th></tr></thead><tbody>${
    d.by_comp.map(r => `<tr><td>${nm(r[0])}</td>${r.slice(1).map(v => `<td>${num(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>` : "";
  const big = (d.biggest || []).map((x, i) => x ? `<li>أكبر فوز لـ${nm(d.names[i])}: ${mlink(x[2], o, num(x[1]))} <span class="muted small num">${esc(x[0])}</span></li>` : "").join("");
  const list = (d.matches || []).map(m => {
    const name = id => nm(d.names[d.teams.indexOf(id)] || id);
    return `<li><span class="num muted small">${esc(m[0])}</span> ${mlink(m[7], o, `${name(m[3])} ${num(m[4])} - ${num(m[5])} ${name(m[6])}`)} <span class="muted small">${nm(m[1])}${m[2] ? " " + num(m[2]) : ""}</span></li>`;
  }).join("");
  return U.grp("كل المواجهات في كل البطولات", sum + comps + (big ? `<ul class="lc">${big}</ul>` : "")) + U.grp("كل المواجهات", `<ol class="lc">${list}</ol>`) +
    '<p class="src">من أرشيف تيفو: الدوري والكؤوس وآسيا والمباريات الدولية، من FotMob و365Scores وقواعد بيانات النتايج التاريخية.</p>';
}

function teamBody(me, rows, names, o) {
  o = o || {};
  const tr = rows.map(r => {
    const href = o.pair && o.pair(me, r[0]);
    const who = href ? `<a href="${href}">${nm(names[r[0]] || r[0])}</a>` : nm(names[r[0]] || r[0]);
    return `<tr><td>${who}</td>${r.slice(1).map(v => `<td>${num(v)}</td>`).join("")}</tr>`;
  }).join("");
  return U.grp("", `<div class="tblw"><table class="tbl"><thead><tr><th>الخصم</th><th>مواجهات</th><th>فوز</th><th>تعادل</th><th>خسارة</th></tr></thead><tbody>${tr}</tbody></table></div>`) +
    '<p class="src">من أرشيف تيفو، في كل البطولات.</p>';
}

module.exports = { pairBody, teamBody, key };
