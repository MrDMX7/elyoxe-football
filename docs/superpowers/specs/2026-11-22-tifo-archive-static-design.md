# Tifo's whole archive as static pages (2026-11-22)

Owner, 22 Nov 2026: «اريد الداتا بيس كامل… لما اضغط عالموسم اللي اباه يطلعلي كل شي كانه الموسم الحالي… بروفايلات لكل
اللاعبين… كل المواسم، كل المباريات، كل المدربين، كل الكروت، كل الحكام كلهم بصورهم». Asked how the millions of pages are made,
he chose **static pages built ahead** («عشان تنتشر فقوقل… وما تتأخر على الزاير»).

## What the review found (22 Nov, graph build 13:19 UTC)

| | in the database | pages on the site |
|---|---|---|
| matches | 1,647,342 | ~39k (28k FotMob + 11k archive) |
| players | 222,858 | ~21k (17k FotMob + 3.8k archive) |
| clubs | 34,374 | 901 |
| coaches | 14,003 | 2,198 |
| referees | 2,119 | 236 |
| season pages | 50,062 editions | 1,505 (only the UAE and some tournaments show table and matches) |

- Every page type already wears the v5 design (`data-v5`).
- Premier League 2015/16, every European season, the Champions League: honours only, no table, no matches, though the DB
  holds every match in detail.
- Profiles: an old player's page shows honours only; a current one (Messi) has no season-by-season career, transfers or
  injuries although `player_season` (1.29M), `transfer` (15k) and `injury` (149k) hold them.
- Detail by decade: line-ups, scorers, cards and referees are almost all 2010 on (2000s: 9k of 309k matches have scorers).
  Earlier decades are results, tables, champions and top scorers. Filling them is a separate data track (phase 5).

## Design

**A separate job owns the archive.** `.github/workflows/tifo-archive.yml` (public repo: free minutes) runs after each
published graph build (and on dispatch):

1. Takes `graph/tifo.db.gz` (private S3) and the site's shells (`state/site/shells.json`).
2. `node site/archive/build.cjs` reads the DB with `node:sqlite` and renders pages with the site's own v5 code
   (`src/v5/pages.js`, `ui.js`, `lib/season_view.cjs`, `lib/match_view.cjs`) into a work folder, a batch at a time.
3. Uploads only pages whose bytes changed: a manifest of page hashes kept in S3 state (`state/archive/manifest.json.gz`),
   boto3 many at a time (the owner's fast-upload rule). The first run is the heavy one (~2.5M pages, ~$12 of PUTs once);
   later runs touch what changed.
4. Writes `sitemap-archive-<n>.xml` (50k URLs each) and their index, listed in robots.txt.

**Shells, not a copy of `page()`.** The site build already saves its article shell to state; it now also saves an
`archive` shell per page kind (comp, match, player, team, person) with placeholders (`__TITLE__`, `__DESC__`, `__PATH__`,
`__BODY__`, `__LD__`, `__DATA__`). Archive pages therefore always carry the site's current head, nav, footer and hashed
assets (old hashed assets stay in S3: the asset sync never deletes).

**Who owns which URL.** The archive job owns every season page `/c/<key>/s/<season>/`, every archive match `/m/k<id>/`,
every archive person `/p/k<id>/`, `/coach/<id>/` and `/r/<id>/` it writes, and the club pages `/t/k<id>/`. The site build stops
writing those and excludes them from its `--delete` (runner `PAGE_EXCLUDES`); it learns which archive URLs exist from
`v1/archive/index.json` so its dead-link pass keeps the links. A FotMob match the site already renders (`/m/<FotMob id>/`)
is linked to from the archive, never rendered twice; an archive match that is a FotMob one carries the FotMob page as canonical.

**Competition URLs.** A competition the site follows keeps its key (`/c/premier-league/`). Any other gets
`/c/<slug>-<FotMob id or k<Tifo id>>/` from its English name, and a minimal competition page listing its seasons.

## Phases (in order; each verified live before the next)

0. Foundation: shells saved by the site build, the renderer's frame, the manifest uploader, the workflow, sitemaps,
   the site's excludes and archive index.
1. Every competition's every season as it shows today (table, rounds/months, scorers, honours) and every match page —
   the Premier League first (128 seasons) to check, then all.
2. Every player's profile: season-by-season career (`player_season`, `spell`), matches, goals, cards, honours,
   transfers, injuries, caps; the site's FotMob player pages gain the same sections.
3. Every club, coach, referee and stadium.
4. Photos: Wikidata/Commons images for players, coaches, referees and grounds (licence shown on the page).
5. Data depth before 2010 (line-ups, scorers, cards, referees): sources to be weighed with the owner.
