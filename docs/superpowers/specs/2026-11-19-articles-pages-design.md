# Tifo articles in Tifo's own design — spec

**Date:** 2026-11-19. Agreed with the owner question by question the same day.

**Goal:** Tifo's articles (match reports, news, «عاجل») become the site's news and keep the reader on Tifo:
- Today the news page links every story out to Google News and from there to another site; that list moves to a tab of its own.
- The article page is redesigned in Tifo's v5 design (`site/redesign/v5/DESIGN.md`).
- Articles appear on the home page.
- A page goes up within a minute of its article being written.
- Followers of a club or player are notified of new articles.
- A «الأكثر قراءة» list, and the goal videos inside match reports.

**Success:** a reader who opens an article stays on Tifo: they go on to «ذات صلة», a club, or another article. Google indexes
the article within the hour; it is up within the minute it is written. On a phone the page is the screen's width, the text
reads at 17 px, and the photo fits.

## Decisions (the owner's answers)

| # | Question | Decision |
|---|---|---|
| 1 | News page: our articles with Google News? | **Our articles only.** The Google News list moves to its own tab, «من الصحف» |
| 2 | What the article page carries | **The clubs and players** with logos, a link and «تابع». **«ذات صلة»** with photos. **Share** and **reading time**. (Tifo data cards: no) |
| 3 | Where else articles appear | **The home page** only |
| 4 | The article's head | **The headline on the photo**, over a dark gradient (like Marca and Goal) |
| 5 | Additions | **Notifications** to the followers of a club or player. **«الأكثر قراءة»**. **The goal videos** in the match report |
| 6 | How fast a page goes up | **Within a minute** of the article being written |

## 1. The news page `/news/`

- **Two tabs** in v5's segmented control:
  - «مقالات تيفو», the default, at `/news/`;
  - «من الصحف», the journal's list as it is today, at `/news/press/`.

  The tabs are links, so each tab is its own static page that Google can read.
- **Lead:** the newest «عاجل» from the last 2 hours, else the newest article, as a large card:
  - a 16:9 photo across the full width;
  - over a dark gradient, the type chip and the headline in white.
- **Then a grid** of two cards a row: the photo, the headline (three lines at most), the type and the time ago. «عاجل» carries
  the red live badge (v5: live = red).
- **Filters:** الكل · تقارير · انتقالات · إصابات · تصريحات. Each article doc gains `topic`, the journal story's kind
  (transfer, injury, statement, presser, official), or `report`. The filter runs in the page over the cards already there.
- **«الأكثر قراءة»** after the sixth card: five numbered lines (§5).
- **30 cards**, then «المزيد», which loads the next 30 from `v1/news/articles.json` in the page.

## 2. The article page `/news/<id>/`

- **Head:**
  - the photo at 16:9 across the full width;
  - over a dark gradient (transparent to 75% black), the type chip («انتقالات · رسمي», «تقرير مباراة», «عاجل» in red) and
    the headline in white, 24-28 px.

  Under the photo:
  - the standfirst at 19 px;
  - the line «تحرير تيفو · N دقائق قراءة · time», where reading time is the word count / 200, at least 1;
  - a share button: `navigator.share` where the phone has it, else three buttons (WhatsApp, X, copy the link).
- **Clubs and players:** a strip, scrolling sideways, with one chip for each club and player in the article's `entities`.
  - Each chip has the logo or player photo and the Arabic name, and links to its Tifo page.
  - Each has a «تابع» button that opens the existing follow sheet (the same subscription as the club and player pages).
- **The text:**
  - paragraphs at 17 px, line height 1.85;
  - subheads at 19 px;
  - «حقائق سريعة» as a v5 card;
  - the caption under the photo at 13 px.
- **Goal videos (match reports):** after the standfirst, one player per goal (§6), `preload="none"` with a poster. None when a
  report has no video yet.
- **At the end:**
  - «ذات صلة»: a grid of four photo cards that share a club, player or match with the article, newest first;
  - «الأكثر قراءة»: five lines;
  - the trust links (كيف نكتب · سياسة التصحيح · من نحن) as today.
- **Unchanged:** `NewsArticle` structured data, `og:image` at 1200×675, `max-image-preview:large`, the canonical URL and the
  news sitemap.

