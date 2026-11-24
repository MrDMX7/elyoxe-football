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

test("a FotMob man's profile carries his encyclopedia facts (data/fmp.json) with his club's Arabic name (fm_teams.json)", () => {
  const { o } = world();
  fs.mkdirSync(path.join(o.data, "people"), { recursive: true });
  fs.writeFileSync(path.join(o.data, "people", "5.json"), JSON.stringify({ "5": { n: "Eugene Frimpong", fm: 1526227, car: [["2025/2026", "LaLiga2", "x", null, 32, 2, 0, null, 0, 0]] } }));
  fs.writeFileSync(path.join(o.data, "fmp.json"), JSON.stringify({ 1526227: { bio: { team: 1585, mv: 139630, shirt: 16 }, s0: ["2025/2026", 8005, 32, 2, 0, 6.05] } }));
  fs.writeFileSync(path.join(o.data, "fm_teams.json"), JSON.stringify({ 1585: "كالاماتا", 8005: "بونفيرادينا" }));
  A.build(o);
  const h = fs.readFileSync(path.join(o.out, "p/k5/index.html"), "utf8");
  assert.match(h, /النادي<\/span><span class="rv">كالاماتا/);
  assert.match(h, /القيمة السوقية/);
  assert.match(h, /هذا الموسم[\s\S]*?بونفيرادينا/);
});

test("a season's top scorer links his profile", () => {
  const { o } = world();
  const ef = path.join(o.data, "editions", "47.json"), ed = JSON.parse(fs.readFileSync(ef, "utf8"));
  ed.seasons[0].top_scorers = [{ rank: 1, name: "آلان سميث", value: "22", tifo: 5 }];
  fs.writeFileSync(ef, JSON.stringify(ed));
  const mf = path.join(o.data, "matches", "47", "1990-1991.json"), md = JSON.parse(fs.readFileSync(mf, "utf8"));
  md.matches.forEach(m => { delete m.ev; });                                   // only the honours list names him
  fs.writeFileSync(mf, JSON.stringify(md));
  fs.mkdirSync(path.join(o.data, "people"), { recursive: true });
  fs.writeFileSync(path.join(o.data, "people", "5.json"), JSON.stringify({ "5": { n: "Alan Smith", car: [["1990/1991", "Premier League", "أرسنال", 9825, 37, 22, 0, null, 0, 0]] } }));
  A.build(o);
  assert.match(fs.readFileSync(path.join(o.out, "c/premier-league/s/1990-1991/index.html"), "utf8"), /href="\/p\/k5\/"[^>]*>[\s\S]{0,80}آلان سميث/);
  assert.match(fs.readFileSync(path.join(o.out, "c/premier-league/seasons/index.html"), "utf8"), /href="\/p\/k5\/"[^>]*>[\s\S]{0,80}آلان سميث/);   // the seasons list too
});

test("a FotMob club the site has a page for gets no second page in the archive", () => {
  const { o } = world();
  fs.writeFileSync(path.join(o.data, "clubs.json"), JSON.stringify({ "7": { n: "Al Ain", fm: 102117, ss: [["1990/1991", 538, "الدوري", 30, 20, 5, 5, 60, 30]] },
    "8": { n: "Alanyaspor", fm: 4678, ss: [["2020/2021", 71, "الدوري التركي", 34, 15, 9, 10, 50, 40]] } }));
  fs.writeFileSync(o.known, JSON.stringify({ m: [], p: [], t: ["102117", 9825, 8650] }));
  A.build(o);
  assert.equal(fs.existsSync(path.join(o.out, "t", "k7", "index.html")), false);
  assert.equal(fs.existsSync(path.join(o.out, "t", "k8", "index.html")), true);
});

test("a club with the encyclopedia's page is shown there: its history goes out for that page and it gets no /t/k page", () => {
  const { o } = world();
  fs.writeFileSync(path.join(o.data, "clubs.json"), JSON.stringify({ "8": { n: "Alanyaspor", fm: 4678, ss: [["2020/2021", 71, "الدوري التركي", 34, 15, 9, 10, 50, 40]] },
    "9": { n: "Old Club", ss: [["1990/1991", 47, "الدوري", 30, 10, 10, 10, 40, 40]] } }));
  fs.writeFileSync(o.known, JSON.stringify({ m: [], p: [], t: [9825, 8650], dbclub: ["4678"] }));
  A.build(o);
  assert.equal(fs.existsSync(path.join(o.out, "t", "k8", "index.html")), false);
  assert.equal(fs.existsSync(path.join(o.out, "t", "k9", "index.html")), true);
  const h = JSON.parse(fs.readFileSync(path.join(o.out, "_club_history.json"), "utf8"));
  assert.deepEqual(Object.keys(h), ["4678"]);
  assert.equal(h["4678"].n, "Alanyaspor");
});

