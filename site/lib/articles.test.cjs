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
  assert.match(h, /<div class="ashr" data-url="https:\/\/tifo\.elyoxe\.com\/news\/r-9\/"/);
  assert.match(h, /href="https:\/\/wa\.me\/\?text=[^"]*tifo\.elyoxe\.com%2Fnews%2Fr-9%2F"/);
  assert.match(h, /href="https:\/\/x\.com\/intent\/post\?text=[^"]*&amp;url=https%3A%2F%2Ftifo\.elyoxe\.com%2Fnews%2Fr-9%2F"/);
  assert.match(h, /data-copy/); assert.match(h, /navigator\.share/);
});

test("the clubs and players strip: logo, Arabic name, link, and «تابع» for a club", () => {
  const h = A.articleHtml(doc("r-9", { entities: [["team", 1], ["player", 7], ["team", 99]] }), [], NAMES);
  assert.match(h, /<a class="aent" href="\/t\/1\/"><img src="\/logo\/1\.png"[^>]*>العين<\/a><button type="button" class="pill" data-fav="t:1" data-n="العين">تابع<\/button>/);
  assert.match(h, /<a class="aent" href="\/p\/7\/">[\s\S]*سفيان رحيمي<\/a>/);
  assert.doesNotMatch(h, /\/t\/99\//);                                     // a club with no Arabic name is left out
  assert.doesNotMatch(A.articleHtml(doc("r-9"), []), /class="aents"/);        // no names, no strip
});

test("«ذات صلة» is four photo cards", () => {
  const rel = [1, 2, 3, 4, 5].map(i => doc("r-" + i, { headline: "مقال " + i }));
  const h = A.articleHtml(doc("r-9"), rel);
  assert.equal((h.match(/<a class="arc" href="\/news\/r-\d\/">/g) || []).length, 4);
  assert.match(h, /<a class="arc" href="\/news\/r-1\/"><img src="[^"]*r-1\.jpg"[^>]*><span>مقال 1<\/span><\/a>/);
});

test("the article stylesheet: the head's gradient, 17 px text, a photo that fits", () => {
  const css = A.CSS.replace(/\s+/g, "");
  assert.match(css, /\.ahimg\{[^}]*width:100%[^}]*height:auto/);
  assert.match(css, /linear-gradient/); assert.match(css, /\.artp\{[^}]*font-size:17px/);
  assert.match(A.CSS_NAME, /^a\.[0-9a-f]{10}\.css$/);
});

// ---- the news page and the home block (spec §1, §3)
const NOWT = Date.parse("2026-11-19T12:00:00Z");
const item = (i, o) => Object.assign({ id: "n-" + i, kind: "news", topic: "transfer", headline: "خبر " + i, standfirst: "مقدمة " + i,
  image: { url: SITE + "/v1/news/img/n-" + i + ".jpg" }, published: new Date(NOWT - i * 36e5).toISOString() }, o || {});

test("/news/ is our articles: the two tabs, the filters, the lead, the grid of 30 and «المزيد»", () => {
  const list = Array.from({ length: 40 }, (_, i) => item(i + 1));
  const h = A.newsIndexHtml(list, NOWT);
  assert.match(h, /<nav class="ntabs"><a href="\/news\/" aria-current="page">مقالات تيفو<\/a><a href="\/news\/press\/">من الصحف<\/a><\/nav>/);
  for (const t of ["all", "report", "transfer", "injury", "statement"]) assert.match(h, new RegExp(`data-t="${t}"`));
  assert.match(h, /<a class="anl" href="\/news\/n-1\/"/);                                       // the newest leads
  const cards = h.replace(/<script>[\s\S]*?<\/script>/g, "");                              // the rendered cards, not the script's templates
  assert.equal((cards.match(/<a class="nc" /g) || []).length, 29);                            // 30 with the lead
  assert.match(h, /<button type="button" class="nmore" data-from="30">المزيد<\/button>/);
  assert.match(h, /fetch\("\/v1\/news\/articles\.json"/);
});

test("a «عاجل» of the last two hours leads; a press conference files under statements; a report under reports", () => {
  const list = [item(1), item(3, { breaking: true }), item(4, { topic: "presser" }), item(5, { kind: "report", topic: undefined })];
  const h = A.newsIndexHtml(list, NOWT);
  assert.match(h, /<a class="anl" href="\/news\/n-1\/"/);                                       // the «عاجل» is 3 h old: not the lead
  const h2 = A.newsIndexHtml([item(1), item(2, { breaking: true })], NOWT);
  assert.match(h2, /<a class="anl" href="\/news\/n-2\/"/);
  assert.match(h, /<a class="nc" href="\/news\/n-4\/" data-t="statement"/);
  assert.match(h, /<a class="nc" href="\/news\/n-5\/" data-t="report"/);
});

test("«من الصحف» keeps the journal's list under the same two tabs", () => {
  assert.match(A.pressTabs(), /<a href="\/news\/">مقالات تيفو<\/a><a href="\/news\/press\/" aria-current="page">من الصحف<\/a>/);
});

test("the home block: one large card, three small, all articles; redrawn live from articles.json", () => {
  const h = A.homeBlock([1, 2, 3, 4, 5].map(i => item(i)), NOWT);
  assert.match(h, /<section class="ahb">[\s\S]*<a href="\/news\/">كل المقالات<\/a>/);
  const b = h.replace(/<script>[\s\S]*?<\/script>/g, "");
  assert.equal((b.match(/<a class="anl" /g) || []).length, 1); assert.equal((b.match(/<a class="hr" /g) || []).length, 3);
  assert.match(h, /fetch\("\/v1\/news\/articles\.json"/);
  assert.equal(A.homeBlock([], NOWT), "");
});

// ---- the fast step's renderer (spec §7): the full build's shells, filled
test("the renderer fills the shells: every marker, the current stylesheet, the article's data and the news page", () => {
  const RN = require("./render_news.cjs");
  const shell = '<html><head><title>__TITLE__</title><meta property="og:title" content="__TITLE__"><meta name="description" content="__DESC__"><link rel="canonical" href="https://tifo.elyoxe.com/news/__ID__/"><meta property="og:image" content="__OGURL__"><script type="application/ld+json">{"__LD__":1}</script><link rel="stylesheet" href="/news/a.0000000000.css"></head><body>__BODY__</body></html>';
  const d = doc("n-7", { kind: "news", topic: "injury", headline: "إصابة <كبيرة>" });
  const out = RN.renderAll({ shells: { article: shell, news: shell.replace("/news/__ID__/", "/news/") }, docs: [d], list: [d], teams: { 1: { name_ar: "العين" } }, players: {}, now: NOWT });
  const p = out["news/n-7/index.html"];
  assert.ok(p && !/__(TITLE|DESC|ID|OGURL|BODY|LD)__/.test(p));
  assert.match(p, /<title>إصابة &lt;كبيرة&gt; \| تيفو<\/title>/); assert.match(p, /href="https:\/\/tifo\.elyoxe\.com\/news\/n-7\/"/);
  assert.match(p, /"@type":"NewsArticle"/); assert.match(p, new RegExp("/news/" + A.CSS_NAME.replace(/\./g, "\.")));
  assert.match(p, /<a class="aent" href="\/t\/1\/">/);
  assert.match(out["news/index.html"], /<a class="anl" href="\/news\/n-7\/"/);
  assert.match(out["sitemap-news.xml"], /<loc>https:\/\/tifo\.elyoxe\.com\/news\/n-7\/<\/loc>/);
  assert.equal(out["news/" + A.CSS_NAME], A.CSS);
});
