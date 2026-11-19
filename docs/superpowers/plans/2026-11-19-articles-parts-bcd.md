# Articles parts B, C, D Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (the owner's method for this spec's parts). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** the article push to club and player followers (B), «الأكثر قراءة» (C), and the goal videos in match reports (D).

**Architecture:** B adds a push kind `article` end to end: the site's settings (notify.js), the cards API that stores the
choice, the sender (push.py run_jobs) with a per-club/player cap, and the job builder in the fast «Article pages» step, which
hands the jobs over only after the pages are uploaded. C counts article visits in the existing hit counter and has the fast
step write `v1/news/top.json`, which the pages read in the page. D has the goal runner publish a small public copy of each
rendered goal and a per-match list, which the report page reads in the page.

**Tech Stack:** Python 3.13 (pytest), Node 24 (node:test), DynamoDB `cards`, Lambda (`elyoxe-football-push` arm64, the cards
API), S3 data bucket `v1/`, GitHub Actions (journal, goals).

**Spec:** `docs/superpowers/specs/2026-11-19-articles-pages-design.md` §4, §5, §6.

## Global Constraints

- The push claim is `TIFOPUSHSENT#article:<id>` (job `match` = `article:<id>`, `key` = `article`): once per article, ever.
- At most 3 article pushes a day per club or player (UAE day); quiet hours apply; «عاجل» is `urgency: high`.
- A push leaves only after its page is uploaded, only for an article first published in the last 3 hours, at most 20 a run.
- `article` is on by default: a subscription saved before the switch existed (no `art` flag) gets articles when it gets goals.
- «بدون حرق» drops `article` (a match report gives the score away).
- `top.json`: the 10 most read of the last 24 hours = today's counts + yesterday's × the share of yesterday inside the 24 hours.
- Goal copy: `v1/goals/<match>/<goal dir>.mp4` at 720 px on the long side, poster `.jpg`, list `v1/goals/<match>.json`
  `{match, goals: [{n, minute, scorer_ar, mp4, poster}]}` in minute order.
- Western digits; Arabic copy plain (no slogans); never deploy the poller for this: only the sender's two files and the cards API's `app.py`.

## Review Focus

1. The first fast-step run after deploy, or one with an empty pages state: must not push a backlog of old articles.
2. A subscription saved by the old settings page (events without `article`, no `art`): gets articles only if it has `goal`.
3. A visitor who unticks «مقالات» on the new page: `art` flag stored, `article` absent, never pushed again — even on resync.
4. A report with 25 players: one push per device (team and player audiences deduplicated), each audience capped at 3 a day.
5. `top.json` and the goal list absent or empty: the pages show nothing and throw nothing.

---

### Task B1: the sender knows `article`

**Files:** Modify `push.py` (TEAM_EVENTS, JOB_TTL, wants, run_jobs), `pushplayer.py` (KINDS). Test `tests/test_push_article.py`.

- [ ] Tests: `wants` for old/new subscriptions; run_jobs sends an article job once (claim), skips quiet subs, caps an audience
  after 3 article jobs in a UAE day (`cap_ok(table, "art:<audience>", day, cap=3)`), dedupes a device across team+player.
- [ ] Implement; full suite green; commit.

### Task B2: the job builder in the fast step

**Files:** Create `news/articles/push_jobs.py` (`jobs(docs, known, now)`), modify `news/articles/pages.py` (run → returns
the new docs; main invokes). Test `tests/test_articles_push_jobs.py`.

- [ ] Tests: first-time ids only, published ≤ 3 h, no jobs when `known` is empty, ≤ 20, payload title/body(120)/url/tag,
  audiences `"<team>"` and `"P<pid>"`, breaking → high.
- [ ] Implement; `pages.run(..., push=fn)` calls it after the upload, errors logged not raised; commit.

### Task B3: the cards API stores the choice

**Files:** `saas/cards/src/app.py` (TIFOPUSH_EVENTS, TIFOPUSH_PEVENTS, defaults, `art` flag). Test `saas/cards/tests/test_tifo_api.py`.

### Task B4: the settings page

**Files:** `site/src/notify.js` (switch «مقالات تيفو», player group «من تيفو», PDEF, `art: 1`, nospoil, one-time migration).
Test `site/src/notify.test.cjs` (or the existing notify test).

### Task C1: article visits counted

**Files:** `saas/cards/src/app.py` tifo_hit: `/news/<id>/` → `ART#<id>`. Test in `test_tifo_api.py`.

### Task C2: `top.json`

**Files:** Create `news/articles/top.py` (`rank(today, yday, frac, lst, n=10)`, `counts(table, day)`, `main`), run from the
workflow's «Article pages» step after pages. Test `tests/test_articles_top.py`.

### Task C3: «الأكثر قراءة» on the pages

**Files:** `site/lib/articles.cjs` (slot `.atop` in the article end and after the 6th card, the CLIENT fills it), `articles.css`.
Test `site/lib/articles.test.cjs`.

### Task D1: the public goal copy

**Files:** workspace `content/social/tifo/goal_watch.py` (`public_copy(c, out)` from `upload`, `goals_index(prev, entry)`).
Test workspace `content/social/tifo/tests/test_goal_public.py`.

### Task D2: the goals in the report page

**Files:** `site/lib/articles.cjs` (slot `.agoals[data-match]` after the standfirst of a report; the CLIENT fills it),
`articles.css`. Test `site/lib/articles.test.cjs`.

### Ship

- Final review (one fresh reviewer), fixes test-first; merge; push (deploys the site and the workflow).
- Deploy: the sender's `push.py` + `pushplayer.py` into the live zip; the cards API's `app.py` into its live zip (each diffed
  against what is live first). The goal runner gets the new goal_watch.py from the laptop's kit.
- Check at 375 px against live data: the settings switch, `top.json` and its list, a report with a goal video.
