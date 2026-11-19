// node --test site/lib/motm_pages.test.cjs — «رجل المباراة» pages (lib/motm_pages.cjs) from v1/motm/* (graph/publish.py)
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), M = require("./motm_pages.cjs");

const IX = { since: "2026-07-01", matches: 900, leaders: { season: [[170716, "علي مبخوت", 6], [5, "Kodjo Laba", 4]], all: [[170716, "علي مبخوت", 41]] },
  comps: { "538": { name: "دوري أدنوك للمحترفين", season: [[170716, "علي مبخوت", 5]], all: [[170716, "علي مبخوت", 30]] }, "99": { name: "Other", season: [], all: [[1, "x", 2]] } } };
const o = { hasPage: id => id === 170716, comp: id => (id === 538 ? { name_ar: "دوري أدنوك للمحترفين", href: "/c/uae-pro-league/" } : null) };

test("the hub: this season first, all time, and the site's competitions", () => {
  const h = M.hubBody(IX, o);
  assert.ok(h.indexOf("هالموسم") < h.indexOf("عبر التاريخ"));
  assert.match(h, /<a href="\/p\/170716\/">علي مبخوت<\/a>/);
  assert.match(h, /<span class="lat">Kodjo Laba<\/span>/);
  assert.match(h, /دوري أدنوك للمحترفين/);
  assert.doesNotMatch(h, /Other/);                                    // a competition without a site page is left out
});

test("a player's block: total, this season, by competition, last picks", () => {
  const rec = { total: 41, seasons: { "2026/2027": 6, "2025/2026": 9 }, comps: { "538": 30, "99": 11 }, opponents: { "102122": 7 }, recent: [[4800, "2026-11-01", "8.9", 102122]] };
  const h = M.playerBlock(rec, Object.assign({ team: id => (id === 102122 ? "الوحدة" : null), match: id => id === 4800 }, o));
  assert.match(h, /رجل المباراة/);
  assert.match(h, /<span class="num">41<\/span>/);
  assert.match(h, /دوري أدنوك للمحترفين/);
  assert.match(h, /href="\/m\/4800\/"/);
  assert.match(h, /الوحدة/);
  assert.equal(M.playerBlock(null, o), "");
});
