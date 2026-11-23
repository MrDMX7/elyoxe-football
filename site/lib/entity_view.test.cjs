// node --test site/lib/entity_view.test.cjs — the archive's referee and club pages (lib/entity_view.cjs)
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), V = require("./entity_view.cjs");

const R = { n: "M Halsey", c: "England", ms: [["2003/2004", 47, "الدوري الإنجليزي الممتاز", 30, 98, 4], ["2002/2003", 47, "الدوري الإنجليزي الممتاز", 28, 80, 2]],
  last: [["k698675", "2004-05-15", "بيرمنغهام", 8658, "توتنهام", 8586, 1, 0, 47]] };
const C = { n: "Wimbledon", ar: "ويمبلدون", c: "ENG", ss: [["1990/1991", 47, "الدوري الإنجليزي الممتاز", 38, 14, 14, 10, 53, 46], ["1989/1990", 47, "الدوري الإنجليزي الممتاز", 38, 13, 16, 9, 47, 40]],
  hon: [["champion", "كأس الاتحاد الإنجليزي", 132, "1987/1988"]], last: [["k1", "1991-05-11", "ويمبلدون", null, "ليفربول", 8650, 1, 2, 47]] };
const o = { team: id => id === 8650, comp: id => (id === 47 ? { key: "premier-league" } : null) };

test("a referee's page: his games and cards by season, his last games", () => {
  const h = V.referee(R, o);
  assert.match(h, /M Halsey/);
  assert.match(h, /<span class="num">58<\/span> مباراة/);
  assert.match(h, /<span class="num">178<\/span> إنذار/);
  assert.match(h, /href="\/c\/premier-league\/s\/2003-2004\/"/);
  assert.match(h, /href="\/m\/k698675\/"/);
});

test("a club's page: every season's record, its titles, its last games", () => {
  const h = V.club(C, o);
  assert.match(h, /ويمبلدون/);
  assert.match(h, /بطل[\s\S]*?كأس الاتحاد الإنجليزي[\s\S]*?1987\/1988/);
  assert.match(h, /<td><span class="num">14<\/span><\/td>/);
  assert.match(h, /<a href="\/t\/8650\/">ليفربول<\/a>/);
});

test("the search engines get the big records only", () => {
  assert.equal(V.refIndexable(R), true);
  assert.equal(V.refIndexable({ n: "X", ms: [["2003", 1, "x", 5, 0, 0]] }), false);
  assert.equal(V.clubIndexable(C), true);
});
