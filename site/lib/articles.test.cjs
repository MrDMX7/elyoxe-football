// node --test site/lib/articles.test.cjs — Tifo articles' pages (lib/articles.cjs) on hand-made documents
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), A = require("./articles.cjs");
const SITE = "https://tifo.elyoxe.com";
const doc = (id, o) => Object.assign({ id, kind: "report", headline: "العين يفوز على الوحدة 2-1", standfirst: "فاز العين.", author: "تحرير تيفو",
  sections: [{ subhead: "الأهداف", paragraphs: ["سجل فلان في الدقيقة 10."] }], facts_box: ["حقيقة"],
  image: { url: SITE + "/v1/news/img/" + id + ".jpg", w: 1200, h: 675, caption: "لقطة", card: false },
  match: 9, entities: [["team", 1], ["team", 2]], published: "2026-11-18T20:00:00+00:00", modified: "2026-11-18T20:05:00+00:00" }, o || {});

test("the page body carries the headline, the byline, the photo with its caption and the trust links", () => {
  const h = A.articleHtml(doc("r-9"), []);
  assert.match(h, /<h1[^>]*>العين يفوز على الوحدة 2-1<\/h1>/);
  assert.match(h, /تحرير تيفو/); assert.match(h, /<figure[\s\S]*r-9\.jpg[\s\S]*<figcaption>لقطة<\/figcaption>/);
  assert.match(h, /href="\/how-we-write\/"/); assert.match(h, /href="\/m\/9\/"/);
});

test("NewsArticle data has the author, the dates and the 1200 px image", () => {
  const ld = A.articleLd(doc("r-9"), SITE);
  assert.equal(ld["@type"], "NewsArticle"); assert.equal(ld.author.name, "تحرير تيفو");
  assert.equal(ld.datePublished, "2026-11-18T20:00:00+00:00"); assert.equal(ld.dateModified, "2026-11-18T20:05:00+00:00");
  assert.deepEqual(ld.image, [SITE + "/v1/news/img/r-9.jpg"]); assert.equal(ld.mainEntityOfPage, SITE + "/news/r-9/");
});

test("the news sitemap lists the last 48 hours only, with the Google News fields", () => {
  const now = Date.parse("2026-11-19T12:00:00Z");
  const xml = A.newsSitemap([doc("r-1"), doc("r-2", { published: "2026-11-10T10:00:00+00:00" })], SITE, now);
  assert.match(xml, /xmlns:news="http:\/\/www\.google\.com\/schemas\/sitemap-news\/0\.9"/);
  assert.match(xml, /<loc>https:\/\/tifo\.elyoxe\.com\/news\/r-1\/<\/loc>/); assert.doesNotMatch(xml, /r-2/);
  assert.match(xml, /<news:name>تيفو<\/news:name><news:language>ar<\/news:language>/);
});

test("related articles share a club, newest first, never the article itself", () => {
  const all = [doc("r-1", { entities: [["team", 1]], published: "2026-11-17T00:00:00Z" }), doc("r-2", { entities: [["team", 5]] }),
               doc("r-3", { entities: [["team", 2]], published: "2026-11-18T00:00:00Z" }), doc("r-9")];
  assert.deepEqual(A.related(doc("r-9"), all, 5).map(d => d.id), ["r-3", "r-1"]);
});

test("the three trust pages exist", () => {
  assert.deepEqual(A.TRUST.map(t => t.path), ["/about/", "/how-we-write/", "/corrections/"]);
});

test("pages are built from the full index, the list from the short one", async () => {
  // final review, finding 3: pages beyond the newest 500 were deleted by the next deploy
  const files = { "news/articles.json": { articles: [{ id: "r-2" }] }, "news/articles-all.json": { articles: [{ id: "r-1" }, { id: "r-2" }] },
                  "news/a/r-1.json": doc("r-1"), "news/a/r-2.json": doc("r-2") };
  const written = [];
  const out = await A.render({ get: async p => files[p] || null, pool: async (xs, n, fn) => Promise.all(xs.map(fn)), write: rel => written.push(rel),
    page: o => o.path, SITE, OUT: "/tmp", fs: { writeFileSync: () => {} }, path: require("path") });
  assert.ok(written.includes("news/r-1/index.html") && written.includes("news/r-2/index.html"));
  assert.deepEqual(out.latest.map(a => a.id), ["r-2"]);
});

test("a breaking article carries the «عاجل» label", () => {
  assert.match(A.articleHtml(doc("n-1", { kind: "news", breaking: true }), []), /<span class="brk">عاجل<\/span>/);
  assert.doesNotMatch(A.articleHtml(doc("n-2", { kind: "news" }), []), /class="brk"/);
});

test("an article's photo fits the phone and its text is readable (owner's phone, 2026-11-19: a 1200 px photo widened the page)", () => {
  const fs = require("fs"), path = require("path");
  for (const f of ["../src/tifo.css", "../src/v5/content.css"]) {
    const css = fs.readFileSync(path.join(__dirname, f), "utf8").replace(/\s+/g, "");
    assert.match(css, /\.art[^{}]*figureimg\{[^}]*max-width:100%[^}]*height:auto/, f);    // content.css scopes it under .lc
    assert.match(css, /\.art[^{}]*p\{[^}]*font-size:1\.0625rem/, f);
  }
});
