// «رجل المباراة» (Tifo graph phase 3, spec §8): /motm/ and the player pages' block, from v1/motm/index.json and
// v1/motm/players.json (graph/publish.py). The pick is FotMob's: the match's highest rating. A player links to /p/ only when
// the site has his page; a name with no Arabic form is shown in Latin.
"use strict";
const U = require("../src/v5/ui.js");

const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const AR = /[؀-ۿ]/;
const nm = s => AR.test(s || "") ? esc(s) : `<span class="lat">${esc(s || "")}</span>`;
const num = v => `<span class="num">${esc(v)}</span>`;
const times = n => n === 1 ? "مرة" : n === 2 ? "مرتين" : n <= 10 ? `${num(n)} مرات` : `${num(n)} مرة`;

function hubBody(ix, o) {
  o = o || {};
  const link = (id, name) => o.hasPage && o.hasPage(id) ? `<a href="/p/${id}/">${AR.test(name || "") ? esc(name) : nm(name)}</a>` : nm(name);
  const list = l => `<ol class="lc">${(l || []).slice(0, 20).map(([id, name, k]) => `<li>${link(id, name)} <span class="muted small">${times(k)}</span></li>`).join("")}</ol>`;
  const comps = Object.keys(ix.comps || {}).map(Number).map(id => [id, o.comp && o.comp(id), ix.comps[id]]).filter(x => x[1] && ((x[2].season || []).length || (x[2].all || []).length));
  return U.grp(`هالموسم <span class="muted small">من ${num(ix.since || "")}</span>`, list(ix.leaders && ix.leaders.season)) +
    U.grp("عبر التاريخ", list(ix.leaders && ix.leaders.all)) +
    comps.map(([id, c, d]) => U.grp(`<a href="${esc(c.href || "#")}">${esc(c.name_ar)}</a>`,
      ((d.season || []).length ? `<p class="muted small">هالموسم</p>${list(d.season)}` : "") + `<p class="muted small">عبر التاريخ</p>${list(d.all)}`)).join("") +
    '<p class="src">رجل المباراة = صاحب أعلى تقييم في المباراة من FotMob، لكل مباراة لها تقييمات في قاعدة تيفو.</p>';
}

function playerBlock(rec, o) {
  if (!rec || !rec.total) return "";
  o = o || {};
  const seasons = Object.entries(rec.seasons || {}).sort((a, b) => (a[0] < b[0] ? 1 : -1));
  const comps = Object.entries(rec.comps || {}).map(([id, k]) => [o.comp && o.comp(+id), k]).filter(x => x[0]);
  const rows = [{ icon: "crown", c: "#FFCC00", t: `رجل المباراة ${times(rec.total)}`, sub: seasons.length ? `آخر موسم ${num(seasons[0][0])}: ${times(seasons[0][1])}` : "" }]
    .concat(comps.slice(0, 4).map(([c, k]) => ({ href: c.href || null, icon: "medal", c: "#34C759", t: esc(c.name_ar), v: times(k) })));
  const recent = (rec.recent || []).slice(0, 5).map(([mid, d, r, opp]) => {
    const vs = o.team && o.team(opp) ? `ضد ${esc(o.team(opp))}` : "";
    const t = `${vs} <span class="muted small num">${esc(d)}</span> <span class="num">${esc(r)}</span>`;
    return o.match && o.match(mid) ? `<li><a href="/m/${mid}/">${t}</a></li>` : `<li>${t}</li>`;
  }).join("");
  return U.grp("رجل المباراة", U.rows(rows) + (recent ? `<ul class="lc">${recent}</ul>` : ""), { more: '<a class="more" href="/motm/">الكل</a>' });
}

module.exports = { hubBody, playerBlock };
