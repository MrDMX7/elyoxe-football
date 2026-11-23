// The archive's referee (/r/k<Tifo id>/) and club (/t/k<Tifo id>/) pages, from graph/archive_export referees and clubs: a
// referee's games and cards by season and his last games; an old club's record by season, its titles and its last games. The
// owner, 22 Nov 2026: «كل المدربين كل الكروت كل الحكام».
"use strict";
const U = require("../src/v5/ui.js");

const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const AR = /[؀-ۿ]/;
const num = v => `<span class="num">${esc(v)}</span>`;
const txt = s => (AR.test(s || "") ? esc(s) : `<span class="lat">${esc(s || "")}</span>`);
const nameOf = x => (x.ar && AR.test(x.ar) ? x.ar : x.n) || "";
const seasonHref = (o, fid, season) => (fid && o.comp && o.comp(fid) ? `/c/${o.comp(fid).key}/s/${String(season).replace(/\//g, "-")}/` : null);
const head = x => `<div class="lt"><h1>${txt(nameOf(x))}</h1>${x.ar && x.n && x.ar !== x.n ? `<p class="muted"><span class="lat">${esc(x.n)}</span></p>` : ""}${x.c ? `<p class="muted">${txt(x.c)}</p>` : ""}</div>`;
// the row links the match; a club link inside it would be a link in a link, which the browser splits into broken rows
const lastGames = (x, title) => ((x.last || []).length ? U.grp(title, x.last.map(m => U.row({ href: `/m/${m[0]}/`,
  t: `${txt(m[2])} ${num(`${m[6]}-${m[7]}`)} ${txt(m[4])}`, sub: U.dateAr(m[1]) })).join("")) : "");

function referee(r, o) {
  o = o || {};
  const ms = r.ms || [], t = ms.reduce((a, s) => [a[0] + s[3], a[1] + s[4], a[2] + s[5]], [0, 0, 0]);
  const per = t[0] ? (t[1] / t[0]).toFixed(1) : "0";
  return head(r) + U.grp("", `<p class="note">${num(t[0])} مباراة في أرشيف تيفو، ${num(t[1])} إنذار و${num(t[2])} طرد (${num(per)} إنذار في المباراة).</p>`) +
    U.grp("مبارياته موسم بموسم", ms.map(s => U.row({ t: `${num(s[0])} · ${txt(s[2])}`, sub: `${num(s[3])} مباراة · ${num(s[4])} إنذار · ${num(s[5])} طرد`,
      href: seasonHref(o, s[1], s[0]) })).join("")) + lastGames(r, "آخر مبارياته");
}

function club_(c, o) {
  o = o || {};
  const ss = c.ss || [], hon = c.hon || [];
  const tot = ss.reduce((a, s) => a.map((v, i) => v + (s[3 + i] || 0)), [0, 0, 0, 0, 0, 0]);
  const titles = hon.length ? U.grp("ألقابه", hon.map(h => U.row({ t: `${h[0] === "champion" ? "بطل" : "وصيف"} · ${txt(h[1])}`, sub: num(h[3]), href: seasonHref(o, h[2], h[3]) })).join("")) : "";
  const td = v => `<td>${num(v)}</td>`;
  const table = ss.length ? U.grp("موسم بموسم", `<div class="tblw"><table class="tbl"><thead><tr><th>الموسم</th><th>البطولة</th><th>لعب</th><th>ف</th><th>ت</th><th>خ</th><th>له</th><th>عليه</th></tr></thead><tbody>${
    ss.map(s => { const h = seasonHref(o, s[1], s[0]); return `<tr><td>${h ? `<a href="${h}">${num(s[0])}</a>` : num(s[0])}</td><td>${txt(s[2])}</td>${s.slice(3, 9).map(td).join("")}</tr>`; }).join("")}</tbody></table></div>`) : "";
  return head(c) + U.grp("", `<p class="note">${num(tot[0])} مباراة في أرشيف تيفو: ${num(tot[1])} فوز و${num(tot[2])} تعادل و${num(tot[3])} خسارة، ${num(tot[4])} هدف له و${num(tot[5])} عليه.</p>`) +
    titles + table + lastGames(c, "آخر مبارياته في الأرشيف");
}

// a coach (graph/archive_export.coaches): his record, every bench club by club, his awards, his last games, and his playing
// days when he has a profile (/coach/k<Tifo id>/; the owner, 22 Nov 2026: «كل المدربين»)
const team = (name, fm, o) => (fm && o.team && o.team(fm) ? `<a href="/t/${fm}/">${txt(name)}</a>` : txt(name));
const yearOf = d => String(d || "").slice(0, 4);
const coachGames = c => (c.sp || []).reduce((a, s) => a + s[4], 0);

function coach(c, o) {
  o = o || {};
  const sp = c.sp || [], t = sp.reduce((a, s) => a.map((v, i) => v + s[4 + i]), [0, 0, 0, 0]);
  const facts = [c.b && U.row({ t: "تاريخ الميلاد", v: U.dateAr(c.b) }), c.nat && U.row({ t: "الجنسية", v: txt(c.nat) }),
    c.pid != null && o.person && o.person(c.pid) && U.row({ href: `/p/k${c.pid}/`, t: "مسيرته لاعباً" })].filter(Boolean);
  const pct = (w, m) => (m ? Math.round((100 * w) / m) : 0);
  const td = v => `<td>${num(v)}</td>`;
  const table = sp.length ? U.grp("مسيرته التدريبية", `<div class="tblw"><table class="tbl"><thead><tr><th>الفريق</th><th>الفترة</th><th>م</th><th>ف</th><th>ت</th><th>خ</th><th>الفوز</th></tr></thead><tbody>${
    sp.map(s => `<tr><td>${team(s[0], s[1], o)}</td><td>${num(yearOf(s[2]) === yearOf(s[3]) ? yearOf(s[2]) : `${yearOf(s[2])}–${yearOf(s[3])}`)}</td>${s.slice(4, 8).map(td).join("")}<td>${num(pct(s[5], s[4]))}%</td></tr>`).join("")}</tbody></table></div>`) : "";
  const hon = (c.hon || []).filter(h => h[1] === 1);
  const awards = hon.length ? U.grp("جوائزه", hon.map(h => U.row({ t: txt(h[2]), sub: num(h[4]), href: h[3] && o.comp && o.comp(h[3]) ? `/c/${o.comp(h[3]).key}/` : null })).join("")) : "";
  return (o.photo ? require("./person_view.cjs").header(c, o.photo) : head(c)) + (facts.length ? U.grp("", facts.join("")) : "") +
    (t[0] ? U.grp("", `<p class="note">${num(t[0])} مباراة على الدكة في أرشيف تيفو: ${num(t[1])} فوز و${num(t[2])} تعادل و${num(t[3])} خسارة (${num(pct(t[1], t[0]))}% فوز).</p>`) : "") +
    awards + table + lastGames(c, "آخر مبارياته");
}

const coachIndexable = c => coachGames(c) >= 30 || (c.hon || []).some(h => h[1] === 1);
const refIndexable = r => (r.ms || []).reduce((a, s) => a + s[3], 0) >= 20;
const clubIndexable = c => (c.hon || []).length > 0 || (c.ss || []).reduce((a, s) => a + s[3], 0) >= 100;

module.exports = { referee, club: club_, coach, refIndexable, clubIndexable, coachIndexable, nameOf };
