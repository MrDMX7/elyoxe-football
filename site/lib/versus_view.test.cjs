// node --test site/lib/versus_view.test.cjs — two teams' meetings, a team's record, the ratings (graph/features_export.py's rows)
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const V = require("./versus_view.cjs");

const N = { 1: ["أرسنال", 9825, 0], 2: ["ليفربول", 8650, 0] };
// [day, competition, season, 1 when lo is at home, home goals, away goals, Tifo match, FotMob match]
const MS = [["1989-05-26", 47, "1988/1989", 0, 0, 2, 900, 0], ["1990-09-01", 47, "1990/1991", 1, 2, 1, 1, 0], ["1991-03-03", 47, "1990/1991", 0, 1, 1, 901, 0]];
const O = { team: () => null, hub: t => (t === 1 ? "/vs/1/" : null), pair: () => "/vs/1-2/", match: m => (m[6] === 1 ? "/m/k1/" : null),
  comp: n => (n === 47 ? { key: "premier-league", name: "الدوري الإنجليزي", season: () => null } : null) };

test("a pair's numbers are counted for the lower id whichever side was at home", () => {
  const s = V.pairStats(1, 2, MS);
  assert.deepEqual(s.t, [3, 2, 1, 0, 5, 2]);              // Arsenal won 2-0 away and 2-1 at home, then drew 1-1 away
  assert.deepEqual(s.home.slice(0, 4), [1, 1, 0, 0]);
  assert.deepEqual(s.away.slice(0, 4), [2, 1, 1, 0]);
});

test("the pair's page lists every meeting newest first and links only the matches that have a page", () => {
  const h = V.pair(1, 2, MS, N, O);
  assert.ok(h.lastIndexOf("3 مارس 1991") < h.lastIndexOf("26 مايو 1989"));
  assert.match(h, /href="\/m\/k1\/"/);
  assert.equal((h.match(/href="\/m\//g) || []).length >= 1, true);
  assert.doesNotMatch(h, /k900|k901/);
  assert.match(h.replace(/<[^>]+>/g, "").replace(/s+/g, " "), /ليفربول 0 - 2 أرسنال/);                  // the home side first, as it was played
  assert.match(h, /href="\/vs\/1\/"/);
  assert.match(V.pairTitle(1, 2, N), /أرسنال.*ليفربول/);
});

test("a team's page shows its record against each opponent it met twice, linking the pair", () => {
  const d = { tot: [120, 70, 30, 20, 200, 90], first: "1989-05-26", last: "1991-03-03", opp: [[2, 3, 2, 1, 0, 5, 2], [3, 1, 1, 0, 0, 1, 0]],
    run: { win: [3, "1989-05-26", "1991-03-03"] }, elo: { now: 1700, peak: [1710, "1991-01-01"], low: [1500, "1989-06-01"], yr: [[1987, 1500], [1988, 1520], [1989, 1550], [1990, 1650], [1991, 1700]] } };
  const h = V.team(1, d, N, O);
  assert.match(h, /href="\/vs\/1-2\/"[^>]*>ليفربول/);
  assert.match(h, /<svg/);
  assert.match(h, /1710/);
});
