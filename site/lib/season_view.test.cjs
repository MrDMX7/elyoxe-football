// node --test site/lib/season_view.test.cjs — an old season in the current competition page's shapes (lib/season_view.cjs)
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), V = require("./season_view.cjs");

const S = { season: "2002/2003", table: [[1, 102119, "الأهلي", 22, 15, 4, 3, 50, 20, 49], [2, null, "دبي", 22, 12, 5, 5, 40, 25, 41]],
  top_scorers: [{ rank: 1, fotmob: null, tifo: 238460, name: "علي دائي", value: "17" }, { rank: 2, fotmob: 170716, name: "علي مبخوت", value: "12" }] };
const MS = [{ id: "k1", date: "2002-10-17", round: null, h: [null, "دبي"], a: [102122, "الوحدة"], s: [2, 3] },
  { id: "k2", date: "2002-11-02", h: [102119, "الأهلي"], a: [null, "دبي"], s: [3, 2], pen: null },
  { id: "4100", date: "2003-01-09", round: "14", h: [102122, "الوحدة"], a: [102119, "الأهلي"], s: [1, 1] }];

test("the final table in the current table's rows: an old club FotMob never had has no crest and no link of its own", () => {
  const st = V.standings(S);
  assert.equal(st.groups.length, 1);
  assert.deepEqual(st.groups[0].rows[0], { rank: 1, team: { id: 102119, name_ar: "الأهلي" }, played: 22, won: 15, drawn: 4, lost: 3, gf: 50, ga: 20, gd: 30, pts: 49 });
  assert.equal(st.groups[0].rows[1].team.nocrest, true);
  assert.match(String(st.groups[0].rows[1].team.id), /^n/);
  assert.equal(V.standings({ season: "1980/1981", table: [] }), null);
});

test("the matches by round, a round-less season by month, each linked to its archive page", () => {
  const fx = V.fixtures(MS);
  assert.equal(fx.matches.length, 3);
  const m = fx.matches[1];
  assert.deepEqual([m.round, m.status, m.score, m.href, m.home.name_ar, m.away.nocrest], ["نوفمبر 2002", "finished", { home: 3, away: 2 }, "/m/k2/", "الأهلي", true]);
  assert.equal(fx.matches[0].round, "أكتوبر 2002");
  assert.equal(fx.matches[2].round, "14");
  assert.match(m.kickoff_utc, /^2002-11-02T/);
});

test("the top scorers as the current scorers' list: a man FotMob never had links to his archive page", () => {
  const g = V.stats(S).lists.goals;
  assert.deepEqual(g[0], { rank: 1, player: { id: "k238460", name: "علي دائي" }, team: null, value: "17" });
  assert.equal(g[1].player.id, 170716);
  assert.equal(V.stats({ top_scorers: [] }), null);
});

test("a season's neighbours for the chips: the one before, the one after", () => {
  const ss = [{ season: "2003/2004" }, { season: "2002/2003" }, { season: "2001/2002" }];
  assert.deepEqual(V.around(ss, "2002/2003"), { newer: "2003/2004", older: "2001/2002" });
  assert.deepEqual(V.around(ss, "2003/2004"), { newer: null, older: "2002/2003" });
});

test("an old season renders in the current competition page: its rounds written in, switched without a fetch", () => {
  const P = require("../src/v5/pages.js");
  const c = { id: 538, key: "uae-pro-league", name_ar: "دوري أدنوك للمحترفين", season: "2002/2003" };
  const v = P.comp(c, { st: V.standings(S), fx: V.fixtures(MS), stats: V.stats(S), archive: 1, x: { chips: '<a class="chip" href="/c/uae-pro-league/seasons/">كل المواسم</a>', hist: "<p>honours</p>" } });
  assert.match(v.body, /id="rounds"[^>]*data-static="1"/);
  assert.match(v.body, /data-rk="أكتوبر 2002" hidden/);              // every round in the page, the last one shown
  assert.match(v.body, /data-rk="14" hidden/);
  assert.match(v.body, /data-rk="نوفمبر 2002">/);                       // the last round, as the current page opens on it
  assert.match(v.body, /href="\/m\/k2\/"/);
  assert.match(v.body, /كل المواسم/);
  assert.doesNotMatch(v.body, /الفورمة/);                               // the archive holds no form
  assert.match(v.body, /علي دائي/);
});

test("a season with only its honours opens on them", () => {
  const P = require("../src/v5/pages.js");
  const v = P.comp({ id: 538, key: "k", name_ar: "د" }, { st: null, fx: { matches: [] }, stats: null, archive: 1, x: { hist: "<p>honours</p>" } });
  assert.match(v.body, /data-p="hist">/);                               // shown, not hidden
  assert.match(v.body, /data-t="hist" aria-selected="true"/);
});

