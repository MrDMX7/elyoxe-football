// node --test site/lib/person_view.test.cjs — an archive man's profile (lib/person_view.cjs) from graph/archive_export.persons
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), V = require("./person_view.cjs");

const P = { n: "Harry Kewell", ar: "هاري كيول", b: "1978-09-22", h: 180, ft: "left", bp: "Smithfield, Sydney", nat: "Australia",
  car: [["2012/2013", "Stars League", "الغرافة", 101897, 3, 1, 0, 169, 0, 0], ["2004/2005", "Premier League", "ليفربول", 8650, 18, 1, 2, 1215, 1, 0]],
  ms: [["2006", 77, "كأس العالم", 3, 1]], last: [["k1418580", "2011-01-25", "أوزبكستان", 8700, "أستراليا", 6716, 0, 6, 290]],
  tr: [["2008-07-01", "ليفربول", 8650, "غلطة سراي", 8637, null, null], ["2014-06-30", "ملبورن", null, null, null, null, "retired"]],
  inj: [["2013/2014", "concussion", "2013-10-12", "2013-11-02", 22, 2]],
  hon: [["top_scorer", 4, "كأس آسيا", 290, "2011", "3"], ["winner", 1, "Oceania Footballer of the Year", null, "2003", null]], intl: ["أستراليا", 56, 17, "1996–2012"] };
const o = { team: id => [8650, 101897].includes(id), comp: id => (id === 77 ? { key: "world-cup" } : null) };

test("the profile: his facts, honours, every season, his moves, injuries and caps", () => {
  const h = V.body(P, o);
  assert.match(h, /22 سبتمبر 1978/);
  assert.match(h, /اليسرى/);
  assert.match(h, /<a href="\/t\/8650\/">ليفربول<\/a>/);
  assert.match(h, /مسيرته موسم بموسم[\s\S]*?2004\/2005[\s\S]*?Premier League|مسيرته موسم بموسم[\s\S]*?2004\/2005[\s\S]*?الدوري الإنجليزي الممتاز/);
  assert.match(h, /انتقالاته[\s\S]*?غلطة سراي/);
  assert.match(h, /اعتزل/);
  assert.match(h, /إصاباته[\s\S]*?ارتجاج/);
  assert.match(h, /Oceania Footballer of the Year/);
  assert.match(h, /<span class="num">56<\/span>/);
  assert.match(h, /href="\/m\/k1418580\/"/);
});

test("a full record is for the search engines, a name and three games is not", () => {
  assert.equal(V.indexable(P), true);
  assert.equal(V.indexable({ n: "X", ms: [["1990/1991", 538, "الدوري", 3, 0]] }), false);
});

test("the page's title and its Person data", () => {
  assert.match(V.title(P), /هاري كيول: مسيرته/);
  const ld = V.ld(P, "/p/k1/");
  assert.equal(ld["@type"], "Person");
  assert.equal(ld.birthDate, "1978-09-22");
  assert.equal(ld.alternateName, "Harry Kewell");
});

test("a man with a free photo shows it with its credit", () => {
  const h = V.body(P, Object.assign({}, o, { photo: { src: "/v1/ph/k1.webp", page: "https://commons.wikimedia.org/wiki/File:K.jpg", artist: "A. B", license: "CC BY-SA 4.0" } }));
  assert.match(h, /<figure class="pph"[^>]*><img src="\/v1\/ph\/k1\.webp"/);
  assert.match(h, /CC BY-SA 4\.0/);
});
