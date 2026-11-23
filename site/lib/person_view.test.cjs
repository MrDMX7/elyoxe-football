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

test("the facts are rows of their card, a label and its value (a bare list spilled out of the card, 23 Nov)", () => {
  const h = V.body(P, o);
  assert.match(h, /<div class="row"><span class="rt">تاريخ الميلاد<\/span><span class="rv">22 سبتمبر 1978<\/span><\/div>/);
  assert.doesNotMatch(h, /<ul class="lc">/);
});

test("a FotMob man's profile carries what the encyclopedia showed: his club, shirt, value, contract and this season", () => {
  const fm = { bio: { team: 1585, shirt: 16, mv: 139630, contract: "2027-06-30", pos: "وسط" },
    s0: ["2025/2026", 8005, 32, 2, 0, 6.05] };
  const h = V.body(Object.assign({}, P, { pos: null }), Object.assign({}, o, { fm, teamName: id => ({ 1585: "كالاماتا", 8005: "بونفيرادينا" })[id] }));
  assert.match(h, /<span class="rt">النادي<\/span><span class="rv">كالاماتا<\/span>/);
  assert.match(h, /<span class="rt">المركز<\/span><span class="rv">وسط<\/span>/);
  assert.match(h, /<span class="rt">الرقم<\/span><span class="rv"><span class="num">16<\/span><\/span>/);
  assert.match(h, /<span class="rt">القيمة السوقية<\/span><span class="rv"><span class="num">€140<\/span> ألف<\/span>/);
  assert.match(h, /<span class="rt">نهاية العقد<\/span><span class="rv">30 يونيو 2027<\/span>/);
  assert.match(h, /هذا الموسم[\s\S]*?بونفيرادينا[\s\S]*?<span class="num">32<\/span> مباراة[\s\S]*?6\.05/);
});

test("a market value in millions", () => {
  assert.equal(V.mvAr(2500000), '<span class="num">€2.5</span> مليون');
  assert.equal(V.mvAr(80000000), '<span class="num">€80</span> مليون');
});
