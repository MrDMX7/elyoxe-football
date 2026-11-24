// Tifo archive: the pages one pass over every match gives (graph/features_export.py versus) — two teams' every meeting
// (/vs/<lo>-<hi>/, Tifo ids), a team's record against every opponent with its longest runs and its rating year by year
// (/vs/<tid>/), and the ratings (/elo/, /elo/<competition key>/). Facts only: every line is a count, a day or a result.
//
// o: team(tid) a team's page or null · hub(tid) its /vs/<tid>/ or null · pair(a, b) the two's page or null ·
//    match(row) a meeting's page or null · comp(number) {key, name, season(s) -> its season page or null} or null
"use strict";
const U = require("../src/v5/ui.js");

const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const AR = /[؀-ۿ]/;
const txt = s => (AR.test(s || "") ? esc(s) : `<span class="lat">${esc(s || "")}</span>`);
const num = v => `<span class="num">${esc(v)}</span>`;
const a = (href, inner) => (href ? `<a href="${href}">${inner}</a>` : inner);
const td = v => `<td>${num(v)}</td>`;
const table = (head, rows) => `<div class="tblw"><table class="tbl"><thead><tr>${head.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
const nameOf = (N, t) => (N[t] && N[t][0]) || `#${t}`;
const SRC = '<p class="src">محسوب من نتايج المباريات في قاعدة تيفو؛ المباراة اللي ما وصلتنا نتيجتها مب داخلة.</p>';

// a pair's meetings read from the lower id's side: [games, wins, draws, losses, goals for, against]
function tally(ms, keep) {
  const t = [0, 0, 0, 0, 0, 0];
  for (const m of ms) {
    if (keep && !keep(m)) continue;
    const f = m[3] ? m[4] : m[5], g = m[3] ? m[5] : m[4];
    t[0]++; t[f > g ? 1 : f === g ? 2 : 3]++; t[4] += f; t[5] += g;
  }
  return t;
}

// the longest run of wins of each side, and the longest without a draw... kept to wins: [games, from, to]
function runs(ms) {
  const best = [null, null], cur = [[0, null], [0, null]];
  for (const m of ms) {
    const f = m[3] ? m[4] : m[5], g = m[3] ? m[5] : m[4];
    [f > g, g > f].forEach((won, i) => {
      if (!won) { cur[i] = [0, null]; return; }
      cur[i] = [cur[i][0] + 1, cur[i][1] || m[0]];
      if (!best[i] || cur[i][0] > best[i][0]) best[i] = [cur[i][0], cur[i][1], m[0]];
    });
  }
  return best;
}

const score = m => `${num(m[4])} - ${num(m[5])}${m[8] != null ? ` <span class="muted small">(الترجيح ${num(m[8])} - ${num(m[9])})</span>` : ""}`;

function pairStats(lo, hi, ms) {
  const t = tally(ms), home = tally(ms, m => m[3]), away = tally(ms, m => !m[3]);
  const big = [null, null]; let high = null;
  for (const m of ms) {
    const f = m[3] ? m[4] : m[5], g = m[3] ? m[5] : m[4], i = f > g ? 0 : g > f ? 1 : -1;
    if (i >= 0 && (!big[i] || Math.abs(f - g) > big[i][0] || (Math.abs(f - g) === big[i][0] && f + g > big[i][1]))) big[i] = [Math.abs(f - g), f + g, m];
    if (!high || f + g > high[0]) high = [f + g, m];
  }
  return { t, home, away, big, high, run: runs(ms) };
}

