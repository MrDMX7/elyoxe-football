# تيفو v5 in production: the rollout contract

v5 (`DESIGN.md`, `IA.md`) replaces the v3 shell on every page of tifo.elyoxe.com. This file says where things live now, the
contract every page builder follows (`page()` in `site/build.cjs`), how pages that other code writes pick up the v5 shell without
doing anything, and how to take it back.

## Files

| what | where |
|---|---|
| renderers (shared by the build and the browser) | `site/src/v5/ui.js` (`U`, `window.U5`), `site/src/v5/pages.js` (`P5`, `window.P5`) |
| browser client | `site/src/v5/app.js` (bundled with ui.js + pages.js as `assets/app5.<hash>.js`) |
| styles | `site/src/v5/app.css` (v5) + `site/src/v5/content.css` (the old blocks' classes, generated) → `assets/app.<hash>.css` |
| content layer generator | `site/redesign/v5/legacy-css.cjs` (re-run after editing `src/tifo.css`, `src/v3.css` or `src/allmatches.css`) |
| legacy bodies → v5 skeleton | `site/lib/v5.cjs` (`legacy5`, `secRows`, `grp`, `tabOf`) |
| icons, splash screens | `site/redesign/v5/icons.py` → `site/icons/*.png` (committed) |
| the old widgets' client | `site/src/render.js` + `site/src/v3.js` + `site/src/app.js` → `assets/legacy.<hash>.js`, loaded after app5 on pages that need it |

`site/redesign/v5/build.cjs` (the `/next/` preview) is frozen: it still reads `src/v5/*`, but the production changes
(links, mounts, production-only sections) are not tested there. Use the production build with `TIFO_ONLY` instead (below).

`src/shell.js` and `src/keyart.js` are no longer loaded by any page; `src/tifo.css`, `src/v3.css` and the v3 asset files are
still written to `out/assets/` (old cached pages keep working, and a revert needs nothing rebuilt).

## page(o)

```
page({ path, page, title, desc,            // required
       noindex, og, ogv, ld, names, pp,    // SEO and names, unchanged from v3
       attrs,                              // extra <body> attributes (data-id, data-comp… the old scripts read them)
       nav, near, legacy,                  // tab hint, «near kickoff» stamp, force the legacy bundle
       v5: { nav, body, tab, sheets, cls, data, tools }   // a page drawn with U/P5
       | body, tools, lg, heroExtra,       // or a v2/v3-shaped body: legacy5() turns it into the v5 skeleton
       head, js })                         // extra <head> HTML; extra script URLs (deferred, after the v5 and legacy bundles)
```

The SEO head (title, description, canonical or `noindex`, Open Graph, JSON-LD, manifest, theme colours, speculation rules) is
built the same way for both kinds of page and never depends on the template. Sitemap, `lastmod`, the dead-link pass, the
`write()` text fixes and the page-count guard are unchanged.

### A new page, the easy way (no v5 code needed)

Pass a v3-shaped `body`:

```html
<p class="crumbs"><a href="/">تيفو</a><a href="/arabs/">العرب</a></p>
<h1>العنوان</h1>
<p class="season">سطر تحت العنوان</p>
<p>مقدمة (تصير داخل .lc)</p>
<section class="blk" id="x"><h2>عنوان القسم<small>سطر صغير</small></h2> … </section>
<p class="tools"><button type="button" id="mybtn">زر</button></p>
```

`legacy5()` makes: the nav bar with a back button to the **last crumb** (or «المزيد»), a large title (with the crumbs as a
kicker when there are two or more), each `<section class="blk">` as a grouped inset card (`section.grp.blk > .gh h2 + .card.lc`),
any other HTML in a `.lc` container, and `<p class="tools">` rows of buttons moved into the page's «شارك» sheet (ids kept).
Pages under `/worldcup-arabs/` and `/national/<cc>/` with four or more blocks get v3's shelf as rows that open sheets.
Everything inside `.lc` is drawn by `content.css` (the old classes in v5 colours, light and dark), so old markup works as is;
v5 classes (`U.row`, `U.grp`, `U.table`, `.card`, `.chip`…) work too.

### A page drawn with v5

```js
const v5 = { nav: { back: "/x/", backLabel: "x", title: "…", trail: U.navLink("search", "بحث", "/search/") },
             body: '<div class="lt"><h1>…</h1></div>' + U.segbar("g", [["a", "أ"], ["b", "ب"]], "a") + U.pane("g", "a", …, 1) + U.pane("g", "b", …),
             tab: "comps",                     // today | comps | news | mine | more (default: from the path)
             sheets: U.sheet("sh-x", "عنوان", "…"),
             data: { id: 1 } };                // window.V5 in the browser (page, id, built + this)
write("x/index.html", page({ v5, path: "/x/", page: "x", title, desc }));
```

- A sheet opens from any element with `data-sheet="<dialog id>"`; `[data-close]` inside closes it. A body wrapped in
  `<template class="lazys">` is stamped on first open; a pane's `<template class="lazyp">` on first show.
- A block with a widget the legacy client wires at start-up must stay live DOM: add its id to `LIVE_IDS` in build.cjs.
- `page` names in `NOLEGACY` (home, daypage, all, news, mine, more, search, comps, db, league, none, offline) load only the v5
  bundle; every other page also loads `assets/legacy.<hash>.js` (or pass `legacy: true`).
- Extra behaviour for a new page: put it in its own file under `site/src/`, write it to `out/assets/<name>.<hash>.js` in the
  asset block, and pass `js: ["/assets/<name>.<hash>.js"]`.

### In the browser

- `window.U5`, `window.P5`: the renderers. `window.V5`: this page's data. `window.V5C`: competitions, countries, first-visit
  picks, the audit, the share.js version. `window.TR`: render.js on legacy pages, a small stand-in elsewhere.
- Events on `document`: `tifo:match` (every match refresh, detail = the match), `tifo:day` (home list redrawn),
  `tifo:country`, `tifo:fresh` (a good poll), `tifo:nospoil`, `tifo:sheet` (a sheet opened).
- `window.TifoSheet.open(el, from)` / `.close()`: older `<div class="sheet">` (media.js's video sheet) behave like v5 sheets.
- `window.TifoShare` (story, wallpaper, card, listCard, out, banner): loads `share.js` on first use.
- Settings and favourites keep the live site's localStorage keys (`tifo.favs`, `tifo.mine`, `tifo.country`, `tifo.nospoil`,
  `tifo.goalsnd`, `tifo.theme`, `tifo.car`, `tifo.picks`, `tifo.push`…); new: `tifo.island.off`, `tifo.island.x`,
  `tifo.opened`, `tifo.onb`, `tifo.inst.no`, `tifo.allopen`.

## The six features

1. **جزيرة المباراة** (`app.js` island): a pill floating above the tab bar on every page (a mini player: nothing on the page moves when it appears) while a followed team (or a match opened in the
   last hours) is live; tap opens the match; × hides it for that match; المزيد → «جزيرة المباراة» turns it off. Reads
   `v1/live.json` and `v1/all/live.json` (teams outside our competitions) every 25 s only while something followed is live;
   otherwise it looks again at the next followed kickoff (from `/tn/<id>.json`). Goals: a pulse, a polite announcement, the
   whistle when «صوت الهدف» is on. Hidden on that match's own page and in no-spoiler mode's scores.
2. **اليوم** (`P.home`): one page with the day strip and «الكل · مباشر · العرب»; every match of the world under ours
   (`v1/all/<ymd>.json`: FotMob + 365Scores' Arab leagues), loaded when scrolled near, live from `v1/all/live.json`.
   `/today/`, `/tomorrow/` and `/all/` are the same page on their own URL (canonical, title and description unchanged).
3. **First visit** (`#sh-onb`): on a first home visit (not bots), teams by search or from the Arab national teams and the
   leading clubs of each Arab league, and the country; «بعدين» skips; never shown again (`tifo.onb`); the same sheet opens again
   from a row in «فريقي» and in «المزيد» (`[data-onb]`).
4. **App-like navigation**: cross-document view transitions (`@view-transition`), the tab bar held still; speculation rules
   prefetch links (moderate) and the tab bar (eager); where they are unsupported, `app.js` prefetches on touchstart/hover and the
   likeliest cards in view; the back button goes back in history when the visitor came from tifo.
5. **PWA**: `manifest.webmanifest` (Arabic, RTL, any + maskable icons, shortcuts), iPhone splash screens light and dark on the
   pages people add, theme colours per scheme; «ثبّت تيفو» as a quiet card on a second visit (Android: the browser's prompt;
   iPhone: the two Safari steps), 30 days of quiet after «مب الحين»; offline: `/offline/` lists the saved pages and the followed
   teams' next match, last results and table (their `/tn/` files are fetched when the phone is idle).
6. **الأرقام مدققة**: from `v1/audit/latest.json` at build time, only when `ok` and no errors: the footer of every page and
   «المزيد». Absent or failed: nothing is said.

## Dev switches (never set by the runner or deploy.sh)

`TIFO_FETCH_CACHE=<dir>` keeps every `/v1` answer on disk (two builds compare on the same data); `TIFO_ONLY=<regex>` writes only
the matching paths (e.g. `'^/(index\.html|m/123/|t/5789/)'`) and skips the manifest, the dead-link pass and the dashboard;
`TIFO_NO_OG=1` skips the share images; `TIFO_NO_DASH=1` skips the owner's dashboard query. In Git Bash prefix the command with
`MSYS2_ENV_CONV_EXCL='*'`: MSYS rewrites a value that starts with `^/` into a Windows path (`^C:/Program Files/Git/…`) and the
filter then matches nothing.

## Checks

`node site/redesign/v5/qa.cjs --base http://localhost:8794 --pages "/ /m/<id>/ …"` (no horizontal scroll at 360–1280, 44 px
targets, scores as `dir="rtl"` runs, RTL basics, no script errors) and `node site/redesign/v5/lh.cjs` against a local server of
`site/out` (`python site/dev_server.py 8794`).

## Taking it back

The rollout is a set of commits on one branch. `git revert -m 1 <merge commit>` (or reverting the rollout commits) restores the
v3 shell: build.cjs's `page()`, the templates, `src/app.js`, `src/tv.js`, `src/media.js`, `src/render.js` and the icons come
back as they were; nothing in `/v1` or the deploy changes. Every v3 asset is still built, so pages already in caches keep working
either way.
