// «كشّاف تيفو» (owner bold idea 6, 2026-10-06): the pool of young Arab players and the points each earns, match by match,
// from Tifo's own match files (the build's finished details: lineups with nationality, age, minutes and rating; the goal events
// with scorer and assist). The game itself (each scout's five, their totals, the board) is the Cards Lambda's
// (saas/cards src/tifo_scout.py), which reads points.json; the page (/scout/, src/scout.js) reads pool.json.
//
// The pool: Arab League nationals (FotMob's three-letter code on the lineup) aged 23 or under at their first match this season,
// named in a lineup (played, or on the bench of their national team) since SEASON_FROM.
// The points of one match (RULES, shown on the page as they are):
//   played +1 · 60 minutes or more +1 · a goal +5 (a penalty too, an own goal never) · an assist +3
//   a rating of 8 or more +3, from 7 +1 · named in his national team's matchday squad +2 (the call-up, even unused)
"use strict";

const SEASON_FROM = "2026-07-01";
const RULES = { played: 1, sixty: 1, goal: 5, assist: 3, r8: 3, r7: 1, squad: 2, maxAge: 23 };
// FotMob's codes for the 22 Arab League members (Lebanon comes as LBN or LIB) -> ISO 3166-1 alpha-2
const ARAB3 = { UAE: "AE", KSA: "SA", QAT: "QA", KUW: "KW", BHR: "BH", OMA: "OM", IRQ: "IQ", JOR: "JO", SYR: "SY", LBN: "LB", LIB: "LB", PLE: "PS",
  YEM: "YE", EGY: "EG", SUD: "SD", LBY: "LY", TUN: "TN", ALG: "DZ", MAR: "MA", MTN: "MR", SOM: "SO", DJI: "DJ", COM: "KM" };
const GOALS = new Set(["goal", "penalty_goal"]);

// one appearance -> its points
function points(a) {
  let p = a.nt ? RULES.squad : 0;
  if (a.mins > 0) {
    p += RULES.played + (a.mins >= 60 ? RULES.sixty : 0) + RULES.goal * a.g + RULES.assist * a.a;
    if (a.rating != null && a.rating >= 8) p += RULES.r8; else if (a.rating != null && a.rating >= 7) p += RULES.r7;
  }
  return p;
}

// a finished match's young Arab appearances: [{id, name, c, age, role, team, teamAr, nt, mins, g, a, rating}]
function appearances(md, natTeams) {
  const out = [], lus = md.lineups || {}, g = {}, as = {};
  for (const e of md.events || []) {
    if (!GOALS.has(e.type)) continue;
    if (e.player && e.player.id) g[e.player.id] = (g[e.player.id] || 0) + 1;
    if (e.assist && e.assist.id) as[e.assist.id] = (as[e.assist.id] || 0) + 1;
  }
  for (const side of ["home", "away"]) {
    const lu = lus[side] || {}, team = md[side] || {}, nt = natTeams.has(+team.id), starters = new Set((lu.starters || []).map(p => p && p.id));
    for (const p of [].concat(lu.starters || [], lu.subs || [])) {
      if (!p || !p.id || !ARAB3[p.country] || p.age == null || p.age > RULES.maxAge + 1) continue;
      const st = starters.has(p.id), on = p.minutes_on, off = p.minutes_off;
      const mins = Math.max(0, st ? (off != null ? off : 90) : (on != null ? (off != null ? off : 90) - on : 0));
      if (!mins && !nt) continue;   // an unused club substitute: no match for the pool
      out.push({ id: +p.id, name: p.name || "", c: ARAB3[p.country], age: +p.age, role: p.role || "", team: +team.id, teamAr: team.name_ar || team.name || "",
        nt, mins, g: g[p.id] || 0, a: as[p.id] || 0, rating: p.rating == null ? null : +p.rating });
    }
  }
  return out;
}

// matches: finished match details; o: {natTeams: Set of national team ids, nameOf: id -> Arabic name, from, now}
function build(matches, o) {
  const from = o.from || SEASON_FROM, natTeams = o.natTeams || new Set(), P = new Map();
  const list = [...matches].filter(md => md && md.status === "finished" && md.kickoff_utc && md.kickoff_utc >= from && md.lineups && md.lineups.home)
    .sort((x, y) => Date.parse(x.kickoff_utc) - Date.parse(y.kickoff_utc) || x.id - y.id);
  for (const md of list) {
    for (const a of appearances(md, natTeams)) {
      let r = P.get(a.id);
      if (!r) P.set(a.id, r = { id: a.id, n: a.name, c: a.c, age: a.age, role: a.role, t: null, tn: "", nt: 0, apps: 0, mins: 0, g: 0, a: 0, pts: 0, rs: [], m: [] });
      r.age = Math.min(r.age, a.age);
      if (a.role) r.role = a.role;
      if (!a.nt) { r.t = a.team; r.tn = a.teamAr; }   // his club: the latest club match (a national team match never replaces it)
      else r.nt++;
      const pts = points(a);
      if (a.mins > 0) { r.apps++; r.mins += a.mins; r.g += a.g; r.a += a.a; if (a.rating != null) r.rs.push(a.rating); }
      r.pts += pts;
      r.m.push([+md.id, md.kickoff_utc, pts, a.mins, a.g, a.a, a.rating, a.nt ? 1 : 0]);
    }
  }
  const players = [...P.values()].filter(r => r.age <= RULES.maxAge && r.m.length);
  const pool = players.map(r => ({ id: r.id, n: (o.nameOf && o.nameOf(r.id)) || r.n, en: r.n, c: r.c, age: r.age, pos: r.role, t: r.t, tn: r.tn, nt: r.nt, apps: r.apps, mins: r.mins,
    g: r.g, a: r.a, pts: r.pts, r: r.rs.length ? Math.round(r.rs.reduce((s, x) => s + x, 0) / r.rs.length * 100) / 100 : null }))
    .sort((x, y) => y.pts - x.pts || y.mins - x.mins || x.id - y.id);
  const pts = {}; players.forEach(r => { pts[r.id] = r.m.map(x => [x[0], x[1], x[2]]); });
  const gen = (o.now || new Date()).toISOString();
  return { pool: { generated: gen, from, rules: RULES, players: pool }, points: { generated: gen, from, rules: RULES, players: pts } };
}

module.exports = { SEASON_FROM, RULES, ARAB3, points, appearances, build };