test("an old scorer's Arabic name is set as Arabic, not in the Latin style", () => {
  const U = require("../src/v5/ui.js");
  assert.equal(U.pname({ id: "k238460", name: "علي دائي" }), "علي دائي");
  assert.match(U.pname({ id: "k1", name: "Ali Daei" }), /class="lat"/);
});

test("a tournament's group tables, counted from its group matches when the archive holds none", () => {
  const G = [{ id: "1", date: "2022-11-20", round: "Group A", h: [1, "قطر"], a: [2, "الإكوادور"], s: [0, 2] },
    { id: "2", date: "2022-11-21", round: "Group A", h: [3, "السنغال"], a: [4, "هولندا"], s: [0, 2] },
    { id: "3", date: "2022-11-25", round: "Group A", h: [1, "قطر"], a: [3, "السنغال"], s: [1, 3] },
    { id: "4", date: "2022-11-25", round: "Group A", h: [4, "هولندا"], a: [2, "الإكوادور"], s: [1, 1] },
    { id: "5", date: "2022-11-29", round: "Group B", h: [5, "إنجلترا"], a: [6, "ويلز"], s: [3, 0] },
    { id: "6", date: "2022-12-03", round: "Round of 16", h: [4, "هولندا"], a: [7, "أمريكا"], s: [3, 1] }];
  const st = V.standings({ table: [] }, G);
  assert.deepEqual(st.groups.map(g => g.name), ["Group A", "Group B"]);
  const a = st.groups[0].rows;
  assert.deepEqual(a.map(r => [r.rank, r.team.name_ar, r.pts, r.gd]), [[1, "الإكوادور", 4, 2], [2, "هولندا", 4, 2], [3, "السنغال", 3, 0], [4, "قطر", 0, -4]]);
  assert.equal(a[0].played, 2);                                          // level on all we hold: by name
  assert.equal(V.standings({ table: [] }, [{ id: "9", date: "2001-01-01", round: "1", h: [1, "x"], a: [2, "y"], s: [1, 0] }]), null);   // a league with no table: none
});

test("a tournament's knockout rounds named as the current rounds: one chip each, in order", () => {
  const ms = ["Group A", "Round of 16", "round of 16", "Third Place Play-Off", "Quarter-Finals", "Semi-Finals", "Final", "Round of 32"]
    .map((r, i) => ({ id: "x" + i, date: "2022-12-0" + (i + 1), round: r, h: [1, "a"], a: [2, "b"], s: [1, 0] }));
  assert.deepEqual(V.fixtures(ms).matches.map(m => m.round), ["Group A", "1/8", "1/8", "3rd place", "1/4", "1/2", "Final", "1/16"]);
  const U = require("../src/v5/ui.js"), R = U.rounds(V.fixtures(ms));
  assert.deepEqual(R.order, ["Group A", "1/16", "1/8", "1/4", "1/2", "3rd place", "Final"]);
});

test("a season the archive holds matches for but no honours still gets its page and its row", () => {
  const ed = { seasons: [{ season: "1980" }, { season: "1972" }] };
  const msea = new Map([["50|1976", [{ id: "x", season: "1976", date: "1976-06-20", h: [1, "a"], a: [2, "b"], s: [2, 2] }]], ["50|1980", []], ["47|1976", [{ season: "1976" }]]]);
  assert.deepEqual(V.seasons(ed, msea, 50).map(s => s.season), ["1980", "1976", "1972"]);
  assert.deepEqual(V.seasons(null, msea, 50).map(s => s.season), ["1976"]);
});

test("a season's card leaders and, with no scorers list, its scorers from its matches' events", () => {
  const ms = [{ id: "k1", h: [1, "أ"], a: [2, "ب"], s: [2, 0], ev: [[10, 0, "goal", "h", "سالم", "k5"], [20, 0, "goal", "h", "سالم", "k5"], [30, 0, "yellow", "a", "خالد", "k6"],
    [80, 0, "second_yellow", "a", "خالد", "k6"], [85, 0, "own_goal", "h", "خالد", "k6"]] },
    { id: "k2", h: [2, "ب"], a: [1, "أ"], s: [0, 0], ev: [[5, 0, "yellow", "h", "خالد", "k6"], [9, 0, "red", "a", "سالم", "k5"]] }];
  const c = V.cards(ms);
  assert.deepEqual(c.yellow.map(p => [p.player.name, p.value]), [["خالد", 2]]);
  assert.deepEqual(c.red.map(p => [p.player.id, p.value]).sort(), [["k5", 1], ["k6", 1]]);
  const st = V.stats({ top_scorers: [] }, ms);
  assert.deepEqual(st.lists.goals.map(p => [p.player.name, p.value]), [["سالم", 2]]);    // an own goal is nobody's
});
