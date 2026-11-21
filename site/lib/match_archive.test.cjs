// node --test site/lib/match_archive.test.cjs — the old matches' pages (/m/<id>/, /m/k<id>/) from v1/matches/*
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), M = require("./match_archive.cjs");

const M1 = { id: "2600001", date: "2016-10-01", comp: 538, season: "2016/2017", round: "5", h: [102101, "الجزيرة"], a: [102117, "العين"], s: [2, 1],
  ev: [[23, 0, "goal", "h", "علي مبخوت", "170716"], [70, 0, "yellow", "a", "Someone", null], [88, 2, "penalty_goal", "a", "عمر عبد الرحمن", "201165"]],
  lu: { h: [["علي مبخوت", "170716", "7", 1], ["Sub Guy", "k9", "20", 0]], a: [["عمر عبد الرحمن", "201165", "10", 1]] }, co: { h: "Henk ten Cate" }, venue: "Mohammed bin Zayed Stadium", ref: "Ammar Al Jeneibi" };
const OLD = { id: "k950", date: "1990-06-15", comp: 77, season: "1990", h: [null, "ألمانيا الغربية"], a: [5789, "الإمارات"], s: [5, 1], ev: [[46, 0, "goal", "a", "خالد إسماعيل", "k12"]] };
const COMP = { id: 538, key: "uae-pro-league", name_ar: "دوري أدنوك للمحترفين" };
const o = { team: id => [102101, 102117, 5789].includes(id), player: id => id === "170716", person: id => id === "k12", comp: c => (c === 538 ? COMP : null) };

test("a match page: score, scorers, cards, lineups, coach, venue", () => {
  const h = M.matchBody(M1, o);
  assert.match(h, /<a href="\/t\/102101\/">الجزيرة<\/a>/);
  assert.match(h, /<span class="num">2<\/span>/);
  assert.match(h, /<a href="\/p\/170716\/">علي مبخوت<\/a>/);
  assert.match(h, /عمر عبد الرحمن/);
  assert.match(h, /ضربة جزاء/);
  assert.match(h, /<span class="num">90\+2<\/span>|<span class="num">88\+2<\/span>/);
  assert.match(h, /إنذار/);
  assert.match(h, /التشكيلة/);
  assert.match(h, /الاحتياط/);
  assert.match(h, /Henk ten Cate/);
  assert.match(h, /href="\/c\/uae-pro-league\/s\/2016-2017\/"/);
  assert.match(h, /Mohammed bin Zayed Stadium/);
});

test("an old international with a scorer FotMob does not know", () => {
  const h = M.matchBody(OLD, o);
  assert.match(h, /<a href="\/p\/k12\/">خالد إسماعيل<\/a>/);
  assert.match(h, /ألمانيا الغربية/);
  assert.equal(M.href(OLD), "/m/k950/");
  assert.equal(M.href(M1), "/m/2600001/");
});

test("titles, indexing and the season's list", () => {
  assert.equal(M.title(M1, COMP), "الجزيرة 2-1 العين: دوري أدنوك للمحترفين 2016/2017 | تيفو");
  assert.equal(M.indexable(M1), true);
  assert.equal(M.indexable({ id: "k1", s: [1, 0], h: [1, "a"], a: [2, "b"] }), false);       // a score alone: a page, not indexed
  const l = M.listBody([M1, Object.assign({}, M1, { id: "2600002", round: "6", date: "2016-10-08" })], o);
  assert.match(l, /الجولة <span class="num">5<\/span>/);
  assert.match(l, /href="\/m\/2600002\/"/);
});

test("an old match with no starters marked shows who played, not a lineup of substitutes", () => {
  const m = Object.assign({}, M1, { lu: { h: [["A", "1", "9", 0], ["B", "2", "8", 0]] } });
  const h = M.matchBody(m, o);
  assert.match(h, /شاركوا في المباراة/);
  assert.doesNotMatch(h, /الاحتياط/);
  assert.doesNotMatch(h, /التشكيلة: الجزيرة/);
});

test("a club's matches from the season files: grouped by side, deduplicated, oldest first, only past the floor, never a team with its own file", () => {
  const mk = (id, date, h, a) => ({ id, date, comp: 538, season: "x", h: [h, "H"], a: [a, "A"], s: [1, 0] });
  const s1 = [mk("1", "2016-10-08", 102117, 102101), mk("2", "2016-09-01", 102101, 5789), mk("3", "2016-11-01", null, 102117)];
  const s2 = [mk("1", "2016-10-08", 102117, 102101), mk("4", "2015-05-01", "102101", 102117)];
  const g = M.teamMatches([s1, s2], { min: 3, skip: new Set([5789]) });
  assert.deepEqual([...g.keys()].sort(), [102101, 102117]);
  assert.deepEqual(g.get(102117).map(m => m.id), ["4", "1", "3"]);
  assert.deepEqual(g.get(102101).map(m => m.id), ["4", "2", "1"]);
  assert.equal(M.teamMatches([s1, s2], { min: 4 }).size, 0);
  assert.equal(M.teamMatches([s1, s2], { min: 1, keep: id => id === 102117 }).size, 1);
});

test("a match page names its man of the match, linked", () => {
  const h = M.matchBody({ ...OLD, motm: ["خالد إسماعيل", "k12"] }, o);
  assert.match(h, /رجل المباراة:<\/span> <a href="\/p\/k12\/">خالد إسماعيل<\/a>/);
  assert.doesNotMatch(M.matchBody(OLD, o), /رجل المباراة/);
});
