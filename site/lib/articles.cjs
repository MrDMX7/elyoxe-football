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

// the page's look (spec 2026-11-19 §2): one stylesheet for the article, /news/ and the home block, named by its content
const CSS = require("fs").readFileSync(require("path").join(__dirname, "articles.css"), "utf8");
const CSS_NAME = "a." + require("crypto").createHash("sha1").update(CSS).digest("hex").slice(0, 10) + ".css";
const SITE_URL = "https://tifo.elyoxe.com";
const HEAD = `<meta name="robots" content="max-image-preview:large"><link rel="stylesheet" href="/news/${CSS_NAME}">`;
const TOPIC = { report: "تقرير مباراة", transfer: "انتقالات", injury: "إصابات", statement: "تصريحات", presser: "مؤتمر صحفي", official: "إعلان رسمي" };
const STAGE = { rumour: "إشاعة", talks: "مفاوضات", agreed: "اتفاق", here_we_go: "اتفاق نهائي", official: "رسمي" };
const kindOf = doc => (TOPIC[doc.topic || (doc.kind === "report" ? "report" : "")] || "خبر") + (doc.topic !== "report" && STAGE[doc.stage] ? " · " + STAGE[doc.stage] : "");

// names for the clubs and players strip: teams.json's teams and names/players_ar.json -> (kind, id) -> {name, img, href} | null
function makeNames(teams, players){
  return (kind, id) => {
    if (kind === "team"){ const t = (teams || {})[id] || {}; return t.name_ar ? { name: t.name_ar, img: `/logo/${id}.png`, href: `/t/${id}/` } : null; }
    if (kind === "player"){ const p = (players || {})[id]; const n = typeof p === "string" ? p : p && p.ar; return n ? { name: n, img: `/v1/ph/${id}.webp`, href: `/p/${id}/` } : null; }
    return null;
  };
}

function readTime(doc){
  const words = [doc.standfirst || ""].concat(...(doc.sections || []).map(s => s.paragraphs || [])).join(" ").split(/\s+/).filter(Boolean).length;
  const m = Math.max(1, Math.round(words / 200));
  return m === 1 ? "دقيقة قراءة" : m === 2 ? "دقيقتان قراءة" : m <= 10 ? `${m} دقائق قراءة` : `${m} دقيقة قراءة`;
}

function shareHtml(doc){
  const url = `${SITE_URL}/news/${doc.id}/`, u = encodeURIComponent(url), t = encodeURIComponent(doc.headline || "");
  return `<div class="shr" data-url="${E(url)}" data-title="${E(doc.headline)}"><button type="button" class="pill pri" data-native hidden>مشاركة</button>`
    + `<a class="pill" href="https://wa.me/?text=${t}%20${u}" target="_blank" rel="noopener">واتساب</a>`
    + `<a class="pill" href="${E(`https://x.com/intent/post?text=${t}&url=${u}`)}" target="_blank" rel="noopener">X</a>`
    + `<button type="button" class="pill" data-copy>نسخ الرابط</button></div>`
    + `<script>(function(){var s=document.currentScript.previousElementSibling,n=s.querySelector("[data-native]"),u=s.dataset.url,t=s.dataset.title;`
    + `if(navigator.share){n.hidden=false;n.onclick=function(){navigator.share({title:t,url:u}).catch(function(){})}}`
    + `s.querySelector("[data-copy]").onclick=function(e){var b=e.currentTarget;(navigator.clipboard?navigator.clipboard.writeText(u):Promise.reject()).then(function(){b.textContent="انتسخ"},function(){prompt("الرابط",u)})}})()</script>`;
}

function entsHtml(doc, names){
  if (!names) return "";
  const chips = (doc.entities || []).map(([k, id]) => {
    const n = names(k, id); if (!n) return "";
    const img = `<img src="${E(n.img)}" alt="" width="26" height="26" loading="lazy"${k === "player" ? ' onerror="this.remove()"' : ""}>`;
    return `<span class="ent-c"><a class="ent" href="${E(n.href)}">${img}${E(n.name)}</a>`
      + (k === "team" ? `<button type="button" class="pill" data-fav="t:${E(id)}" data-n="${E(n.name)}">تابع</button>` : "") + "</span>";
  }).filter(Boolean);
  return chips.length ? `<nav class="ents" aria-label="في المقال">${chips.join("")}</nav>` : "";
}

