// node --test site/lib/articles.test.cjs — Tifo articles' pages (lib/articles.cjs) on hand-made documents
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), A = require("./articles.cjs");
const SITE = "https://tifo.elyoxe.com";
const doc = (id, o) => Object.assign({ id, kind: "report", headline: "العين يفوز على الوحدة 2-1", standfirst: "فاز العين.", author: "تحرير تيفو",
  sections: [{ subhead: "الأهداف", paragraphs: ["سجل فلان في الدقيقة 10."] }], facts_box: ["حقيقة"],
  image: { url: SITE + "/v1/news/img/" + id + ".jpg", w: 1200, h: 675, caption: "لقطة", card: false },
  match: 9, entities: [["team", 1], ["team", 2]], published: "2026-11-18T20:00:00+00:00", modified: "2026-11-18T20:05:00+00:00" }, o || {});

test("the headline sits on the photo, with the type, then the standfirst, the byline and the trust links (spec §2)", () => {
  const h = A.articleHtml(doc("r-9"), []);
  assert.match(h, /<header class="ah">[\s\S]*r-9\.jpg[\s\S]*<span class="ah-k">تقرير مباراة<\/span>[\s\S]*<h1>العين يفوز على الوحدة 2-1<\/h1>[\s\S]*<\/header>/);
  assert.match(h, /<figcaption class="ah-cap">لقطة<\/figcaption>/);
  assert.match(h, /<p class="lede">فاز العين\.<\/p>/); assert.match(h, /تحرير تيفو/);
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
    page: o => o.path, SITE, OUT: "/tmp", fs: { writeFileSync: () => {}, mkdirSync: () => {} }, path: require("path") });
  assert.ok(written.includes("news/r-1/index.html") && written.includes("news/r-2/index.html"));
  assert.deepEqual(out.latest.map(a => a.id), ["r-2"]);
});

test("a breaking article carries the «عاجل» label", () => {
  assert.match(A.articleHtml(doc("n-1", { kind: "news", breaking: true }), []), /<span class="brk">عاجل<\/span>/);
  assert.doesNotMatch(A.articleHtml(doc("n-2", { kind: "news" }), []), /class="brk"/);
});

// ---- part A (docs/superpowers/specs/2026-11-19-articles-pages-design.md §2)
const NAMES = A.makeNames({ 1: { name_ar: "العين" }, 2: { name_ar: "الوحدة" } }, { 7: { ar: "سفيان رحيمي" } });

test("a news article's type is its topic and stage; «عاجل» is red", () => {
  assert.match(A.articleHtml(doc("n-1", { kind: "news", topic: "transfer", stage: "official" }), []), /<span class="ah-k">انتقالات · رسمي<\/span>/);
  assert.match(A.articleHtml(doc("n-2", { kind: "news", topic: "injury" }), []), /<span class="ah-k">إصابات<\/span>/);
  assert.match(A.articleHtml(doc("n-3", { kind: "news", topic: "transfer", breaking: true }), []), /<span class="brk">عاجل<\/span>/);
});

test("the byline has the reading time, in Arabic numbers grammar and Western digits", () => {
  const words = n => doc("r-1", { standfirst: "", sections: [{ subhead: "", paragraphs: [Array(n).fill("كلمة").join(" ")] }] });
  assert.match(A.articleHtml(words(150), []), /دقيقة قراءة/);
  assert.match(A.articleHtml(words(390), []), /دقيقتان قراءة/);
  assert.match(A.articleHtml(words(700), []), /4 دقائق قراءة/);
});

test("the share block has the phone's share, WhatsApp, X and copy, with the page's address", () => {
  const h = A.articleHtml(doc("r-9"), []);
  assert.match(h, /<div class="shr" data-url="https:\/\/tifo\.elyoxe\.com\/news\/r-9\/"/);
  assert.match(h, /href="https:\/\/wa\.me\/\?text=[^"]*tifo\.elyoxe\.com%2Fnews%2Fr-9%2F"/);
  assert.match(h, /href="https:\/\/x\.com\/intent\/post\?text=[^"]*&amp;url=https%3A%2F%2Ftifo\.elyoxe\.com%2Fnews%2Fr-9%2F"/);
  assert.match(h, /data-copy/); assert.match(h, /navigator\.share/);
});

test("the clubs and players strip: logo, Arabic name, link, and «تابع» for a club", () => {
  const h = A.articleHtml(doc("r-9", { entities: [["team", 1], ["player", 7], ["team", 99]] }), [], NAMES);
  assert.match(h, /<a class="ent" href="\/t\/1\/"><img src="\/logo\/1\.png"[^>]*>العين<\/a><button type="button" class="pill" data-fav="t:1" data-n="العين">تابع<\/button>/);
  assert.match(h, /<a class="ent" href="\/p\/7\/">[\s\S]*سفيان رحيمي<\/a>/);
  assert.doesNotMatch(h, /\/t\/99\//);                                     // a club with no Arabic name is left out
  assert.doesNotMatch(A.articleHtml(doc("r-9"), []), /class="ents"/);        // no names, no strip
});

test("«ذات صلة» is four photo cards", () => {
  const rel = [1, 2, 3, 4, 5].map(i => doc("r-" + i, { headline: "مقال " + i }));
  const h = A.articleHtml(doc("r-9"), rel);
  assert.equal((h.match(/<a class="rc" href="\/news\/r-\d\/">/g) || []).length, 4);
  assert.match(h, /<a class="rc" href="\/news\/r-1\/"><img src="[^"]*r-1\.jpg"[^>]*><span>مقال 1<\/span><\/a>/);
});

test("the article stylesheet: the head's gradient, 17 px text, a photo that fits", () => {
  const css = A.CSS.replace(/\s+/g, "");
  assert.match(css, /\.ahimg\{[^}]*width:100%[^}]*height:auto/);
  assert.match(css, /linear-gradient/); assert.match(css, /\.artp\{[^}]*font-size:17px/);
  assert.match(A.CSS_NAME, /^a\.[0-9a-f]{10}\.css$/);
});
