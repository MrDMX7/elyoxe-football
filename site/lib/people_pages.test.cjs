// node --test site/lib/people_pages.test.cjs — the old players' pages (/p/k<id>/) from v1/people/index.json and awards/players.json
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), PP = require("./people_pages.cjs");

const TAL = { name: "Adnan Al Talyani", name_ar: "عدنان الطلياني", born: "1964-10-30", died: null, nat: "الإمارات", wc: [["1990", 3, 0]] };
const HON = [["asian-footballer-of-the-year", "1990", "winner", 1, null], [null, "1986/1987", "top_scorer", 1, 538], ["x", "1991", "winner", 3, null]];

test("the page: name, birth, national team, World Cups, honours; never a career total", () => {
  const h = PP.personBody(TAL, HON, { award: k => (k === "asian-footballer-of-the-year" ? { key: k, name: "Asian Footballer of the Year", name_ar: "أفضل لاعب في آسيا" } : null),
    comp: c => (c === 538 ? { name_ar: "دوري أدنوك للمحترفين", href: "/c/uae-pro-league/" } : null) });
  assert.match(h, /<span class="num">1964<\/span>/);
  assert.match(h, /الإمارات/);
  assert.match(h, /كأس العالم/);
  assert.match(h, /<span class="num">1990<\/span>/);
  assert.match(h, /أفضل لاعب في آسيا/);
  assert.doesNotMatch(h, /مباراة دولية/);                  // internationals before FotMob are partial: no total
});

test("titles and indexing", () => {
  assert.equal(PP.title(TAL), "عدنان الطلياني: ألقابه وجوائزه ومشاركاته في كأس العالم | تيفو");
  assert.equal(PP.indexable(TAL, HON), true);
  assert.equal(PP.indexable({ wc: [] }, [["x", "1991", "winner", 1, null]]), false);          // one award, no World Cup: a page, not indexed
});

test("the national team's record, from its article", () => {
  const b = PP.intlBlock(["United Arab Emirates", 161, 52, "1983–1997"]);
  assert.match(b, /مع المنتخب/);
  assert.match(b, /<span class="num">161<\/span> مباراة دولية/);
  assert.match(b, /<span class="num">52<\/span> هدف/);
  assert.match(b, /1983–1997/);
  assert.equal(PP.intlBlock(null), "");
  assert.match(PP.personBody(TAL, HON, {}, ["United Arab Emirates", 161, 52, "1983–1997"]), /161/);
});
