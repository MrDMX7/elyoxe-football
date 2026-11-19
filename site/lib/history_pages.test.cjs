// node --test site/lib/history_pages.test.cjs — season, coach and club-coach pages (lib/history_pages.cjs) from v1/editions and v1/coaches
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), H = require("./history_pages.cjs");

const COMP = { id: 538, key: "uae-pro-league", name_ar: "دوري أدنوك للمحترفين" };
const S16 = { season: "2016/2017", matches: 182, champion: { fotmob: 102101, name: "الجزيرة" }, runner_up: { fotmob: 102117, name: "العين" },
  table: [[1, 102101, "الجزيرة", 26, 22, 2, 2, 70, 20, 68], [2, 102117, "العين", 26, 18, 4, 4, 60, 30, 58]],
  top_scorers: [{ rank: 1, fotmob: 170716, name: "علي مبخوت", value: "33" }], best_player: [{ rank: 1, fotmob: 1, name: "Omar Abdulrahman", value: null }],
  best_young: [], best_goalkeeper: [], best_local: [], top_assist: [], best_coach: [], champion_coach: { kid: 5, name: "Henk ten Cate" }, motm: [[170716, "علي مبخوت", 7]] };
const ED = { fotmob: 538, seasons: [S16, { season: "1973/1974", matches: 0, champion: { fotmob: 102124, name: "الشارقة" }, runner_up: null, table: [], top_scorers: [],
  best_player: [], best_young: [], best_goalkeeper: [], best_local: [], top_assist: [], best_coach: [], champion_coach: null, motm: [] }] };
const o = { team: id => [102101, 102117].includes(id), player: id => id === 170716, coach: id => (id === 5 ? "/coach/k5/" : null), coachName: id => (id === 5 ? "هنك تن كات" : null) };

test("season slugs", () => {
  assert.equal(H.slug("2016/2017"), "2016-2017");
  assert.equal(H.slug("2026"), "2026");
});

test("the seasons index: every season, champion, runner-up, top scorer, linked", () => {
  const h = H.seasonsBody(ED, COMP, o);
  assert.match(h, /href="\/c\/uae-pro-league\/s\/2016-2017\/"/);
  assert.match(h, /<a href="\/t\/102101\/">الجزيرة<\/a>/);
  assert.match(h, /الشارقة/);
  assert.match(h, /علي مبخوت/);
});

test("a season page: table, top scorers, awards, coach, man of the match", () => {
  const h = H.seasonBody(S16, COMP, o);
  assert.match(h, /البطل/);
  assert.match(h, /<a href="\/coach\/k5\/">هنك تن كات<\/a>/);
  assert.match(h, /<span class="num">68<\/span>/);
  assert.match(h, /<a href="\/p\/170716\/">علي مبخوت<\/a>/);
  assert.match(h, /رجل المباراة/);
  assert.match(h, /<span class="lat">Omar Abdulrahman<\/span>/);
  assert.equal(H.seasonRich(S16), true);
  assert.equal(H.seasonRich(ED.seasons[1]), false);        // a champion alone is a row in the index, not a page
});

test("a coach page and the club's coaches", () => {
  const c = { name: "Henk ten Cate", name_ar: null, fotmob: 150526, spells: [{ team: 102101, team_name: "الجزيرة", start: "2015-12-01", end: "2018-05-01", m: 70, w: 40, d: 12, l: 18, gf: 140, ga: 80 }] };
  const h = H.coachBody(c, o);
  assert.match(h, /<span class="num">70<\/span>/);
  assert.match(h, /<a href="\/t\/102101\/">الجزيرة<\/a>/);
  assert.equal(H.coachIndexable(c), true);
  assert.equal(H.coachPageable({ spells: [{ team: 9, m: 4 }] }, o), false);           // 4 matches somewhere we don't cover: no page
  const site = { spells: [{ team: 102101, m: 4 }] };
  assert.equal(H.coachPageable(site, o), true);                                       // a bench at a club the site has: a page,
  assert.equal(H.coachIndexable(site), false);                                        // but too thin for the index
  const cc = H.clubCoaches([{ kid: 5, name: "Henk ten Cate", start: "2015-12-01", end: "2018-05-01", m: 70, w: 40, d: 12, l: 18 },
    { kid: 6, name: "Abel Braga", start: "2015-08-01", end: "2015-11-01", m: 9, w: 4, d: 2, l: 3 }], o);
  assert.match(cc, /<a href="\/coach\/k5\/">هنك تن كات<\/a>/);
  assert.match(cc, /<span class="lat">Abel Braga<\/span>/);
  assert.doesNotMatch(cc, /coach\/k6/);
  assert.match(cc, /2015/);
});

test("the site's Arabic names win over the graph's Latin ones", () => {
  const ed = { seasons: [{ season: "2001/2002", matches: 30, champion: { fotmob: 102101, name: "Al Jazira" }, runner_up: null, table: [], top_scorers: [{ rank: 1, fotmob: 170716, name: "Ali Mabkhout", value: "20" }] }] };
  const h = H.seasonsBody(ed, COMP, Object.assign({}, o, { teamName: id => (id === 102101 ? "الجزيرة" : null), playerName: id => (id === 170716 ? "علي مبخوت" : null) }));
  assert.match(h, /<a href="\/t\/102101\/">الجزيرة<\/a>/);
  assert.match(h, /<a href="\/p\/170716\/">علي مبخوت<\/a>/);
  assert.doesNotMatch(h, /Al Jazira|Ali Mabkhout/);
});