function pair(lo, hi, ms, N, o) {
  o = o || {};
  const A = nameOf(N, lo), B = nameOf(N, hi), s = pairStats(lo, hi, ms), t = s.t;
  const side = m => (m[3] ? [lo, hi] : [hi, lo]);
  const line = m => { const [h, w] = side(m); return `${txt(nameOf(N, h))} ${score(m)} ${txt(nameOf(N, w))}`; };
  const head = `<div class="lt"><h1>${txt(A)} و${txt(B)}: كل المواجهات</h1><p>${num(t[0])} مواجهة من ${num(ms[0][0].slice(0, 4))} لين ${num(ms[ms.length - 1][0].slice(0, 4))}: ` +
    `${txt(A)} ${num(t[1])} فوز، تعادل ${num(t[2])}، ${txt(B)} ${num(t[3])} فوز. الأهداف ${num(t[4])} - ${num(t[5])}.</p>` +
    `<p>${[[lo, A], [hi, B]].map(([id, n]) => [o.team && o.team(id) && `<a class="chip" href="${o.team(id)}">${txt(n)}</a>`, o.hub && o.hub(id) && `<a class="chip" href="${o.hub(id)}">سجل ${txt(n)}</a>`].filter(Boolean).join("")).join("")}</p></div>`;
  const rec = (label, r) => `<tr><td>${label}</td>${[r[0], r[1], r[2], r[3], r[4], r[5]].map(td).join("")}</tr>`;
  const where = s.home[0] && s.away[0] ? U.grp("السجل حسب صاحب الأرض", table(["", "لعب", `فوز ${txt(A)}`, "تعادل", `فوز ${txt(B)}`, `أهداف ${txt(A)}`, `أهداف ${txt(B)}`],
    [rec("الكل", t), rec(`${txt(A)} صاحب الأرض`, s.home), rec(`${txt(B)} صاحب الأرض`, s.away)])) : "";
  const by = new Map();
  for (const m of ms) { if (!by.has(m[1])) by.set(m[1], []); by.get(m[1]).push(m); }
  const cname = c => { const x = c && o.comp && o.comp(c); return x ? x.name : null; };
  const comps = [...by.entries()].filter(e => cname(e[0])).sort((x, y) => y[1].length - x[1].length);
  const byComp = comps.length > 1 ? U.grp("حسب البطولة", table(["البطولة", "لعب", `فوز ${txt(A)}`, "تعادل", `فوز ${txt(B)}`], comps.map(([c, l]) => {
    const r = tally(l), x = o.comp(c); return `<tr><td>${a(x.key ? `/c/${x.key}/` : null, txt(x.name))}</td>${[r[0], r[1], r[2], r[3]].map(td).join("")}</tr>`; }))) : "";
  const facts = [
    U.row({ t: "أول مواجهة", sub: line(ms[0]), v: U.dateAr(ms[0][0]), href: o.match && o.match(ms[0]) }),
    U.row({ t: "آخر مواجهة", sub: line(ms[ms.length - 1]), v: U.dateAr(ms[ms.length - 1][0]), href: o.match && o.match(ms[ms.length - 1]) }),
    s.big[0] && U.row({ t: `أكبر فوز لـ${txt(A)}`, sub: line(s.big[0][2]), v: U.dateAr(s.big[0][2][0]), href: o.match && o.match(s.big[0][2]) }),
    s.big[1] && U.row({ t: `أكبر فوز لـ${txt(B)}`, sub: line(s.big[1][2]), v: U.dateAr(s.big[1][2][0]), href: o.match && o.match(s.big[1][2]) }),
    s.high && s.high[0] >= 5 && U.row({ t: `أكثر مباراة أهداف: ${num(s.high[0])}`, sub: line(s.high[1]), v: U.dateAr(s.high[1][0]), href: o.match && o.match(s.high[1]) }),
    s.run[0] && s.run[0][0] >= 3 && U.row({ t: `أطول سلسلة انتصارات لـ${txt(A)}`, sub: `${U.dateAr(s.run[0][1])} لين ${U.dateAr(s.run[0][2])}`, v: `${num(s.run[0][0])} مواجهات` }),
    s.run[1] && s.run[1][0] >= 3 && U.row({ t: `أطول سلسلة انتصارات لـ${txt(B)}`, sub: `${U.dateAr(s.run[1][1])} لين ${U.dateAr(s.run[1][2])}`, v: `${num(s.run[1][0])} مواجهات` }),
  ].filter(Boolean).join("");
  const list = ms.slice().reverse().map(m => { const x = m[1] && o.comp && o.comp(m[1]);
    return U.row({ t: line(m), sub: x ? `${txt(x.name)}${m[2] ? ` <span class="num">${num(m[2])}</span>` : ""}` : "", v: U.dateAr(m[0]), href: o.match && o.match(m) }); }).join("");
  return head + where + byComp + U.grp("أرقام المواجهة", facts) + U.grp("كل المواجهات", list) + SRC;
}

