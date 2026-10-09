// The transfer market of every club (spec docs/superpowers/specs/2026-10-09-transfers-design.md, phase 1): the ledger
// v1/transfers/all.json (db/transfers_world.py) -> /transfers/, /transfers/<league>/ and the club's «انتقالات هالموسم».
// A move: [date, player id, name, from id, from, to id, to, fee EUR | null, kind, market value, nationality, position]
const ARAB = new Set(["UAE", "KSA", "QAT", "KUW", "BHR", "OMA", "IRQ", "JOR", "LBN", "SYR", "PLE", "YEM", "EGY", "LBY", "TUN", "ALG", "MAR", "SDN", "MTN", "COM", "DJI", "SOM"]);
const NO_CLUB = new Set([null, undefined, 0, 2]);   // FotMob's «Free agent» / «Without club» is team 2
const KIND = { loan: "إعارة", free: "انتقال حر", undisclosed: "مبلغ ما انعلن" };
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const AR = /[؀-ۿ]/;
const nm = s => AR.test(s || "") ? esc(s) : `<span class="lat">${esc(s)}</span>`;

const season = (moves, since) => (moves || []).filter(m => m && m[0] >= since);
const top = (moves, n) => moves.filter(m => m[7]).sort((a, b) => b[7] - a[7] || (b[0] > a[0] ? 1 : -1)).slice(0, n);
const arabs = moves => moves.filter(m => ARAB.has(m[10]));
// a league's moves: in or out of one of its clubs ({club id: 1})
const league = (moves, clubs) => moves.filter(m => clubs[m[3]] || clubs[m[5]]);

function forClub(moves, id) {
  const In = moves.filter(m => +m[5] === +id), Out = moves.filter(m => +m[3] === +id);
  const sum = l => l.reduce((a, m) => a + (m[8] === "fee" && m[7] ? m[7] : 0), 0);
  return { id, in: In, out: Out, spent: sum(In), received: sum(Out) };
}

function eur(v) {
  if (!v) return "";
  return v >= 1e6 ? `<span class="num">€${Math.round(v / 1e5) / 10}</span> مليون` : `<span class="num">€${Math.round(v / 1e3)}</span> ألف`;
}
const cn = (id, name, o) => (o && o.cname && o.cname(id)) || name;
const club = (id, name, o) => NO_CLUB.has(id) ? "بدون نادي" : `<a href="/t/${id}/">${nm(cn(id, name, o))}</a>`;
// «من أرسنال» / «للهلال», «لـبرشلونة» (the preposition inside the link: the build's «لـال» -> «لل» fix works on one text node);
// no club on the other side: «لاعب حر،» before, «صار بدون نادي» after
const from = (id, name, o) => NO_CLUB.has(id) ? "لاعب حر،" : `من ${club(id, name, o)}`;
function to(id, name, o) {
  if (NO_CLUB.has(id)) return "صار بدون نادي";
  const n = cn(id, name, o);
  return AR.test(n || "") ? `<a href="/t/${id}/">${/^ال/.test(n) ? "لل" + esc(n.slice(2)) : "لـ" + esc(n)}</a>` : `لـ${club(id, name, o)}`;
}
const dm = d => `<span class="num">${+d.slice(8, 10)}/${+d.slice(5, 7)}</span>`;

// one move: the player, from -> to, the kind or the fee; o.pname / o.cname: the site's Arabic names first
function row(m, o) {
  o = o || {};
  const side = o.side === "in" ? from(m[3], m[4], o).replace(/،$/, "") : o.side === "out" ? to(m[5], m[6], o) : `${from(m[3], m[4], o)} ${to(m[5], m[6], o)}`;
  const what = m[8] === "fee" && m[7] ? eur(m[7]) : m[8] === "free" && NO_CLUB.has(m[5]) ? "" : KIND[m[8]] || "";
  return `<li><span class="muted small">${dm(m[0])}</span> <a href="/p/${m[1]}/">${nm((o.pname && o.pname(m[1])) || m[2])}</a> <span class="muted">${side}</span>${what ? ` <b>${what}</b>` : ""}</li>`;
}
const list = (moves, o) => `<ul class="wcl">${moves.map(m => row(m, o)).join("")}</ul>`;
const withSide = (o, side) => Object.assign({}, o, { side });