## 3. The home page

A «مقالات تيفو» block at the top of the home page:
- one large card (as §1's lead) and three small ones, then «كل المقالات» to `/news/`;
- the static build writes the block as it stands;
- the page then reads `v1/news/articles.json` (cache 20 s) and redraws it, so the block is never an hour old.

## 4. Notifications

- A new kind, `article`, for club subscriptions (`TIFOPUSH#<team>`) and player subscriptions (`TIFOPUSH#P<id>`). It is on
  by default, like `start`/`goal`/`end`, and appears in the notification settings as «مقالات».
- **When:** an article is published for the first time. A rewrite or an update does not notify again. Each club and player in
  its `entities` gets one push: the headline as the title, the standfirst cut to 120 characters as the body, and the article's
  page as the link.
- **Limits:**
  - at most 3 article pushes a day per club or player;
  - the existing quiet hours apply;
  - «عاجل» goes at once;
  - the push leaves only once the page is up (§7).
- **The sender** is the existing one (`push.py`'s jobs). It claims each push once (`TIFOPUSHSENT#article:<id>`) so no follower
  gets it twice.

## 5. «الأكثر قراءة»

- The existing visit counter (`/api/tifo/hit`, the cards stack) also counts one hit per visit to `/news/<id>/`, under the UAE
  day: `TIFOHIT#<day>`, sort key `ART#<id>`.
- The fast build (§7) reads the day's counts and writes `v1/news/top.json`: the 10 most read articles of the last 24 hours,
  each with its id, headline, photo and count.
- Pages read that file in the page. Before the first count it is empty, and the list is not shown.

## 6. Goal videos in the match report

- The goal watcher (`content/social/tifo/goal_watch.py`) already renders each goal to `state/goals/<dir>/goal.mp4`. It also
  writes a public copy at `v1/goals/<match>/<n>.mp4`, at 720 px on its long side and around 2-4 MB, plus a poster at
  `v1/goals/<match>/<n>.jpg`. It lists them in `v1/goals/<match>.json`:
  `{match, goals: [{n, minute, scorer_ar, mp4, poster}]}`.
- The report page reads that file in the page, so a goal rendered after the report still shows. Each goal is a `<video>`
  with controls, the minute and the scorer.

## 7. Within a minute

- **A new workflow step**, «Article pages», runs after «Tifo articles» in the journal workflow:
  - it builds only the article pages written or changed in this run, `/news/`, `/news/press/` and `sitemap-news.xml`;
  - it uploads them to the site's bucket with the full build's headers, and invalidates exactly those paths on CloudFront.
- **The hourly full build** stays as it is and builds everything. If the fast step fails, the full build catches up within
  the hour, and the failure is in the step's log.
- **The X poster and the notifications** wait for a page that answers 200, as they do now; with this step that is about a
  minute.
- **How:** the fast build uses `site/build.cjs`'s own page shell, so the two builds can never look different. Either
  `build.cjs` runs in its existing `TIFO_ONLY` mode limited to the news pages, if that is fast enough on the runner (under
  90 s), or the shell moves into `site/lib/shell.cjs`, which both builds use. The plan measures and chooses.

## Order

1. **Part A:** the article page, the news page and its tabs, the home block, and the fast step (§1, §2, §3, §7). The doc
   gains `topic`.
2. **Part B:** notifications (§4).
3. **Part C:** «الأكثر قراءة» (§5).
4. **Part D:** the goal videos (§6).

Each part has its own plan, its tests, and a check on a phone width against the live data before it ships.

## Not in scope

- Tifo data cards in the article.
- Articles on club, player, match or competition pages beyond what exists today.
- A «عاجل» bar across the site.
- Comments.

## Testing

- Node tests (`site/lib/articles.test.cjs`) for:
  - the article page HTML: head, chips, share, reading time, related, the video slot;
  - the news page: tabs, lead, grid, filters, 30 and «المزيد»;
  - the home block.
- Python tests for:
  - `topic` in the doc;
  - the fast step's list of changed pages;
  - the article push (first publish only, 3 a day, claimed once);
  - `top.json`;
  - the goal video list.
- Each part is checked in the browser at 375 px against the live data before it ships.
