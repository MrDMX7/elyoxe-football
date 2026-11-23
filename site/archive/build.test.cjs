// node --test site/archive/build.test.cjs — the archive job's pages (site/archive/build.cjs) from graph/archive_export.py's files
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), fs = require("fs"), os = require("os"), path = require("path");
const A = require("./build.cjs");

const SHELL = '<!doctype html><html><head><meta charset="utf-8"><title>__TITLE__</title><meta name="description" content="__DESC__"><link rel="canonical" href="https://tifo.elyoxe.com/__PATH__/"><script type="application/ld+json">{"__LD__":1}</script></head><body><nav><a href="__BACK__">__BACKL__</a>__NAVT__</nav><main>__BODY__</main></body></html>';

function world() {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), "arch-"));
  const data = path.join(d, "data");
  fs.mkdirSync(path.join(data, "editions"), { recursive: true });
  fs.mkdirSync(path.join(data, "matches", "47"), { recursive: true });
  fs.writeFileSync(path.join(data, "editions", "47.json"), JSON.stringify({ fotmob: 47, seasons: [
    { season: "1990/1991", matches: 2, champion: { fotmob: 9825, name: "أرسنال" }, runner_up: null, table: [[1, 9825, "أرسنال", 38, 24, 13, 1, 74, 18, 83]], top_scorers: [] },
    { season: "1889/1890", matches: 0, champion: { fotmob: 8657, name: "بريستون" }, runner_up: null, table: [], top_scorers: [] }] }));
  const m = (k, ev) => ({ id: `k${k}`, k, date: "1990-09-01", comp: 47, season: "1990/1991", h: [9825, "أرسنال", 1], a: [8650, "ليفربول", 2], s: [2, 1],
    ev: ev ? [[10, 0, "goal", "h", "سميث", null, 5]] : undefined });
  fs.writeFileSync(path.join(data, "matches", "47", "1990-1991.json"), JSON.stringify({ comp: 47, season: "1990/1991", matches: [m(1, true), m(2, false)] }));
  fs.writeFileSync(path.join(d, "shell.html"), SHELL);
  fs.writeFileSync(path.join(d, "index.json"), JSON.stringify({ competitions: [{ id: 47, key: "premier-league", name_ar: "الدوري الإنجليزي", season: "2026/2027", country: { iso2: "GB" } }] }));
  fs.writeFileSync(path.join(d, "known.json"), JSON.stringify({ m: [], p: [], t: [9825, 8650] }));
  return { d, o: { data, shell: path.join(d, "shell.html"), index: path.join(d, "index.json"), known: path.join(d, "known.json"), out: path.join(d, "out") } };
}

test("a results-only old match is a page, but not one for the search engines; a match with its goals is", () => {
  const { o } = world();
  const r = A.build(o);
  const read = p => fs.readFileSync(path.join(o.out, p, "index.html"), "utf8");
  assert.doesNotMatch(read("m/k1"), /noindex/);
  assert.match(read("m/k2"), /<meta name="robots" content="noindex,follow">/);
  const urls = JSON.parse(fs.readFileSync(path.join(o.out, "_archive_urls.json"), "utf8"));
  assert.ok(urls.includes("/m/k1/") && !urls.includes("/m/k2/"));
  assert.ok(urls.includes("/c/premier-league/s/1990-1991/") && urls.includes("/c/premier-league/seasons/"));
  assert.equal(r.matches, 2);
});

test("a season page carries the table and links its matches", () => {
  const { o } = world();
  A.build(o);
  const h = fs.readFileSync(path.join(o.out, "c/premier-league/s/1990-1991/index.html"), "utf8");
  assert.match(h, /أرسنال/);
  assert.match(h, /href="\/m\/k1\/"/);
  assert.match(h, /<title>الدوري الإنجليزي 1990\/1991/);
});

test("a match page tells the search engines what it is: a SportsEvent with its teams, date and score", () => {
  const { o } = world();
  A.build(o);
  const h = fs.readFileSync(path.join(o.out, "m/k1/index.html"), "utf8");
  const ld = JSON.parse(h.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/)[1]);
  const ev = ld["@graph"].find(x => x["@type"] === "SportsEvent");
  assert.equal(ev.startDate, "1990-09-01");
  assert.equal(ev.homeTeam.name, "أرسنال");
  assert.equal(ev.awayTeam.name, "ليفربول");
  assert.match(ev.name, /أرسنال 2-1 ليفربول/);
  assert.ok(ld["@graph"].some(x => x["@type"] === "BreadcrumbList"));
});