const pairTitle = (lo, hi, N) => `${nameOf(N, lo)} ضد ${nameOf(N, hi)}: كل المواجهات والنتايج عبر التاريخ | تيفو`;
function pairDesc(lo, hi, ms, N) {
  const t = tally(ms);
  return `${t[0]} مواجهة بين ${nameOf(N, lo)} و${nameOf(N, hi)} من ${ms[0][0].slice(0, 4)}: ${nameOf(N, lo)} ${t[1]} فوز، تعادل ${t[2]}، ${nameOf(N, hi)} ${t[3]} فوز، وكل النتايج.`;
}

// a rating year by year: one line, its first and last year and its highest and lowest under it
function chart(yr) {
  if (!yr || yr.length < 5) return "";
  const W = 600, H = 140, lo = Math.min(...yr.map(y => y[1])), hi = Math.max(...yr.map(y => y[1])), y0 = yr[0][0], y1 = yr[yr.length - 1][0];
  const px = y => (y1 === y0 ? 0 : ((y - y0) / (y1 - y0)) * W).toFixed(1), py = v => (hi === lo ? H / 2 : H - 6 - ((v - lo) / (hi - lo)) * (H - 12)).toFixed(1);
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="التصنيف سنة بسنة" style="display:block;width:100%;height:auto" dir="ltr"><polyline fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" points="${
    yr.map(y => `${px(y[0])},${py(y[1])}`).join(" ")}"/></svg><p class="muted small" dir="ltr" style="display:flex;justify-content:space-between">${num(y0)}${num(`${lo} – ${hi}`)}${num(y1)}</p>`;
}

const RUN = { win: "أطول سلسلة انتصارات", unbeaten: "أطول سلسلة بلا خسارة", scored: "أطول سلسلة تسجيل", clean: "أطول سلسلة بشباك نظيفة", winless: "أطول سلسلة بلا فوز", lost: "أطول سلسلة خسارات" };

function team(tid, d, N, o) {
  o = o || {};
  const nm = nameOf(N, tid), t = d.tot, e = d.elo || {};
  const head = `<div class="lt"><h1>سجل ${txt(nm)} التاريخي</h1><p>${num(t[0])} مباراة في أرشيف تيفو من ${num(d.first.slice(0, 4))} لين ${num(d.last.slice(0, 4))}: ${num(t[1])} فوز و${num(t[2])} تعادل و${num(t[3])} خسارة، ${num(t[4])} هدف له و${num(t[5])} عليه.</p>${
    o.team && o.team(tid) ? `<p><a class="chip" href="${o.team(tid)}">صفحة ${txt(nm)}</a></p>` : ""}</div>`;
  const run = Object.keys(RUN).filter(k => d.run && d.run[k]).map(k => U.row({ t: RUN[k], sub: `${U.dateAr(d.run[k][1])} لين ${U.dateAr(d.run[k][2])}`, v: `${num(d.run[k][0])} مباراة` })).join("");
  const elo = e.peak ? U.grp("تصنيف تيفو (Elo)", [U.row({ t: "التصنيف الحين", v: num(e.now) }), U.row({ t: "أعلى تصنيف", sub: U.dateAr(e.peak[1]), v: num(e.peak[0]) }),
    U.row({ t: "أدنى تصنيف", sub: U.dateAr(e.low[1]), v: num(e.low[0]) })].join("") + chart(e.yr), o.elo ? { more: o.elo } : undefined) : "";
  const many = d.opp.filter(r => r[1] >= 2), once = d.opp.length - many.length;
  const rows = (many.length ? many : d.opp).map(r => `<tr><td>${a(o.pair && o.pair(tid, r[0]), txt(nameOf(N, r[0])))}</td>${r.slice(1).map(td).join("")}</tr>`);
  const opp = U.grp("ضد كل خصم", table(["الخصم", "لعب", "ف", "ت", "خ", "له", "عليه"], rows) +
    (many.length && once ? `<p class="note">و${num(once)} خصم لعب ضده مباراة وحدة.</p>` : ""));
  return head + (run ? U.grp("أطول السلاسل", run) : "") + elo + opp + SRC;
}

