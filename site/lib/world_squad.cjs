// A squad for the team page from the world club file (db/world.py: v1/world/club/<id>.json, members
// [id, name, shirt, group, ccode]): clubs outside the focus set have no team/<id>.json fetched, so their «اللاعبين» tab was
// empty (Al Nassr, 2026-10-09). Same shape as team.json's squad: [{group, players:[{id, name, number, country}]}].
const ORDER = ["keepers", "defenders", "midfielders", "attackers", "coach"];

function squadFromWorld(members) {
  const by = {};
  for (const m of members || []) {
    if (!Array.isArray(m) || !m[0] || !m[1] || !ORDER.includes(m[3])) continue;
    (by[m[3]] = by[m[3]] || []).push({ id: m[0], name: m[1], number: m[2], country: m[4] });
  }
  return ORDER.filter(g => by[g]).map(g => ({ group: g, players: by[g] }));
}

// No squad in the world file either (the Iraqi league's clubs, 2026-10-09): the FotMob players (history/fm/players.json) that
// name the club as their team, by position (FotMob writes it in English or Arabic); one with no known position is left out
const POS = [[/keeper|حارس/i, "keepers"], [/back|مدافع|ظهير/i, "defenders"], [/midfielder|وسط/i, "midfielders"], [/winger|striker|forward|مهاجم/i, "attackers"]];
function squadFromFm(players, team, nameAr) {
  const members = [];
  for (const [id, p] of Object.entries(players || {})) {
    if (!p || +p.team !== +team) continue;
    const g = (POS.find(x => x[0].test(p.pos || "")) || [])[1];
    if (g) members.push([+id, (nameAr && nameAr(+id)) || p.name, p.shirt == null ? null : p.shirt, g, p.cc]);
  }
  return squadFromWorld(members);
}

// The header of a club with no team file: its coach (the squad's coach row) and its stadium (the venue)
function headFromWorld(w) {
  const out = {}, c = ((w && w.squad) || []).find(m => Array.isArray(m) && m[3] === "coach" && m[0] && m[1]);
  if (c) out.coach = { id: c[0], name: c[1] };
  if (w && w.venue && w.venue.name) out.venue = w.venue;
  return out;
}

// A link to a page this build did not write (the post-build link check): a player with an encyclopedia page
// (/db/player/<id>/, lib/world_stage.cjs) goes there, a club in the encyclopedia (world/index.json) or a match to its card; else null (unlinked)
function relink(href, has) {
  let m = /^\/p\/(\d+)\/$/.exec(href);
  if (m) return has.written.has(`/db/player/${m[1]}`) ? `/db/player/${m[1]}/` : null;
  m = /^\/t\/(\d+)\/$/.exec(href);
  if (m) return has.written.has(`/db/club/${m[1]}/`) || has.written.has(`/db/club/${m[1]}`) ? `/db/club/${m[1]}/` : has.clubs.has(+m[1]) ? `/db/club/?id=${m[1]}` : null;   // its static page first
  m = /^\/m\/(\d+)\/$/.exec(href);   // a match: its card (39 of 40 sampled have matchx/<id>.json; the card says so when not)
  if (m) return `/db/match/?id=${m[1]}`;
  return null;
}

module.exports = { squadFromWorld, squadFromFm, headFromWorld, relink };