function articleHtml(doc, rel, names){
  const img = doc.image || {};
  const secs = (doc.sections || []).map(s => (s.subhead ? `<h2>${E(s.subhead)}</h2>` : "") + (s.paragraphs || []).map(p => `<p>${E(p)}</p>`).join("")).join("");
  const facts = (doc.facts_box || []).length ? `<aside class="facts"><h2>حقائق سريعة</h2><ul>${doc.facts_box.map(f => `<li>${E(f)}</li>`).join("")}</ul></aside>` : "";
  const rl = (rel || []).slice(0, 4);
  const rels = rl.length ? `<section class="rel"><h2>ذات صلة</h2><div class="rg">${rl.map(r => `<a class="rc" href="/news/${E(r.id)}/">${r.image && r.image.url ? `<img src="${E(r.image.url)}" alt="" width="600" height="338" loading="lazy">` : ""}<span>${E(r.headline)}</span></a>`).join("")}</div></section>` : "";
  const mod = doc.modified && doc.modified !== doc.published ? ` · آخر تحديث ${E(T(doc.modified))}` : "";
  const chip = doc.breaking ? `<span class="brk">عاجل</span><span class="ah-k">${E(kindOf(doc))}</span>` : `<span class="ah-k">${E(kindOf(doc))}</span>`;
  const head = img.url
    ? `<header class="ah"><figure class="ah-f"><div class="ah-ph"><img src="${E(img.url)}" width="${img.w || 1200}" height="${img.h || 675}" alt="${E(img.caption || doc.headline)}" fetchpriority="high"><div class="ah-in">${chip}<h1>${E(doc.headline)}</h1></div></div>${img.caption ? `<figcaption class="ah-cap">${E(img.caption)}</figcaption>` : ""}</figure></header>`
    : `<header class="ah np"><div class="ah-in">${chip}<h1>${E(doc.headline)}</h1></div></header>`;
  return `<article class="art"><p class="crumbs"><a href="/news/">الأخبار</a></p>${head}<p class="lede">${E(doc.standfirst)}</p>`
    + `<p class="ab"><b>${AUTHOR}</b><span>${readTime(doc)}</span><span>${E(T(doc.published))}${mod}</span></p>`
    + shareHtml(doc) + entsHtml(doc, names)
    + secs + facts
    + (doc.match ? `<a class="mlink" href="/m/${E(doc.match)}/">صفحة المباراة: الأحداث والتشكيلة والإحصائيات</a>` : "")
    + rels + `<p class="trust"><a href="/how-we-write/">كيف نكتب</a> · <a href="/corrections/">سياسة التصحيح</a> · <a href="/about/">من نحن</a></p></article>`;
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
  const { get, pool, write, page, SITE, OUT, fs, path, names } = X;
  const lst = ((await get("news/articles.json", 2)) || {}).articles || [];
  // every article ever published (news/articles-all.json, no limit): a page dropped from the short list must not be deleted
  const all = ((await get("news/articles-all.json", 2)) || {}).articles || lst;
  const docs = (await pool(all, 8, a => get(`news/a/${a.id}.json`, 2))).filter(Boolean);
  const urls = [], byMatch = {};
  fs.mkdirSync(path.join(OUT, "news"), { recursive: true }); fs.writeFileSync(path.join(OUT, "news", CSS_NAME), CSS);
  for (const d of docs){
    write(`news/${d.id}/index.html`, page({ path: `/news/${d.id}/`, page: "ref", title: `${d.headline} | تيفو`, desc: d.standfirst,
      ogUrl: d.image && d.image.url, ogW: d.image && d.image.w, ogH: d.image && d.image.h, ld: articleLd(d, SITE),
      head: HEAD, body: articleHtml(d, related(d, docs, 4), names) }));
    urls.push(`/news/${d.id}/`);
    if (d.kind === "report" && d.match) byMatch[d.match] = d.id;
  }
  for (const t of TRUST){ write(t.path.replace(/^\//, "") + "index.html", page({ path: t.path, page: "ref", title: t.title, desc: t.desc, body: t.body })); urls.push(t.path); }
  fs.writeFileSync(path.join(OUT, "sitemap-news.xml"), newsSitemap(docs, SITE, Date.now()));
  return { urls, byMatch, latest: lst.slice(0, 10) };
}

module.exports = { render, articleHtml, articleLd, newsSitemap, listHtml, related, makeNames, readTime, kindOf, TRUST, AUTHOR, CSS, CSS_NAME };
