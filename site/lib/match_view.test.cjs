// node --test site/lib/match_view.test.cjs — an old match in the current match page (lib/match_view.cjs -> src/v5/pages.js P.match)
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), V = require("./match_view.cjs");

const M = { id: "k1482110", date: "2002-11-20", comp: 538, season: "2002/2003", h: [102119, "الأهلي"], a: [null, "الشباب"], s: [3, 2], ht: [1, 1],
  venue: "استاد راشد", ref: "علي حمد",
  ev: [[20, 0, "goal", "h", "ربيع العفوي", "k500"], [31, 0, "goal", "a", "علي دائي", "k238460"], [60, 2, "yellow", "a", null, null]],
  lu: { h: [["ربيع العفوي", "k500", "9", 1], ["سالم", "k501", "14", 0]], a: [["علي دائي", "k238460", "10", 1]] }, co: { h: "Coach A" } };

test("an old match in the current match page's data: its sides, score, events, ground and referee", () => {
  const md = V.md(M);
  assert.deepEqual([md.id, md.comp, md.status, md.score, md.halftime_score], ["k1482110", 538, "finished", { home: 3, away: 2 }, { home: 1, away: 1 }]);
  assert.deepEqual(md.home, { id: 102119, name_ar: "الأهلي" });
  assert.equal(md.away.nocrest, true);
  assert.deepEqual(md.events[0], { minute: 20, added: 0, type: "goal", team: "home", player: { id: "k500", name: "ربيع العفوي" } });
  assert.equal(md.events[2].player, null);
  assert.deepEqual([md.venue.name_ar, md.referee.name], ["استاد راشد", "علي حمد"]);
  assert.match(md.kickoff_utc, /^2002-11-20T/);
});

test("the lineups as two lists in the current style: starters, then the bench, the coach first", () => {
  const h = V.lineups(M, V.md(M));
  assert.match(h, /data-seg="lu"/);
  assert.match(h, /href="\/p\/k500\/"/);
  assert.match(h, /البدلاء/);
  assert.match(h, /Coach A/);
  assert.equal(V.lineups({ lu: null }, V.md(M)), null);
});

test("the meetings before this match from the every-competition pair file", () => {
  const pair = { teams: ["102119", "k9"], names: ["الأهلي", "الشباب"], matches: [
    ["2001-03-01", "دوري", "2000/2001", "102119", 2, 0, "k9", "k10"], ["2002-01-05", "كأس", "2001/2002", "k9", 1, 1, "102119", "k11"],
    ["2002-11-20", "دوري", "2002/2003", "102119", 3, 2, "k9", "k1482110"], ["2003-04-01", "دوري", "2002/2003", "k9", 2, 1, "102119", "k12"]] };
  const md = V.md(Object.assign({}, M, { a: ["k9", "الشباب"] }));
  const h = V.h2h(pair, md);
  assert.deepEqual(h.summary, { home_wins: 1, draws: 1, away_wins: 0 });       // before 20 Nov 2002 only, from this match's sides
  assert.deepEqual(h.matches.map(m => m.id), ["k11", "k10"]);
});

test("an old match renders in the current match page: no numbers tab, the lineup lists, the events", () => {
  const P = require("../src/v5/pages.js"), md = V.md(M);
  const v = P.match(md, { archive: 1, x: { lu: V.lineups(M, md) } });
  assert.doesNotMatch(v.body, /data-t="st"|data-p="st"/);
  assert.match(v.body, /data-t="lu"/);
  assert.match(v.body, /ربيع العفوي/);
  assert.match(v.body, /href="\/p\/k238460\/"/);
});

test("an old match's date carries its year", () => {
  const P = require("../src/v5/pages.js"), md = V.md(M);
  assert.equal(md.date_fmt, "dy");
  const v = P.match(md, { archive: 1, x: {} });
  assert.match(v.body, /data-f="dy">[^<]*2002</);
});

test("the meetings of any two teams from the archive's own matches, when the every-competition file has none", () => {
  const lists = [[{ id: "a1", date: "1998-06-10", comp: 77, season: "1998", h: [8256, "البرازيل"], a: [8570, "ألمانيا"], s: [1, 0] },
                  { id: "a2", date: "2002-06-30", comp: 77, season: "2002", h: [8570, "ألمانيا"], a: [8256, "البرازيل"], s: [0, 2] }],
                 [{ id: "a2", date: "2002-06-30", comp: 77, season: "2002", h: [8570, "ألمانيا"], a: [8256, "البرازيل"], s: [0, 2] },   // the same match listed twice
                  { id: "a3", date: "2003-01-01", comp: 538, season: "2002/2003", h: [null, "دبي"], a: [8256, "البرازيل"], s: [0, 1] }]];
  const P = V.pairs(lists, id => (id === 77 ? "كأس العالم" : ""));
  const p = P.get("8256-8570");
  assert.deepEqual(p.teams, ["8256", "8570"]);
  assert.equal(p.matches.length, 2);
  assert.deepEqual(p.matches[0], ["1998-06-10", "كأس العالم", "1998", "8256", 1, 0, "8570", "a1"]);
  const md = V.md({ id: "a2", date: "2002-06-30", comp: 77, h: [8570, "ألمانيا"], a: [8256, "البرازيل"], s: [0, 2] });
  assert.deepEqual(V.h2h(p, md).summary, { home_wins: 0, draws: 0, away_wins: 1 });
});

