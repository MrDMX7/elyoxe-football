// node --test site/lib/scout.test.cjs — «كشّاف تيفو» points and pool (lib/scout.cjs) on hand-made matches
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), SC = require("./scout.cjs");

const md = (id, ko, home, away, lh, la, events) => ({ id, status: "finished", kickoff_utc: ko, home, away, events: events || [],
  lineups: { home: { starters: lh.filter(p => !p.sub), subs: lh.filter(p => p.sub) }, away: { starters: la.filter(p => !p.sub), subs: la.filter(p => p.sub) } } });
const pl = (id, country, age, o) => Object.assign({ id, name: "P" + id, country, age, role: "FW", rating: null, minutes_on: null, minutes_off: null }, o || {});
const CLUB = { id: 10, name: "Club", name_ar: "النادي" }, OTHER = { id: 11, name: "Other", name_ar: "الثاني" }, UAE = { id: 5789, name: "UAE", name_ar: "الإمارات" }, KSA = { id: 7795, name: "KSA", name_ar: "السعودية" };
const NAT = new Set([5789, 7795]);

test("the points of one match follow the rules shown on the page", () => {
  assert.equal(SC.points({ mins: 90, g: 2, a: 1, rating: 8.4, nt: false }), 1 + 1 + 10 + 3 + 3);
  assert.equal(SC.points({ mins: 30, g: 0, a: 0, rating: 7.0, nt: false }), 1 + 1);
  assert.equal(SC.points({ mins: 0, g: 0, a: 0, rating: null, nt: true }), 2);         // called up, unused
  assert.equal(SC.points({ mins: 0, g: 0, a: 0, rating: null, nt: false }), 0);
  assert.equal(SC.points({ mins: 60, g: 0, a: 0, rating: 6.9, nt: true }), 2 + 1 + 1);
});

test("pool: young Arab nationals, their club, their minutes; own goals and the old never count", () => {
  const m1 = md(1, "2026-08-10T18:00:00Z", CLUB, OTHER,
    [pl(101, "UAE", 20, { rating: 8.1 }), pl(102, "KSA", 25), pl(103, "ENG", 19), pl(104, "MAR", 21, { sub: 1, minutes_on: 70 }), pl(105, "EGY", 22, { sub: 1 })],
    [pl(201, "TUN", 23, { minutes_off: 55, rating: 7.2 })],
    [{ type: "goal", player: { id: 101 }, assist: { id: 104 } }, { type: "own_goal", player: { id: 201 } }, { type: "penalty_goal", player: { id: 101 } }]);
  const m2 = md(2, "2026-09-05T18:00:00Z", UAE, KSA, [pl(101, "UAE", 20)], [pl(301, "KSA", 19, { sub: 1 })]);   // national teams: 301 called up, unused
  const old = md(3, "2026-06-30T18:00:00Z", CLUB, OTHER, [pl(101, "UAE", 20, { rating: 9 })], []);              // before the season
  const { pool, points } = SC.build([m2, old, m1], { natTeams: NAT, nameOf: id => (id === 101 ? "اللاعب" : null) });
  const by = Object.fromEntries(pool.players.map(p => [p.id, p]));
  assert.deepEqual(Object.keys(by).map(Number).sort((a, b) => a - b), [101, 104, 201, 301]);   // 102 is 25, 103 English, 105 an unused club substitute
  assert.equal(by[101].pts, (1 + 1 + 10 + 3) + (2 + 1 + 1));   // two goals and a rating of 8.1 for his club, then 90 minutes for his country
  assert.deepEqual([by[101].t, by[101].tn, by[101].nt, by[101].n, by[101].apps, by[101].g], [10, "النادي", 1, "اللاعب", 2, 2]);
  assert.equal(by[104].pts, 1 + 3);              // 20 minutes off the bench and an assist
  assert.equal(by[201].pts, 1 + 0 + 1);          // 55 minutes, a 7.2, his own goal counts nothing
  assert.deepEqual([by[301].pts, by[301].apps, by[301].t, by[301].nt], [2, 0, null, 1]);
  assert.deepEqual(points.players[101], [[1, "2026-08-10T18:00:00Z", 15], [2, "2026-09-05T18:00:00Z", 4]]);
  assert.equal(pool.players[0].id, 101);         // the best first
});

test("a player who turns 24 during the season stays in; one first seen at 24 never joins", () => {
  const a = md(1, "2026-08-01T18:00:00Z", CLUB, OTHER, [pl(401, "QAT", 23), pl(402, "QAT", 24)], []);
  const b = md(2, "2027-02-01T18:00:00Z", CLUB, OTHER, [pl(401, "QAT", 24), pl(402, "QAT", 24)], []);
  const ids = SC.build([a, b], { natTeams: NAT }).pool.players.map(p => p.id);
  assert.deepEqual(ids, [401]);
});
