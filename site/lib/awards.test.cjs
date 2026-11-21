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

test("a winner FotMob does not know links to his archive page", () => {
  const d = { key: "ballon-dor", years: [{ season: "1956", podium: [{ rank: 1, name: "Stanley Matthews", name_ar: "ستانلي ماثيوز", fotmob: null, tifo: 7, team: null, value: "47" }] }], most: [] };
  assert.match(AW.awardBody(d, { hasPage: () => false, person: id => id === 7 }), /<a href="\/p\/k7\/">ستانلي ماثيوز<\/a>/);
  assert.doesNotMatch(AW.awardBody(d, { hasPage: () => false, person: () => false }), /\/p\/k7\//);
});

test("an award table with no team or value for any year has no empty columns (QA 2026-11-21: 759 of 820 award pages)", () => {
  const d = { key: "fifa-fair-play-award", years: [{ season: "2025", podium: [{ rank: 1, name: "Andreas Harlass", name_ar: "أندرياس هارلاس", fotmob: null, team: null, value: null }] },
    { season: "2024", podium: [{ rank: 1, name: "Thiago Maia", name_ar: "تياغو مايا", fotmob: null, team: null, value: null }] }], most: [] };
  const h = AW.awardBody(d, {});
  assert.doesNotMatch(h, /<td[^>]*>\s*<\/td>/);
  assert.doesNotMatch(h, /<th>الفريق<\/th>/);
  assert.doesNotMatch(h, /<th><\/th>/);
  const b = AW.awardBody(BD, { hasPage: () => false });                       // the Ballon d'Or has teams and points
  assert.match(b, /<th>الفريق<\/th>/);
  assert.match(b, /باريس سان جيرمان/);
  assert.doesNotMatch(b, /<td[^>]*>\s*<\/td>/);                                // a year without them shows «—»
});

test("awards sharing one Arabic name get the qualifier their English name carries, so no two pages share a title", () => {
  const list = [
    { key: "bulgarian-footballer-of-the-year-men", name: "Bulgarian Footballer of the Year — Men", name_ar: "جائزة لاعب كرة القدم البلغاري للسنة" },
    { key: "bulgarian-footballer-of-the-year-women", name: "Bulgarian Footballer of the Year — Women", name_ar: "جائزة لاعب كرة القدم البلغاري للسنة" },
    { key: "bulgarian-footballer-of-the-year-youth", name: "Bulgarian Footballer of the Year — Youth", name_ar: "جائزة لاعب كرة القدم البلغاري للسنة" },
    { key: "don-balon-award-winners-best-spanish-player", name: "Don Balón Award — Winners — Best Spanish Player", name_ar: "جائزة دون بالون" },
    { key: "don-balon-award-winners-best-foreign-player", name: "Don Balón Award — Winners — Best Foreign Player", name_ar: "جائزة دون بالون" },
    { key: "fai-u21", name: "FAI International Football Awards — Under-21 International Player of the Year", name_ar: "لاعب العام" },
    { key: "lma", name: "League Managers Association Awards — LMA Manager of the Year", name_ar: "مدرب العام" },
    { key: "fa-w", name: "The FA Women's Football Awards — Manager of the Year", name_ar: "مدرب العام" },
    { key: "ballon-dor", name: "Ballon d'Or", name_ar: "الكرة الذهبية" }];
  AW.uniqueNames(list);
  const n = k => list.find(a => a.key === k).name_ar;
  assert.equal(n("bulgarian-footballer-of-the-year-women"), "جائزة لاعب كرة القدم البلغاري للسنة للسيدات");
  assert.equal(n("bulgarian-footballer-of-the-year-youth"), "جائزة لاعب كرة القدم البلغاري للسنة للشباب");
  assert.equal(n("bulgarian-footballer-of-the-year-men"), "جائزة لاعب كرة القدم البلغاري للسنة للرجال");
  assert.equal(n("don-balon-award-winners-best-foreign-player"), "جائزة دون بالون للأجانب");
  assert.equal(n("fa-w"), "مدرب العام للسيدات");                                  // «coach» is already in «مدرب العام»
  assert.equal(n("lma"), "مدرب العام");
  assert.equal(n("ballon-dor"), "الكرة الذهبية");                                 // a name of its own is left alone
  assert.doesNotMatch(n("fai-u21"), /\(\d/);                                       // no made-up numbering
});
