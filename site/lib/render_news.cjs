/* The fast «Article pages» renderer (docs/superpowers/specs/2026-11-19-articles-pages-design.md §7): fills the full build's
   shells (site/build.cjs writes them, tools/runner.py saves them to state/site/shells.json) with lib/articles.cjs's own markup.

     node site/lib/render_news.cjs <input.json> <out dir>
     input: {shells: {article, news}, docs: [article docs to render], list: [news/articles.json], teams: {id: {name_ar}},
             players: {id: {ar}}, now: ms}
     out:   news/<id>/index.html for every doc, news/index.html, sitemap-news.xml, news/a.<hash>.css

   Called by news/articles/pages.py, which decides what changed, uploads and deletes. The shell's stylesheet link is swapped for
   the current one, so a page always matches the markup that rendered it. */
"use strict";
const A = require("./articles.cjs");
const SITE = "https://tifo.elyoxe.com";
const E = s => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function fill(shell, m){
  let h = shell.replace(/\/news\/a\.[0-9a-f]{10}\.css/g, "/news/" + A.CSS_NAME);
  for (const [k, v] of Object.entries(m)) h = h.split(k).join(v);
  return h;
}

function renderAll(inp){
  const now = inp.now || Date.now(), list = inp.list || [], names = A.makeNames(inp.teams || {}, inp.players || {});
  const out = {};
  for (const d of inp.docs || []){
    out[`news/${d.id}/index.html`] = fill(inp.shells.article, {
      "__TITLE__": E(`${d.headline} | تيفو`), "__DESC__": E(d.standfirst), "__ID__": E(d.id),
      "__OGURL__": E((d.image && d.image.url) || `${SITE}/og/tifo.png`),
      '{"__LD__":1}': JSON.stringify(A.articleLd(d, SITE)).replace(/</g, "\\u003c"),
      "__BODY__": A.articleHtml(d, A.related(d, list, 4), names),
    });
  }
  out["news/index.html"] = fill(inp.shells.news, {
    "__TITLE__": E("أخبار الكورة اليوم من تحرير تيفو: الانتقالات والإصابات وتقارير المباريات | تيفو"),
    "__DESC__": E("مقالات تيفو: تقارير المباريات وأخبار الانتقالات والإصابات والتصريحات، تكتبها «تحرير تيفو» من بيانات تيفو والمصادر الرسمية."),
    "__BODY__": A.newsIndexHtml(list, now),
  });
  out["sitemap-news.xml"] = A.newsSitemap(list, SITE, now);
  out["news/" + A.CSS_NAME] = A.CSS;
  return out;
}

if (require.main === module){
  const fs = require("fs"), path = require("path");
  const [inFile, outDir] = process.argv.slice(2);
  const files = renderAll(JSON.parse(fs.readFileSync(inFile, "utf8")));
  for (const [rel, body] of Object.entries(files)){
    const f = path.join(outDir, rel); fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, body);
  }
  console.log(JSON.stringify({ files: Object.keys(files).length }));
}

module.exports = { renderAll, fill };