test("an old player's matches in the archive: those he played or scored in, his goals, the latest first", () => {
  const lists = [[{ id: "k1", date: "2002-11-20", comp: 538, season: "2002/2003", h: [102119, "الأهلي"], a: [null, "الشباب"], s: [3, 2],
                    ev: [[31, 0, "goal", "a", "علي دائي", "k238460"], [70, 0, "goal", "a", "علي دائي", "k238460"], [80, 0, "own_goal", "h", "علي دائي", "k238460"]],
                    lu: { a: [["علي دائي", "k238460", "10", 1]] } },
                  { id: "k2", date: "2003-01-05", comp: 538, season: "2002/2003", h: [null, "الشباب"], a: [102122, "الوحدة"], s: [1, 0],
                    ev: [[12, 0, "goal", "h", "علي دائي", "k238460"]] }]];
  const P = V.players(lists), d = P.get("k238460");
  assert.deepEqual([d.matches.length, d.goals], [2, 3]);                   // an own goal is not his
  assert.deepEqual(d.matches.map(m => m.id), ["k2", "k1"]);
  const h = V.playerBlock(d);
  assert.match(h, /مبارياته في أرشيف تيفو/);
  assert.match(h, /href="\/m\/k2\/"/);
  assert.equal(V.playerBlock(undefined), "");
});

test("an upcoming match's meetings from its home side's every-opponent file (h2h-team): the record, the latest first", () => {
  // Liverpool–Manchester United, 22 Nov 2026: «ما عندنا مواجهات سابقة»; the archive holds 186 meetings
  const file = { team: 8650, name: "ليفربول", opp: { "10260": { name: "مانشستر يونايتد", n: 3, w: [1, 1, 1], goals: [4, 4], matches: [
    ["2026-05-03", "الدوري الإنجليزي الممتاز", "2025/2026", "10260", 3, 2, "8650", "4813722"],
    ["2025-10-19", "الدوري الإنجليزي الممتاز", "2025/2026", "8650", 1, 1, "10260", "4813449"],
    ["1895-10-12", "الدوري الإنجليزي الممتاز", "1895/1896", "8650", 0, 0, "10260", "k77"]] } } };
  const md = { id: 4900001, status: "scheduled", kickoff_utc: "2026-11-22T16:30:00Z", home: { id: 8650, name_ar: "ليفربول" }, away: { id: 10260, name_ar: "مانشستر يونايتد" } };
  const h = V.fromTeamFile(file, md);
  assert.deepEqual(h.summary, { home_wins: 1, draws: 1, away_wins: 1 });
  assert.equal(h.total, 3);
  assert.deepEqual(h.matches.map(m => [m.id, m.home.id, m.score.home]), [["4813722", 10260, 3], ["4813449", 8650, 1], ["k77", 8650, 0]]);
  assert.equal(h.matches[2].href, "/m/k77/");
  const away = Object.assign({}, md, { home: md.away, away: md.home });                 // the file read from the other side
  assert.deepEqual(V.fromTeamFile(file, away, 8650).summary, { home_wins: 1, draws: 1, away_wins: 1 });
  assert.equal(V.fromTeamFile({ team: 8650, opp: {} }, md), null);
});

test("the meetings list dates an old meeting with its year", () => {
  const U = require("../src/v5/ui.js");
  const md = { id: 1, status: "scheduled", kickoff_utc: "2026-11-22T16:30:00Z", home: { id: 8650, name_ar: "ليفربول" }, away: { id: 10260, name_ar: "مانشستر يونايتد" } };
  md.h2h = V.fromTeamFile({ team: 8650, name: "ليفربول", opp: { "10260": { name: "مانشستر يونايتد", n: 1, w: [0, 1, 0], goals: [0, 0],
    matches: [["1895-10-12", "x", "1895/1896", "8650", 0, 0, "10260", "k77"]] } } }, md);
  assert.match(U.h2h(md), /1895/);
});

test("a side the archive holds no players for says so, no empty card (22 Nov QA: /m/k1481515/)", () => {
  const m = Object.assign({}, M, { lu: { h: [["ربيع العفوي", "k500", "9", 1]], a: [] } });
  const h = V.lineups(m, V.md(m));
  assert.doesNotMatch(h, /<div class="card"><\/div>/);
  assert.match(h, /ما عندنا تشكيلة/);
});

test("an old match with a result only says the archive holds no more, not «yet»", () => {
  const U = require("../src/v5/ui.js"), P5 = require("../src/v5/pages.js");
  const md = V.md({ id: "k1", date: "1990-09-01", comp: 47, h: [1, "أ"], a: [2, "ب"], s: [1, 0] });
  const h = P5.match(md, { archive: 1, x: { lu: null, h2h: null, share: "" } }).body;
  assert.match(h, /في الأرشيف/);
  assert.doesNotMatch(h, /للحين/);
});