test("an old match shows the two clubs' earlier meetings in the competition", () => {
  const { o } = world();
  const f = path.join(o.data, "matches", "47", "1989-1990.json");
  fs.writeFileSync(f, JSON.stringify({ comp: 47, season: "1989/1990", matches: [{ id: "k9", k: 9, date: "1989-12-01", comp: 47, season: "1989/1990",
    h: [8650, "ليفربول", 2], a: [9825, "أرسنال", 1], s: [3, 0] }] }));
  const ed = JSON.parse(fs.readFileSync(path.join(o.data, "editions", "47.json"), "utf8"));
  ed.seasons.splice(1, 0, { season: "1989/1990", matches: 1, champion: { fotmob: 8650, name: "ليفربول" }, runner_up: null, table: [], top_scorers: [] });
  fs.writeFileSync(path.join(o.data, "editions", "47.json"), JSON.stringify(ed));
  A.build(o);
  const h = fs.readFileSync(path.join(o.out, "m/k1/index.html"), "utf8");
  assert.doesNotMatch(h, /ما عندنا مواجهات سابقة/);
  assert.match(h, /href="\/m\/k9\/"/);
});

test("every man with a record gets his profile, and the matches link to it; a man with the site's page keeps the site's", () => {
  const { o } = world();
  fs.mkdirSync(path.join(o.data, "people"), { recursive: true });
  fs.writeFileSync(path.join(o.data, "people", "5.json"), JSON.stringify({ "5": { n: "Alan Smith", ar: "آلان سميث", b: "1962-11-21",
    car: [["1990/1991", "Premier League", "أرسنال", 9825, 37, 22, 0, null, 0, 0]], ms: [["1990/1991", 47, "الدوري الإنجليزي", 1, 1]] },
    "6": { n: "Ian Wright", fm: 77, car: [["1993/1994", "Premier League", "أرسنال", 9825, 39, 23, 0, null, 0, 0]] } }));
  fs.writeFileSync(o.known, JSON.stringify({ m: [], p: ["77"], t: [9825, 8650] }));
  const mf = path.join(o.data, "matches", "47", "1990-1991.json"), md = JSON.parse(fs.readFileSync(mf, "utf8"));
  md.matches[0].lu = { h: [["آلان سميث", null, "9", 1, 5]] };                 // [name, page key, shirt, started, Tifo id]
  fs.writeFileSync(mf, JSON.stringify(md));
  const r = A.build(o);
  const h = fs.readFileSync(path.join(o.out, "p/k5/index.html"), "utf8");
  assert.match(h, /آلان سميث/);
  assert.match(h, /"@type":"Person"/);
  assert.ok(!fs.existsSync(path.join(o.out, "p/k6/index.html")));            // FotMob's 77 has the site's page
  assert.match(fs.readFileSync(path.join(o.out, "m/k1/index.html"), "utf8"), /href="\/p\/k5\/"/);   // his line-up row
  assert.equal(r.persons, 1);
});

test("an old club and a referee get their pages, and the match links both", () => {
  const { o } = world();
  fs.writeFileSync(path.join(o.data, "clubs.json"), JSON.stringify({ "2": { n: "Liverpool FC (old)", ss: [["1990/1991", 47, "الدوري الإنجليزي", 38, 23, 7, 8, 77, 40]] } }));
  fs.writeFileSync(path.join(o.data, "referees.json"), JSON.stringify({ "9": { n: "M Halsey", ms: [["1990/1991", 47, "الدوري", 25, 70, 2]] } }));
  fs.writeFileSync(o.known, JSON.stringify({ m: [], p: [], t: [9825] }));              // 8650 has no site page: the archive's k2
  const mf = path.join(o.data, "matches", "47", "1990-1991.json"), md = JSON.parse(fs.readFileSync(mf, "utf8"));
  md.matches[0].ref = "M Halsey"; md.matches[0].rk = 9;
  fs.writeFileSync(mf, JSON.stringify(md));
  A.build(o);
  const m = fs.readFileSync(path.join(o.out, "m/k1/index.html"), "utf8");
  assert.match(m, /href="\/t\/k2\/"/);
  assert.match(m, /href="\/r\/k9\/"/);
  assert.ok(fs.existsSync(path.join(o.out, "t/k2/index.html")) && fs.existsSync(path.join(o.out, "r/k9/index.html")));
  const r = fs.readFileSync(path.join(o.out, "r/k9/index.html"), "utf8");
  assert.match(r, /"@type":"Person","name":"M Halsey","jobTitle":"Football referee"/);      // a referee is a Person to the search engines
});

test("a page carries the shell's footer only, not a second one of its own", () => {
  const { o } = world();
  fs.writeFileSync(o.shell, SHELL.replace("__BODY__", '__BODY__<footer class="foot"><p>SITE</p></footer>'));
  A.build(o);
  for (const p of ["m/k1", "c/premier-league/s/1990-1991", "c/premier-league/seasons"]) {
    const h = fs.readFileSync(path.join(o.out, p, "index.html"), "utf8");
    assert.equal((h.match(/<footer class="foot"/g) || []).length, 1, p);
    assert.match(h, /<p>SITE<\/p><\/footer>/, p);
  }
});