// the club's window: arrivals, departures, money in and out; "" with no move
function clubSection(c, o) {
  if (!c || (!c.in.length && !c.out.length)) return "";
  const money = [c.spent ? `صرف ${eur(c.spent)}` : "", c.received ? `باع بـ${eur(c.received)}` : ""].filter(Boolean).join("، ");
  return (money ? `<p>${money}.</p>` : "") +
    (c.in.length ? `<h3>جاه (<span class="num">${c.in.length}</span>)</h3>${list(c.in, withSide(o, "in"))}` : "") +
    (c.out.length ? `<h3>راح (<span class="num">${c.out.length}</span>)</h3>${list(c.out, withSide(o, "out"))}` : "");
}

// ---- phase 3: rumours (db/transfers_world.py merge_rumours -> v1/transfers/rumours.json) and contracts running out
const PROB = { Low: "احتمال ضعيف", Medium: "احتمال متوسط", High: "احتمال قوي", Imminent: "وشيكة" };
const STAGE = { rumour: "إشاعة", talks: "مفاوضات", agreed: "اتفاق", here_we_go: "Here we go", official: "رسمي" };
function rumourRow(r, o) {
  o = o || {};
  const side = [r.from ? `من ${club(r.from[0], r.from[1], o)}` : "", r.to ? to(r.to[0], r.to[1], o) : ""].filter(Boolean).join(" ");
  const s = (r.stories || [])[0];
  const tag = r.out === "done" ? "صدقت" : r.out === "no" ? "ما صدقت" : STAGE[r.stage] || "";
  // the headline only in Arabic (the site's news is Arabic only); a foreign one leaves just its source
  const meta = [PROB[r.prob], r.fee && r.out !== "no" ? eur(r.fee) : "", s ? (AR.test(s[1] || "") ? `«${esc(s[1])}»` : "") + (s[3] ? (AR.test(s[1] || "") ? " · " : "المصدر: ") + nm(s[3]) : "") : ""].filter(Boolean).join(" · ");
  return `<li><span class="muted small">${dm(r.done || r.last || r.first)}</span> <a href="/p/${r.pid}/">${nm((o.pname && o.pname(r.pid)) || r.name)}</a>` +
    (side ? ` <span class="muted">${side}</span>` : "") + (tag ? ` <b>${tag}</b>` : "") + (meta ? `<br><span class="muted small">${meta}</span>` : "") + "</li>";
}
const rumourList = (R, o) => `<ul class="wcl">${R.map(r => rumourRow(r, o)).join("")}</ul>`;
// a club's (to or from it) or a player's rumours, the open ones first; o.open: the open ones only
function rumoursOf(R, q) {
  const hit = r => (q.pid != null && +r.pid === +q.pid) || (q.club != null && ((r.to && +r.to[0] === +q.club) || (r.from && +r.from[0] === +q.club)));
  return (R || []).filter(r => hit(r) && (!q.open || !r.out)).sort((a, b) => (!!a.out - !!b.out) || ((b.last || "") > (a.last || "") ? 1 : -1));
}
// players whose contract ends by next 30 June: [[id, name, team, date]], soonest first (FotMob's history/fm/players.json)
function expiring(P, today) {
  const until = `${+today.slice(0, 4) + (today.slice(5) > "06-30" ? 1 : 0)}-06-30`;
  const players = Object.entries(P || {}).filter(([, p]) => p && p.contract && p.contract >= today && p.contract <= until)
    .map(([id, p]) => [id, p.name, p.team, p.contract]).sort((a, b) => a[3] < b[3] ? -1 : a[3] > b[3] ? 1 : 0);
  return { until, players };
}

module.exports = { ARAB, season, top, arabs, league, forClub, eur, row, list, clubSection, PROB, STAGE, rumourRow, rumourList, rumoursOf, expiring };
