# Tifo articles in Tifo's design, part A: the pages and the minute — implementation plan

> Executed inline (the owner: «اكتب السبك وابدأ»). TDD for every code change; each page is checked at 375 px on the live data
> before it ships.

**Goal:** the article page in Tifo's design (headline on the photo, clubs and players with «تابع», share, reading time,
«ذات صلة» with photos), `/news/` as our articles only with «من الصحف» as its own tab, a «مقالات تيفو» block on the home page,
and every new or changed article page up within a minute of being written.

**Spec:** `docs/superpowers/specs/2026-11-19-articles-pages-design.md` §1, §2, §3, §7.

**Architecture:**
- `site/lib/articles.cjs` renders everything article-shaped:
  - `articleHtml`, `newsIndexHtml`, `homeBlock`;
  - its own stylesheet `site/lib/articles.css`, served as `/news/a.<hash>.css`, so the pages do not wait for the v5 bundle
    or its generator.
- **The full build** (`site/build.cjs`, hourly):
  - writes the article pages, `/news/`, `/news/press/` (the journal list as today) and the home block;
  - saves two **shells**: `page()`'s real output for an article page and for `/news/`, with markers in place of the title,
    the description, the photo, the structured data and the body. `tools/runner.py` uploads them after a publish to
    `state/site/shells.json`.
- **The fast step** (`news/articles/pages.py`, in the journal workflow after «Tifo articles»):
  - reads the shells and the article docs;
  - asks `site/lib/render_news.cjs` to fill the shells for every article new or changed since its last run (all of them
    when the shells changed), plus `/news/` and `sitemap-news.xml`;
  - uploads them to the site bucket;
  - deletes the pages of withdrawn articles;
  - invalidates exactly those paths, and sends the new URLs to IndexNow.
- **The full build no longer syncs the paths the fast step owns** (`news/index.html`, `news/[a-z]-*`, `news/a.*.css`,
  `sitemap-news.xml`). Its `--delete` would otherwise remove a page written while it was building, for up to an hour.

**Facts read in the code (2026-11-19):**
- The site bucket is `elyoxe-tifo-site-574771023173` and the distribution `E2BSJNNZS8B0WJ`, both read from the stack's
  outputs.
- The CI role `tifo-github-actions` already has `s3:Put/Delete` on the site bucket and `cloudfront:CreateInvalidation` on
  the distribution.
- `page(o)` takes `ogUrl`, `ld` (an object, `JSON.stringify`d) and `head`.
- A team's «تابع» is `<button class="pill pri" data-fav="t:<id>" data-n="<name>">`, handled by v5 `app.js` on any page. A
  player's follow sheet lives on the player page.

## Tasks

1. **The doc carries `topic`:**
   - **What:** news gets the story's kind (and `stage`); reports get `report`. `summary()` carries both, so the lists can
     filter.
   - **Tests:** `test_articles_news_run.py`, `test_articles_run.py`.
2. **The article page:**
   - **What:** `articleHtml(doc, rel, names)`:
     - the head, with the headline on the photo, the type chip, and «عاجل» in red;
     - the standfirst, then the byline with reading time and the time;
     - the share block: `navigator.share`, else WhatsApp, X and copy;
     - the clubs and players strip (logo, name, a link; «تابع» as `data-fav` for clubs; a player links to his page, where
       his follow sheet is);
     - the body, «حقائق سريعة», the match link, «ذات صلة» as four photo cards, and the trust links.

     `articles.css` holds the styles, in v5's tokens.
   - **Tests:** `site/lib/articles.test.cjs`.
3. **The news page and the home block:**
   - **What:**
     - `newsIndexHtml(list)`: the tabs (links), the filters, the lead, the grid, the first 30, and «المزيد», which loads
       more from `articles.json`;
     - `homeBlock(list)`: one large card and three small ones, redrawn in the page from `articles.json`;
     - `build.cjs` writes `/news/` (ours), `/news/press/` (the journal list) and the home block.
   - **Tests:** `site/lib/articles.test.cjs`.
4. **Shells:**
   - **What:** `build.cjs` writes `cache/shells.json` (the article page and `/news/` from `page()` with markers, plus the
     CSS name); `runner.py` uploads it after a publish, and excludes the fast step's paths from its sync.
   - **Tests:** a node test that the shell holds every marker once; a Python test of the exclude list.
5. **The fast step:**
   - **What:**
     - `site/lib/render_news.cjs` (input: shells, docs, names, list; output: files in a folder);
     - `news/articles/pages.py`, which decides what changed (`state/articles/pages.json`), runs the renderer, uploads,
       deletes, invalidates and sends IndexNow;
     - the workflow step «Article pages» (timeout 5 min, continue-on-error).
   - **Tests:** `test_articles_pages.py` (what changed, what is deleted, the upload headers), and a node test of the
     renderer.
6. **Ship:**
   1. Render locally on the live data and check at 375 px.
   2. Merge and push, then start the site build.
   3. Once the shells exist, start the journal and check that a new article's page answers within the minute.