const METHOD = '<p class="src">تصنيف تيفو بطريقة Elo: كل فريق يبدأ من <span class="num">1500</span>، وبعد كل مباراة ياخذ الفايز نقاط من الخاسر على قد المفاجأة وفرق الأهداف ووزن البطولة، وصاحب الأرض محسوب له. محسوب من كل مباراة في قاعدة تيفو.</p>';

function ranking(rows, N, o, peak) {
  return table(["#", "الفريق", "التصنيف"].concat(peak ? ["أعلى تصنيف"] : []), rows.map((r, i) => `<tr><td>${num(i + 1)}</td><td>${a((o.hub && o.hub(r[0])) || (o.team && o.team(r[0])), txt(nameOf(N, r[0])))}</td>${td(r[1])}${
    peak ? `<td>${r[2] != null ? `${num(r[2])} <span class="muted small num">${esc(String(r[3] || "").slice(0, 4))}</span>` : ""}</td>` : ""}</tr>`));
}

// nations: {day, now, peaks}; leagues: [{key, name, n}] the leagues with a page
function eloHub(nations, leagues, N, o) {
  o = o || {};
  const head = `<div class="lt"><h1>تصنيف تيفو للمنتخبات والأندية</h1><p>${num(nations.now.length)} منتخب مرتبين بقوتهم لين ${U.dateAr(nations.day)}، وأندية ${num(leagues.length)} دوري.</p></div>`;
  const peaks = table(["#", "المنتخب", "أعلى تصنيف", "اليوم"], nations.peaks.map((r, i) => `<tr><td>${num(i + 1)}</td><td>${a((o.hub && o.hub(r[0])) || (o.team && o.team(r[0])), txt(nameOf(N, r[0])))}</td>${td(r[1])}<td>${U.dateAr(r[2])}</td></tr>`));
  return head + U.grp("المنتخبات الحين", ranking(nations.now, N, o, 1)) + U.grp("أقوى المنتخبات في التاريخ", peaks) +
    (leagues.length ? U.grp("تصنيف الأندية حسب الدوري", leagues.map(l => U.row({ href: `/elo/${l.key}/`, t: txt(l.name), v: `${num(l.n)} فريق` })).join("")) : "") + METHOD;
}

function eloLeague(c, rows, N, o) {
  o = o || {};
  return `<div class="lt"><h1>تصنيف أندية ${txt(c.name)}</h1><p>${num(rows.length)} فريق من آخر موسم، مرتبين بقوتهم حسب نتايجهم في كل تاريخهم.</p><p><a class="chip" href="/c/${c.key}/">${txt(c.name)}</a><a class="chip" href="/elo/">كل التصنيفات</a></p></div>` +
    U.grp("", ranking(rows, N, o, 1)) + METHOD;
}

module.exports = { pair, pairTitle, pairDesc, pairStats, team, eloHub, eloLeague, tally, runs, chart };
