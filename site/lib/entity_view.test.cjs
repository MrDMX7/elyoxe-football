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
  assert.match(h, /<a class="row" href="\/m\/k1\/">[\s\S]*?ليفربول/);
});

test("a club's page says when it was founded and where it plays, when the graph knows", () => {
  const h = V.club({ ...C, f: 1889, st: ["بلاو لين", 15876, "London"] }, o);
  assert.match(h, /تأسّس[\s\S]*?<span class="num">1889<\/span>/);
  assert.match(h, /الملعب[\s\S]*?بلاو لين/);
  assert.match(h, /سعة الملعب[\s\S]*?15,876/);
  assert.doesNotMatch(V.club(C, o), /تأسّس|الملعب/);
});

test("the search engines get the big records only", () => {
  assert.equal(V.refIndexable(R), true);
  assert.equal(V.refIndexable({ n: "X", ms: [["2003", 1, "x", 5, 0, 0]] }), false);
  assert.equal(V.clubIndexable(C), true);
});

test("a last-games row is one link to the match, with no club link inside it (a link in a link breaks the row)", () => {
  for (const h of [V.referee(R, o), V.club(C, o)]) {
    const rows = h.match(/<a [^>]*href="\/m\/k[^"]*"[\s\S]*?<\/a>/g) || [];
    assert.ok(rows.length > 0);
    for (const r of rows) assert.doesNotMatch(r.slice(2), /<a /, r);
  }
});

const K = { n: "Henk ten Cate", b: "1954-12-09", nat: "Netherlands", pid: 77, sp: [["الجزيرة", 102101, "2016-10-01", "2017-05-20", 30, 20, 5, 5, 60, 30], ["العين", null, "2010-01-01", "2010-06-01", 12, 6, 3, 3, 20, 14]],
  hon: [["winner", 1, "مدرب العام", null, "2017", null]], last: [["2600001", "2016-10-01", "الجزيرة", 102101, "العين", 102117, 2, 1, 538]] };

test("a coach's page: his record, every spell club by club, his awards and last games; his playing days linked", () => {
  const h = V.coach(K, Object.assign({}, o, { team: id => id === 102101, person: pid => pid === 77 }));
  assert.match(h, /Henk ten Cate/);
  assert.match(h, /9 ديسمبر 1954/);
  assert.match(h, /<span class="num">42<\/span> مباراة/);
  assert.match(h, /<a href="\/t\/102101\/">الجزيرة<\/a>/);
  assert.match(h, /2016–2017/);
  assert.match(h, /مدرب العام[\s\S]*?2017/);
  assert.match(h, /href="\/m\/2600001\/"/);
  assert.match(h, /href="\/p\/k77\/"/);
});

test("a coach of 30 games or an award is for the search engines; a few games is not", () => {
  assert.equal(V.coachIndexable(K), true);
  assert.equal(V.coachIndexable({ n: "X", sp: [["a", null, "2000-01-01", "2000-02-01", 5, 1, 1, 3, 2, 6]] }), false);
  assert.equal(V.coachIndexable({ n: "Y", hon: [["winner", 1, "مدرب العام", null, "2001", null]] }), true);
});

test("a coach's page carries his free photo with its credit", () => {
  const h = V.coach(K, Object.assign({}, o, { photo: { src: "/v1/ph/c11.webp", page: "https://commons.wikimedia.org/wiki/File:G.jpg", artist: "A. B", license: "CC BY 2.0" } }));
  assert.match(h, /<figure class="pph"[^>]*><img src="\/v1\/ph\/c11\.webp"/);
  assert.match(h, /CC BY 2\.0/);
});

test("a coach's facts are rows of their card too", () => {
  const h = V.coach(K, Object.assign({}, o, { person: pid => pid === 77 }));
  assert.match(h, /<span class="rt">الجنسية<\/span><span class="rv"><span class="lat">Netherlands<\/span><\/span>/);
  assert.match(h, /<a class="row" href="\/p\/k77\/"><span class="rt">مسيرته لاعباً<\/span>/);
  assert.doesNotMatch(h, /<ul class="lc">/);
});

test("a club's history on its own, for the encyclopedia's club page: the record, the titles, season by season", () => {
  const c = { n: "Alanyaspor", ar: "ألانيا سبور", ss: [["2020/2021", 71, "الدوري التركي", 34, 15, 9, 10, 50, 40]], hon: [["runner_up", "كأس تركيا", 151, "2019/2020"]] };
  const h = V.clubHistory(c, { comp: fid => (fid === 71 ? { key: "super-lig" } : null) });
  assert.match(h, /34<\/span> مباراة في أرشيف تيفو/);
  assert.match(h, /href="\/c\/super-lig\/s\/2020-2021\/"/);
  assert.match(h, /وصيف/);
  assert.doesNotMatch(h, /<h1>/);                                        // the page has its own heading
});
