// Tifo graph phase 6, at the whistle: the graph's man-of-the-match files (v1/motm/*, graph/publish.py) are built nightly; the
// site adds every match that finished since, from the match details the poller writes at the final whistle, so the hourly
// build is never a day behind. Same rule as graph/load/motm.py: the top FotMob rating among the players who played (ties:
// goals + assists, then the lower id). The index lists the FotMob ids it already counted in its last 21 days, so nothing
// counts twice; a file without that list predates phase 6 and is left alone.
"use strict";

const GOALS = new Set(["goal", "penalty_goal"]);
const day = s => String(s || "").slice(0, 10);
const minus = (d, n) => new Date(Date.parse(d + "T00:00:00Z") - n * 864e5).toISOString().slice(0, 10);
const rank = l => l.sort((a, b) => b[2] - a[2] || a[0] - b[0]);

function pick(md) {
  if (!md || md.status !== "finished" || !md.lineups) return null;
  const ga = {};
  (md.events || []).forEach(e => { if (GOALS.has(e.type)) [e.player, e.assist].forEach(p => { if (p && p.id) ga[p.id] = (ga[p.id] || 0) + 1; }); });
  let best = null;
  for (const side of ["home", "away"]) {
    const l = md.lineups[side]; if (!l) continue;
    for (const p of (l.starters || []).concat(l.subs || [])) {
      if (p.rating == null || !p.id) continue;
      const k = [+p.rating, ga[p.id] || 0, -p.id];
      if (!best || k[0] > best.k[0] || (k[0] === best.k[0] && (k[1] > best.k[1] || (k[1] === best.k[1] && k[2] > best.k[2]))))
        best = { k, id: p.id, name: p.name, team: (md[side] || {}).id, opp: (md[side === "home" ? "away" : "home"] || {}).id, rating: +p.rating };
    }
  }
  return best && { id: best.id, name: best.name, team: best.team, opp: best.opp, rating: best.rating };
}

// one more for w in a leaders list capped at cap: exact when the total is known; otherwise +1 for someone listed, or 1 for a
// newcomer while the list is under its cap (then it holds everyone with one or more); a full list can't place a newcomer
function bump(list, w, cap, exact) {
  const e = list.find(r => r[0] === w.id);
  if (e) e[2] = exact != null ? exact : e[2] + 1;
  else if (exact != null || list.length < cap) list.push([w.id, w.name, exact != null ? exact : 1]);
  rank(list).splice(cap);
}

function apply(ix, players, mds) {
  if (!ix || !Array.isArray(ix.counted) || !players) return { added: 0, skipped: "no counted list" };
  const some = Object.values(players)[0];
  if (some && some.now === undefined) return { added: 0, skipped: "players file before phase 6" };   // the leaders are rebuilt from it
  const seen = new Set(ix.counted.map(Number)), lo = minus(ix.today, 21);
  let added = 0;
  for (const md of mds || []) {
    const d = day(md && md.kickoff_utc);
    if (!d || d < lo || seen.has(+md.id)) continue;
    const w = pick(md); if (!w) continue;
    seen.add(+md.id); added++;
    const k = String(w.id), cur = d >= ix.since;
    const p = players[k] || (players[k] = { name: w.name, total: 0, now: 0, seasons: {}, comps: {}, opponents: {}, recent: [] });
    p.total++; if (cur) p.now = (p.now || 0) + 1;
    if (md.season) p.seasons[md.season] = (p.seasons[md.season] || 0) + 1;
    if (md.comp) p.comps[md.comp] = (p.comps[md.comp] || 0) + 1;
    if (w.opp) p.opponents[w.opp] = (p.opponents[w.opp] || 0) + 1;
    p.recent.unshift([+md.id, d, String(w.rating), w.opp || null]); p.recent.sort((a, b) => (b[1] > a[1] ? 1 : b[1] < a[1] ? -1 : 0)).splice(10);
    if (md.comp) {
      const c = ix.comps[md.comp] || (ix.comps[md.comp] = { name: null, season: [], all: [] });
      bump(c.all, w, 20, p.comps[md.comp]); if (cur) bump(c.season, w, 20, null);
    }
    const cl = w.team && ix.clubs[w.team];
    if (cl) { bump(cl.all, w, 10, null); if (cur) bump(cl.season, w, 10, null); }
  }
  if (added) {
    const top = f => rank(Object.entries(players).filter(([, p]) => p[f] > 0).map(([id, p]) => [+id, p.name, p[f]])).slice(0, 50);
    ix.leaders = { season: top("now"), all: top("total") };   // players.json holds everyone, so both lists are exact
    ix.matches += added;
  }
  return { added };
}

module.exports = { pick, apply };
