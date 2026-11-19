// node --test site/lib/awards.test.cjs — the awards pages (lib/awards.cjs) from v1/awards/* (graph/publish.py)
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), AW = require("./awards.cjs");

const IX = { awards: [
  { key: "ballon-dor", name: "Ballon d'Or", name_ar: "الكرة الذهبية", group: "world", years: 69, first: "1956", last: "2025", top: ["ليونيل ميسي", 8, 30981] },
  { key: "uae-pro-league-golden-boot", name: "UAE Golden Boot", name_ar: null, group: "league", years: 3, first: "2020", last: "2022", top: null }] };
const BD = { key: "ballon-dor", name: "Ballon d'Or", name_ar: "الكرة الذهبية", group: "world", most: [["ليونيل ميسي", 8, 30981]],
  years: [{ season: "2025", podium: [{ rank: 1, name: "Ousmane Dembélé", name_ar: "عثمان ديمبيلي", fotmob: 1, team: "باريس سان جيرمان", value: "1380" },
                                       { rank: 2, name: "Lamine Yamal", name_ar: null, fotmob: 2, team: null, value: null }] },
          { season: "1956", podium: [{ rank: 1, name: "Stanley Matthews", name_ar: null, fotmob: null, team: null, value: "47" }] }] };
const pages = new Set(["1"]);

test("the index groups the awards and links each one", () => {
  const h = AW.indexBody(IX, {});
  assert.match(h, /جوائز عالمية/);
  assert.match(h, /href="\/awards\/ballon-dor\/"/);
  assert.match(h, /الكرة الذهبية/);
  assert.match(h, /منذ <span class="num">1956<\/span>/);
  assert.match(h, /<span class="lat">UAE Golden Boot<\/span>/);          // no Arabic name: the Latin one, marked
});

test("an award page links a winner who has a page and names the others", () => {
  const h = AW.awardBody(BD, { hasPage: id => pages.has(String(id)) });
  assert.match(h, /<a href="\/p\/1\/">عثمان ديمبيلي<\/a>/);
  assert.doesNotMatch(h, /href="\/p\/2\/"/);                                  // no site page for him
  assert.match(h, /<span class="lat">Lamine Yamal<\/span>/);
  assert.match(h, /الثاني/);
  assert.match(h, /<span class="lat">Stanley Matthews<\/span>/);
  assert.match(h, /الأكثر فوزاً/);
});

test("a player's block lists his awards and honours", () => {
  const h = AW.playerBlock([["ballon-dor", "2023", "winner", 1, null], [null, "2012/2013", "top_scorer", 1, 538], ["ballon-dor", "2017", "winner", 3, null]],
    { award: k => IX.awards.find(a => a.key === k), comp: c => (c === 538 ? { name_ar: "دوري أدنوك للمحترفين", href: "/c/uae-pro-league/" } : null) });
  assert.match(h, /href="\/awards\/ballon-dor\/"/);
  assert.match(h, /هداف دوري أدنوك للمحترفين/);
  assert.match(h, /الثالث/);
  assert.equal(AW.playerBlock([], {}), "");
});

test("small awards are not indexed", () => {
  assert.equal(AW.indexable(IX.awards[0]), true);
  assert.equal(AW.indexable(IX.awards[1]), false);
});
