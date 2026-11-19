// node --test site/lib/whistle.test.cjs — phase 6: the matches finished since the graph's nightly build, added to its man-of-the-match files
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), W = require("./whistle.cjs");

const md = (id, date, lineups, events, extra) => Object.assign({ id, comp: 538, season: "2026/2027", status: "finished", kickoff_utc: date + "T15:00:00Z",
  home: { id: 102117 }, away: { id: 102122 }, lineups, events: events || [] }, extra);
const lu = (home, away) => ({ home: { starters: home, subs: [] }, away: { starters: away, subs: [] } });

test("the man of the match is the top rating; a tie goes to goals and assists", () => {
  const m = md(1, "2026-11-19", lu([{ id: 10, name: "A", rating: 8.1 }, { id: 11, name: "B", rating: 8.1 }], [{ id: 20, name: "C", rating: 7.9 }, { id: 21, name: "D", rating: null }]),
    [{ type: "goal", player: { id: 11 }, assist: null }]);
  assert.deepEqual(W.pick(m), { id: 11, name: "B", team: 102117, opp: 102122, rating: 8.1 });
  assert.equal(W.pick(Object.assign({}, m, { status: "live" })), null);              // only at the whistle
  assert.equal(W.pick(md(2, "2026-11-19", lu([{ id: 10, rating: null }], []))), null); // no ratings, no pick
});

function files() {
  const ix = { since: "2026-07-01", today: "2026-11-19", counted: [5], matches: 100,
    leaders: { season: [[10, "A", 3], [30, "Z", 2]], all: [[30, "Z", 40], [10, "A", 12]] },
    comps: { 538: { name: "دوري أدنوك للمحترفين", season: [[10, "A", 3]], all: [[30, "Z", 9], [10, "A", 5]] } },
    clubs: { 102117: { season: [[10, "A", 3]], all: [[10, "A", 12]] } } };
  const pl = { 10: { name: "A", total: 12, now: 3, seasons: { "2026/2027": 3 }, comps: { 538: 5 }, opponents: {}, recent: [[5, "2026-11-10", "8.0", 102122]] },
    30: { name: "Z", total: 40, now: 2, seasons: {}, comps: { 538: 9 }, opponents: {}, recent: [] } };
  return { ix, pl };
}

test("a match after the build adds one, everywhere, exactly", () => {
  const { ix, pl } = files();
  const out = W.apply(ix, pl, [md(6, "2026-11-19", lu([{ id: 10, name: "A", rating: 9 }], [{ id: 20, name: "C", rating: 6 }]))]);
  assert.equal(out.added, 1);
  assert.equal(pl[10].total, 13); assert.equal(pl[10].now, 4); assert.equal(pl[10].comps[538], 6); assert.equal(pl[10].opponents[102122], 1);
  assert.deepEqual(pl[10].recent[0], [6, "2026-11-19", "9", 102122]);
  assert.deepEqual(ix.leaders.season[0], [10, "A", 4]);
  assert.deepEqual(ix.leaders.all, [[30, "Z", 40], [10, "A", 13]]);
  assert.deepEqual(ix.comps[538].all[1], [10, "A", 6]);
  assert.deepEqual(ix.clubs[102117].season[0], [10, "A", 4]);
  assert.equal(ix.matches, 101);
});

test("a match the build counted, an old one, or one played twice in the list is not added again", () => {
  const { ix, pl } = files();
  const m = id => md(id, "2026-11-19", lu([{ id: 30, name: "Z", rating: 9 }], []));
  const out = W.apply(ix, pl, [m(5), md(7, "2026-09-01", lu([{ id: 30, name: "Z", rating: 9 }], [])), m(8), m(8)]);
  assert.equal(out.added, 1);
  assert.equal(pl[30].total, 41);
});

test("a new name joins, and a file from before phase 6 is left as it is", () => {
  const { ix, pl } = files();
  W.apply(ix, pl, [md(9, "2026-11-19", lu([{ id: 77, name: "New", rating: 9 }], []))]);
  assert.equal(pl[77].total, 1);
  assert.deepEqual(ix.comps[538].season.find(r => r[0] === 77), [77, "New", 1]);   // the list holds everyone (under its cap), so 1 is exact
  const old = { since: "2026-07-01", matches: 1, leaders: { season: [[1, "x", 1]], all: [[1, "x", 1]] }, comps: {}, clubs: {} };
  assert.deepEqual(W.apply(old, {}, [md(9, "2026-11-19", lu([{ id: 77, rating: 9 }], []))]), { added: 0, skipped: "no counted list" });
  assert.equal(old.matches, 1);
});

test("an index from phase 6 with a players file from before it is left alone", () => {
  const { ix } = files();
  const pl = { 10: { total: 12, seasons: {}, comps: {}, opponents: {}, recent: [] } };          // no now, no name: the old players.json
  assert.deepEqual(W.apply(ix, pl, [md(6, "2026-11-19", lu([{ id: 10, name: "A", rating: 9 }], []))]), { added: 0, skipped: "players file before phase 6" });
  assert.deepEqual(ix.leaders.season, [[10, "A", 3], [30, "Z", 2]]);
});