test("every coach without a site page gets /coach/k<id>/, and an old match links both coaches", () => {
  const { o } = world();
  const f = path.join(o.data, "matches", "47", "1990-1991.json"), s = JSON.parse(fs.readFileSync(f, "utf8"));
  s.matches[0].co = { h: "George Graham", a: "Kenny Dalglish" };
  s.matches[0].ck = { h: 11, a: 12 };
  fs.writeFileSync(f, JSON.stringify(s));
  fs.writeFileSync(path.join(o.data, "coaches.json"), JSON.stringify({
    11: { n: "George Graham", sp: [["أرسنال", 9825, "1986-08-23", "1995-02-18", 460, 225, 133, 102, 700, 400]] },
    12: { n: "Kenny Dalglish", fm: 500, sp: [["ليفربول", 8650, "1985-08-17", "1991-02-20", 300, 180, 70, 50, 600, 250]] } }));
  fs.writeFileSync(o.known, JSON.stringify({ m: [], p: [], t: [9825, 8650], coach: [500] }));
  const r = A.build(o);
  const g = fs.readFileSync(path.join(o.out, "coach/k11/index.html"), "utf8");
  assert.match(g, /George Graham/);
  assert.match(g, /<a href="\/t\/9825\/">أرسنال<\/a>/);
  const k12 = fs.readFileSync(path.join(o.out, "coach/k12/index.html"), "utf8");   // the site has Dalglish's /coach/500/: a pointer there
  assert.match(k12, /<meta http-equiv="refresh" content="0;url=\/coach\/500\/">/);
  assert.match(k12, /<link rel="canonical" href="https:\/\/tifo.elyoxe.com\/coach\/500\/">/);
  assert.match(k12, /noindex/);
  const m = fs.readFileSync(path.join(o.out, "m/k1/index.html"), "utf8");
  assert.match(m, /href="\/coach\/k11\/"/);
  assert.match(m, /href="\/coach\/500\/"/);
  assert.equal(r.coaches, 1);
  assert.ok(JSON.parse(fs.readFileSync(path.join(o.out, "_archive_urls.json"), "utf8")).includes("/coach/k11/"));
});

test("a coach's page shows his own photo, else the one of his playing days", () => {
  const { o } = world();
  fs.writeFileSync(path.join(o.data, "coaches.json"), JSON.stringify({
    11: { n: "George Graham", pid: 5, sp: [["أرسنال", 9825, "1986-08-23", "1995-02-18", 460, 225, 133, 102, 700, 400]] },
    13: { n: "Bertie Mee", sp: [["أرسنال", 9825, "1966-08-20", "1976-05-01", 400, 200, 100, 100, 600, 400]] } }));
  const cr = { artist: "A", license: "CC BY 2.0", page: "https://commons.wikimedia.org/wiki/File:X.jpg" };
  fs.writeFileSync(o.known, JSON.stringify({ m: [], p: [], t: [9825, 8650], ph: { k5: cr, c13: cr } }));
  A.build(o);
  assert.match(fs.readFileSync(path.join(o.out, "coach/k11/index.html"), "utf8"), /<img src="\/v1\/ph\/k5\.webp"/);
  assert.match(fs.readFileSync(path.join(o.out, "coach/k13/index.html"), "utf8"), /<img src="\/v1\/ph\/c13\.webp"/);
});

test("a FotMob match the site has no page for is the archive's, and the build says where (_fm2k.json) for the site's links", () => {
  const { o } = world();
  const f = path.join(o.data, "matches", "47", "1990-1991.json"), s = JSON.parse(fs.readFileSync(f, "utf8"));
  s.matches[0].id = "4000001";                         // FotMob knows it, the site has no /m/4000001/
  s.matches[1].id = "4000002";
  fs.writeFileSync(f, JSON.stringify(s));
  fs.writeFileSync(o.known, JSON.stringify({ m: ["4000002"], p: [], t: [9825, 8650] }));
  A.build(o);
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(o.out, "_fm2k.json"), "utf8")), { "4000001": 1 });
  assert.ok(fs.existsSync(path.join(o.out, "m/k1/index.html")) && !fs.existsSync(path.join(o.out, "m/k2/index.html")));
});

test("a FotMob man the site has no page for is the archive's, and the build says where (_fm2p.json)", () => {
  const { o } = world();
  fs.mkdirSync(path.join(o.data, "people"), { recursive: true });
  fs.writeFileSync(path.join(o.data, "people", "5.json"), JSON.stringify({
    "5": { n: "Eugene Frimpong", fm: 1526227, car: [["2025/2026", "LaLiga2", "بونفيرادينا", null, 32, 2, 0, null, 0, 0]] },
    "6": { n: "Ian Wright", fm: 77, car: [["1993/1994", "Premier League", "أرسنال", 9825, 39, 23, 0, null, 0, 0]] },
    "7": { n: "Old Man", car: [["1950/1951", "League", "x", null, 30, 1, 0, null, 0, 0]] } }));
  fs.writeFileSync(o.known, JSON.stringify({ m: [], p: ["77"], t: [9825, 8650] }));
  A.build(o);
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(o.out, "_fm2p.json"), "utf8")), { 1526227: 5 });
});
