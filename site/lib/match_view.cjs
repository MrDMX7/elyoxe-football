// An old match (v1/matches/*: the archive's compact record) in the shapes the current match page takes (src/v5/pages.js P.match),
// so it looks like a match of today (owner 2026-11-22: «حتى المباريات بالطريقة الحالية»): header, events, lineups, info, meetings.
// The lineups are lists: the archive holds no positions to draw on the pitch.
"use strict";
const U = require("../src/v5/ui.js");

const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const team = (id, name, k) => (id ? { id, name_ar: name } : { id: "n" + k + "-" + String(name || "").replace(/\s+/g, "-"), name_ar: name, nocrest: true });

function md(m) {
  return { id: m.id, comp: m.comp, round: m.round != null && m.round !== "" ? String(m.round) : null, status: "finished",
    score: { home: m.s[0], away: m.s[1] }, penalties: m.pen ? { home: m.pen[0], away: m.pen[1] } : null, halftime_score: m.ht ? { home: m.ht[0], away: m.ht[1] } : null,
    kickoff_utc: (m.date || "") + "T12:00:00Z", time_tbd: true, date_fmt: "dy", home: team(m.h[0], m.h[1], "h"), away: team(m.a[0], m.a[1], "a"),
    events: (m.ev || []).map(e => ({ minute: e[0], added: e[1] || 0, type: e[2], team: e[3] === "a" ? "away" : "home", player: e[4] ? { id: e[5], name: e[4] } : null })),
    venue: m.venue ? { name_ar: m.venue } : null, referee: m.ref ? { name: m.ref } : null };
}

// the two sides' players as lists in the current page's style: the coach, the starters, the bench (a source that marked no
// starter: who played)
function lineups(m, d) {
  const L = m.lu || {};
  if (!(L.h || []).length && !(L.a || []).length) return null;
  const row = p => U.row({ href: p[1] ? "/p/" + p[1] + "/" : null, t: (p[2] ? '<span class="num muted">' + esc(p[2]) + "</span> " : "") + U.pname({ id: p[1], name: p[0] }) });
  const side = k => { const l = L[k] || [], co = (m.co || {})[k], st = l.filter(p => p[3] !== 0), sb = l.filter(p => p[3] === 0), marked = l.some(p => p[3] === 1);
    return (co ? U.grp("المدرب", '<div class="row"><span class="rt">' + U.pname({ name: co }) + "</span></div>") : "") +
      (marked ? U.grp("الأساسيين", st.map(row).join("")) + (sb.length ? U.grp("البدلاء", sb.map(row).join("")) : "") : U.grp("شاركوا في المباراة", l.map(row).join(""))); };
  return '<div class="mt2">' + U.seg("lu", [["home", U.tname(d.home)], ["away", U.tname(d.away)]], "home", { sm: 1 }) + "</div>" + U.pane("lu", "home", side("h"), true) + U.pane("lu", "away", side("a"));
}

// the meetings before this match from the every-competition pair file (v1/h2h-all/<a>-<b>.json): the record from this match's
// sides, the latest meetings first
function h2h(pair, d) {
  if (!pair) return null;
  const hi = String(d.home.id), before = (pair.matches || []).filter(x => x[0] < d.kickoff_utc.slice(0, 10) && x[4] != null && x[5] != null);
  if (!before.length) return null;
  const s = { home_wins: 0, draws: 0, away_wins: 0 };
  before.forEach(x => { const w = x[4] > x[5] ? x[3] : x[5] > x[4] ? x[6] : null; if (w == null) s.draws++; else if (String(w) === hi) s.home_wins++; else s.away_wins++; });
  const nm = id => pair.names[pair.teams.indexOf(String(id))] || "", side = id => (/^\d+$/.test(String(id)) ? { id: +id, name_ar: nm(id) } : { id: "n-" + id, name_ar: nm(id), nocrest: true });
  return { summary: s, matches: before.slice().reverse().map(x => ({ id: x[7], href: "/m/" + x[7] + "/", kickoff_utc: x[0] + "T12:00:00Z", home: side(x[3]), away: side(x[6]), score: { home: x[4], away: x[5] } })) };
}

// every two teams' meetings in the archive's own matches (v1/matches/*: the leagues' seasons and the tournaments), in the
// every-competition pair files' shape, for the pairs those files do not hold (graph/publish.h2h covers the UAE's)
function pairs(lists, compName) {
  const out = new Map(), seen = new Set();
  for (const ms of lists) for (const m of ms) {
    if (seen.has(m.id) || !m.h[0] || !m.a[0] || !m.s || m.s[0] == null) continue;
    seen.add(m.id);
    const a = String(m.h[0]), b = String(m.a[0]), key = [a, b].sort().join("-");
    if (!out.has(key)) out.set(key, { teams: [a, b].sort(), names: [], matches: [] });
    const p = out.get(key);
    p.names[p.teams.indexOf(a)] = m.h[1];
    p.names[p.teams.indexOf(b)] = m.a[1];
    p.matches.push([m.date, compName(m.comp) || "", m.season || "", a, m.s[0], m.s[1], b, m.id]);
  }
  for (const p of out.values()) p.matches.sort((x, y) => (x[0] < y[0] ? -1 : x[0] > y[0] ? 1 : 0));
  return out;
}

// every player's matches in the archive (in a lineup, or a scorer of a match with none), and his goals (own goals not his)
function players(lists) {
  const out = new Map(), seen = new Set();
  const at = (k, m) => { if (!k) return null; if (!out.has(k)) out.set(k, { matches: [], goals: 0, ids: new Set() }); const p = out.get(k); if (!p.ids.has(m.id)) { p.ids.add(m.id); p.matches.push(m); } return p; };
  for (const ms of lists) for (const m of ms) {
    if (seen.has(m.id)) continue;
    seen.add(m.id);
    for (const side of Object.values(m.lu || {})) for (const p of side) at(p[1], m);
    for (const e of m.ev || []) if (/^(goal|penalty_goal)$/.test(e[2]) && e[5]) at(e[5], m).goals++;
  }
  for (const p of out.values()) { p.matches.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0)); delete p.ids; }
  return out;
}

// the player page's block: how many matches and goals the archive holds for him, and the latest of them in the current rows
function playerBlock(d, n) {
  if (!d || !d.matches.length) return "";
  const SV = require("./season_view.cjs"), rows = SV.fixtures(d.matches.slice(0, n || 15)).matches.map(m => U.mrow(m, { date: 1 })).join("");
  return U.grp("مبارياته في أرشيف تيفو", '<p class="note">' + '<span class="num">' + d.matches.length + "</span> مباراة و" + '<span class="num">' + d.goals + "</span> هدف في الأرشيف.</p>" + rows);
}

module.exports = { md, lineups, h2h, pairs, players, playerBlock };