test("a match links a club whose page is the encyclopedia's to that page", () => {
  const { o } = world();
  fs.writeFileSync(o.known, JSON.stringify({ m: [], p: [], t: [9825], dbclub: ["8650"] }));
  A.build(o);
  const m = fs.readFileSync(path.join(o.out, "m/k1/index.html"), "utf8");
  assert.match(m, /href="\/db\/club\/8650\/"/);
  assert.match(m, /href="\/t\/9825\/"/);
  assert.doesNotMatch(m, /\/t\/8650\//);
});

// a competition the site has no page for: graph/archive_export.py's competitions.json names it, its files carry our own number
function archiveWorld() {
  const w = world(), data = w.o.data, id = 2000000123;
  fs.mkdirSync(path.join(data, "matches", String(id)), { recursive: true });
  fs.writeFileSync(path.join(data, "competitions.json"), JSON.stringify([
    { id: 47, cid: 9, name: "Premier League", name_ar: "الدوري الإنجليزي", kind: "league", country: "GB-ENG", seasons: 2, matches: 2 },
    { id, cid: 123, name: "Maltese Cup", name_ar: "كأس مالطا", kind: "cup", scope: "national", country: "MT", country_ar: "مالطا", seasons: 1, matches: 2, first: "1950", last: "1950" }]));
  fs.writeFileSync(path.join(data, "editions", `${id}.json`), JSON.stringify({ fotmob: id, seasons: [
    { season: "1950", matches: 2, champion: { fotmob: null, name: "فلوريانا" }, runner_up: null, table: [], top_scorers: [] }] }));
  const m = (k, ev) => ({ id: `k${k}`, k, date: "1950-05-01", comp: id, season: "1950", h: [null, "فلوريانا", 1], a: [null, "سليما", 2], s: [2, 1],
    ev: ev ? [[10, 0, "goal", "h", "بورغ", null, 5]] : undefined });
  fs.writeFileSync(path.join(data, "matches", String(id), "1950.json"), JSON.stringify({ comp: id, season: "1950", matches: [m(71, true), m(72, false)] }));
  return w;
}

test("a competition the site has no page for gets its seasons at /c/k<id>/, a place in the directory, and pages for the matches that hold more than a score", () => {
  const { o } = archiveWorld();
  A.build(o);
  const has = p => fs.existsSync(path.join(o.out, p, "index.html")), read = p => fs.readFileSync(path.join(o.out, p, "index.html"), "utf8");
  assert.ok(has("c/k123") && has("c/k123/s/1950") && !has("c/k123/seasons"));
  assert.ok(has("c/premier-league/seasons") && !has("c/k9"));                  // the site's own keep their key
  assert.ok(has("m/k71") && !has("m/k72"));
  assert.match(read("c/k123/s/1950"), /href="\/c\/k123\/"/);
  assert.doesNotMatch(read("c/k123/s/1950"), /\/m\/k72\//);
  assert.match(read("c/k123/s/1950"), /<div class="mr" data-mid="k72">/);
  assert.match(read("c/k123/s/1950"), /<a class="mr" href="\/m\/k71\/"/);
  const dir = read("c/archive");
  assert.match(dir, /مالطا/);
  assert.match(dir, /href="\/c\/k123\/"[\s\S]*كأس مالطا/);
  assert.doesNotMatch(dir, /premier-league/);
  const c = JSON.parse(fs.readFileSync(path.join(o.out, "_comps.json"), "utf8"));
  assert.deepEqual(c, { n: 1, keys: ["k123"], fm: {} });
  const urls = JSON.parse(fs.readFileSync(path.join(o.out, "_archive_urls.json"), "utf8"));
  assert.ok(urls.includes("/c/k123/") && urls.includes("/c/archive/") && urls.includes("/c/k123/s/1950/"));
});

test("a run of some competitions writes no directory", () => {
  const { o } = archiveWorld();
  A.build(Object.assign({}, o, { comps: [2000000123] }));
  assert.ok(fs.existsSync(path.join(o.out, "c/k123/index.html")) && !fs.existsSync(path.join(o.out, "c/archive/index.html")) && !fs.existsSync(path.join(o.out, "_comps.json")));
});

// graph/features_export.py's files next to the world's: Arsenal (Tifo 1) and Liverpool (Tifo 2) met three times
function versusWorld(known) {
  const w = world(), vs = path.join(w.o.data, "vs"), J = (p, x) => { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, JSON.stringify(x)); };
  const ms = [["1989-05-26", 47, "1988/1989", 0, 0, 2, 900, 0], ["1990-09-01", 47, "1990/1991", 1, 2, 1, 1, 0], ["1991-03-03", 47, "1990/1991", 0, 0, 1, 901, 0]];
  J(path.join(vs, "names.json"), { 1: ["أرسنال", 9825, 0], 2: ["ليفربول", 8650, 0], 3: ["إنجلترا", 0, 1] });
  J(path.join(vs, "index.json"), { pairs: { "1-2": 3 }, hubs: { 1: 120 } });
  J(path.join(vs, "pairs", "1.json"), { "1-2": ms });
  J(path.join(vs, "teams", "1.json"), { 1: { tot: [120, 70, 30, 20, 200, 90], first: "1989-05-26", last: "1991-03-03", opp: [[2, 3, 3, 0, 0, 5, 1]],
    run: { win: [3, "1989-05-26", "1991-03-03"] }, elo: { now: 1700, peak: [1710, "1991-01-01"], low: [1500, "1989-06-01"], yr: [[1989, 1550], [1990, 1650], [1991, 1700]] } } });
  J(path.join(w.o.data, "elo", "nations.json"), { day: "1991-03-03", now: [[3, 2000, 2100, "1990-07-01", 400]], peaks: [[3, 2100, "1990-07-01"]] });
  J(path.join(w.o.data, "elo", "leagues.json"), { 47: [[1, 1700, 1710, "1991-01-01"], [2, 1500, null, null]] });
  if (known) fs.writeFileSync(w.o.known, JSON.stringify(Object.assign({ m: [], p: [], t: [9825, 8650] }, known)));
  return w;
}

test("two teams' every meeting is one page, a team's record against everyone another, and the ratings a third; the match and the seasons list link them", () => {
  const { o } = versusWorld();
  const r = A.build(o);
  const read = p => fs.readFileSync(path.join(o.out, p, "index.html"), "utf8");
  const p = read("vs/1-2");
  assert.match(p, /أرسنال/);
  assert.match(p, /ليفربول/);
  assert.match(p, /href="\/m\/k1\/"/);                          // the meeting the archive has a page for
  assert.doesNotMatch(p, /\/m\/k900\//);                        // and none for the one it has not
  assert.doesNotMatch(p, /noindex/);
  assert.match(read("vs/1"), /href="\/vs\/1-2\/"/);
  assert.match(read("elo"), /إنجلترا/);
  assert.match(read("elo"), /href="\/elo\/premier-league\/"/);
  assert.match(read("elo/premier-league"), /أرسنال[\s\S]*ليفربول/);
  assert.match(read("m/k1"), /href="\/vs\/1-2\/"/);
  assert.match(read("c/premier-league/seasons"), /href="\/elo\/premier-league\/"/);
  const urls = JSON.parse(fs.readFileSync(path.join(o.out, "_archive_urls.json"), "utf8"));
  for (const u of ["/vs/1-2/", "/vs/1/", "/elo/", "/elo/premier-league/"]) assert.ok(urls.includes(u), u);
  assert.equal(r.versus, 2);
});

test("a pair the site has its own page for gets no second one: the match links the site's", () => {
  const { o } = versusWorld({ h2h: ["8650-9825"] });
  A.build(o);
  assert.ok(!fs.existsSync(path.join(o.out, "vs/1-2/index.html")));
  assert.match(fs.readFileSync(path.join(o.out, "m/k1/index.html"), "utf8"), /href="\/h2h\/8650-9825\/"/);
});

test("a run of some competitions writes none of them", () => {
  const { o } = versusWorld();
  A.build(Object.assign({}, o, { comps: [47] }));
  assert.ok(!fs.existsSync(path.join(o.out, "vs")) && !fs.existsSync(path.join(o.out, "elo")));
  assert.doesNotMatch(fs.readFileSync(path.join(o.out, "m/k1/index.html"), "utf8"), /\/vs\//);
});
