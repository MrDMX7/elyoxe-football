/* Tifo articles (docs/superpowers/specs/2026-11-18-articles-design.md), read from v1/news/articles.json and v1/news/a/<id>.json:
     /news/<id>/                  the article: the text in the HTML, NewsArticle data, the photo (1200 px, max-image-preview:large),
                                  the byline «تحرير تيفو», links to the match and to the related articles
     /about/ /how-we-write/ /corrections/   the trust pages Google News looks for
     sitemap-news.xml             the last 48 hours (Google News sitemap)
   Called by build.cjs with its helpers; returns the URLs for sitemap.xml and {match id: article id} for the match pages. */
"use strict";
const AUTHOR = "تحرير تيفو";
const E = s => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const T = iso => { try { return new Date(iso).toLocaleString("ar-AE-u-nu-latn", { timeZone: "Asia/Dubai", day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" }); } catch (e) { return ""; } };

const TRUST = [
  { path: "/about/", title: "من نحن | تيفو", desc: "تيفو موقع كرة قدم عربي من الإمارات: النتائج والجداول والمقالات من بيانات تيفو.",
    body: "<h1>من نحن</h1><p>تيفو موقع كرة قدم عربي من الإمارات. ينشر النتائج المباشرة والجداول والإحصائيات لأكثر من 40 بطولة، ومقالات تكتبها «تحرير تيفو».</p><p>المقالات تُكتب من بيانات تيفو نفسها: نتائج المباريات وأحداثها دقيقة بدقيقة، والإحصائيات، والجداول. وإذا استند خبر إلى وسيلة إعلام، ذُكرت باسمها في النص.</p><p>للتواصل: <a href=\"mailto:hello@elyoxe.com\">hello@elyoxe.com</a></p>" },
  { path: "/how-we-write/", title: "كيف نكتب | تيفو", desc: "كيف تكتب «تحرير تيفو» مقالاتها: من البيانات، وبفحص كل رقم قبل النشر.",
    body: "<h1>كيف نكتب</h1><p>كل مقال في تيفو يبدأ من ورقة حقائق: نتيجة المباراة وأحداثها وإحصائياتها وترتيب الفريقين، كما يسجلها تيفو. يُكتب المقال بمساعدة الذكاء الاصطناعي من هذه الورقة وحدها.</p><p>قبل النشر يُفحص المقال آلياً: كل نتيجة ودقيقة ورقم واسم يجب أن يكون في الورقة، وترتيب الأهداف والطرد يطابق المباراة. المقال الذي لا يجتاز الفحص لا يُنشر.</p><p>الصور لقطات من المباراة نفسها من القنوات الرسمية، أو بطاقة المباراة من تيفو.</p>" },
  { path: "/corrections/", title: "سياسة التصحيح | تيفو", desc: "كيف تصحح تيفو الخطأ إذا وقع.",
    body: "<h1>سياسة التصحيح</h1><p>إذا وجدت خطأً في مقال، راسلنا على <a href=\"mailto:hello@elyoxe.com\">hello@elyoxe.com</a> مع رابط المقال.</p><p>نصحح الخطأ في المقال نفسه، ويظهر تاريخ آخر تحديث تحت العنوان. وإذا تغيّرت بيانات المباراة بعد النشر، مثل نسب هدف إلى لاعب آخر، يُعاد كتابة التقرير ويُحدّث تلقائياً.</p>" },
];

function related(doc, all, n){
  const mine = new Set((doc.entities || []).map(e => e.join(":")));
  return all.filter(d => d && d.id !== doc.id && (d.entities || []).some(e => mine.has(e.join(":"))))
    .sort((a, b) => String(b.published).localeCompare(String(a.published))).slice(0, n);
}

function articleHtml(doc, rel){
  const img = doc.image || {};
  const secs = (doc.sections || []).map(s => `<h2>${E(s.subhead)}</h2>` + (s.paragraphs || []).map(p => `<p>${E(p)}</p>`).join("")).join("");
  const facts = (doc.facts_box || []).length ? `<aside class="card facts"><h2>حقائق سريعة</h2><ul>${doc.facts_box.map(f => `<li>${E(f)}</li>`).join("")}</ul></aside>` : "";
  const rl = (rel || []).length ? `<section class="grp"><h2>ذات صلة</h2><ul>${rel.map(r => `<li><a href="/news/${E(r.id)}/">${E(r.headline)}</a></li>`).join("")}</ul></section>` : "";
  const mod = doc.modified && doc.modified !== doc.published ? ` · آخر تحديث ${E(T(doc.modified))}` : "";
  return `<article class="art"><p class="crumbs"><a href="/news/">الأخبار</a></p><h1>${E(doc.headline)}</h1><p class="lede">${E(doc.standfirst)}</p>`
    + `<p class="byline muted">${AUTHOR} · ${E(T(doc.published))}${mod}</p>`
    + (img.url ? `<figure><img src="${E(img.url)}" width="${img.w || 1200}" height="${img.h || 675}" alt="${E(img.caption || doc.headline)}" loading="eager"><figcaption>${E(img.caption || "")}</figcaption></figure>` : "")
    + secs + facts
    + (doc.match ? `<p><a href="/m/${E(doc.match)}/">صفحة المباراة: الأحداث والتشكيلة والإحصائيات</a></p>` : "")
    + rl + `<p class="muted small"><a href="/how-we-write/">كيف نكتب</a> · <a href="/corrections/">سياسة التصحيح</a> · <a href="/about/">من نحن</a></p></article>`;
}

function articleLd(doc, SITE){
  return { "@context": "https://schema.org", "@type": "NewsArticle", headline: doc.headline, description: doc.standfirst,
    image: doc.image && doc.image.url ? [doc.image.url] : [], datePublished: doc.published, dateModified: doc.modified || doc.published,
    author: { "@type": "Organization", name: AUTHOR, url: SITE + "/about/" },
    publisher: { "@type": "Organization", name: "تيفو", logo: { "@type": "ImageObject", url: SITE + "/icons/icon-512.png" } },
    mainEntityOfPage: SITE + "/news/" + doc.id + "/", inLanguage: "ar" };
}

function newsSitemap(docs, SITE, now){
  const recent = docs.filter(d => d && now - Date.parse(d.published) <= 48 * 36e5);
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">\n`
    + recent.map(d => `<url><loc>${E(SITE + "/news/" + d.id + "/")}</loc><news:news><news:publication><news:name>تيفو</news:name><news:language>ar</news:language></news:publication><news:publication_date>${E(d.published)}</news:publication_date><news:title>${E(d.headline)}</news:title></news:news></url>`).join("\n")
    + "\n</urlset>\n";
}

function listHtml(list){
  if (!list || !list.length) return "";
  return `<section class="grp" id="articles"><h2>مقالات تيفو</h2><ul class="arts">${list.map(a => `<li><a href="/news/${E(a.id)}/">${a.image && a.image.url ? `<img src="${E(a.image.url)}" width="120" height="68" alt="" loading="lazy">` : ""}<span>${E(a.headline)}</span></a></li>`).join("")}</ul></section>`;
}

async function render(X){
  const { get, pool, write, page, SITE, OUT, fs, path } = X;
  const lst = ((await get("news/articles.json", 2)) || {}).articles || [];
  // every article ever published (news/articles-all.json, no limit): a page dropped from the short list must not be deleted
  const all = ((await get("news/articles-all.json", 2)) || {}).articles || lst;
  const docs = (await pool(all, 8, a => get(`news/a/${a.id}.json`, 2))).filter(Boolean);
  const urls = [], byMatch = {};
  for (const d of docs){
    write(`news/${d.id}/index.html`, page({ path: `/news/${d.id}/`, page: "ref", title: `${d.headline} | تيفو`, desc: d.standfirst,
      ogUrl: d.image && d.image.url, ogW: d.image && d.image.w, ogH: d.image && d.image.h, ld: articleLd(d, SITE),
      head: '<meta name="robots" content="max-image-preview:large">', body: articleHtml(d, related(d, docs, 5)) }));
    urls.push(`/news/${d.id}/`);
    if (d.kind === "report" && d.match) byMatch[d.match] = d.id;
  }
  for (const t of TRUST){ write(t.path.replace(/^\//, "") + "index.html", page({ path: t.path, page: "ref", title: t.title, desc: t.desc, body: t.body })); urls.push(t.path); }
  fs.writeFileSync(path.join(OUT, "sitemap-news.xml"), newsSitemap(docs, SITE, Date.now()));
  return { urls, byMatch, latest: lst.slice(0, 10) };
}

module.exports = { render, articleHtml, articleLd, newsSitemap, listHtml, related, TRUST, AUTHOR };
