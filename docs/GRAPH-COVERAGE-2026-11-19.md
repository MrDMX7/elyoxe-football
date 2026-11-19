# Tifo graph — first build, 2026-11-19

Phase 1 of `docs/superpowers/specs/2026-11-19-tifo-graph-design.md`, built on GitHub Actions from the nightly caches (dry run, 8 min). The full per-edition report is written by every build (`v1/graph/coverage.json`, `docs/GRAPH-COVERAGE-<date>.md` on the runner).

## Totals

| table | rows | by source |
|---|---|---|
| team | 27,615 | fotmob 8,547, martj42 127, rsssf 662, s365 1,695, sch 7,854, tm 8,730 |
| player | 106,508 | fotmob 106,508 |
| coach | 6,998 | fotmob 3, tm 6,995 |
| referee | 1,719 | fotmob 1,719 |
| stadium | 2,232 | fotmob 2,232 |
| competition | 1,341 | fotmob 282, martj42 208, rsssf 3, s365 581, sch 200, tm 67 |
| edition | 28,873 | fotmob 782, martj42 1,876, rsssf 189, s365 19,415, sch 6,057, tm 554 |
| match | 1,432,039 | fotmob 93,135, martj42 47,843, rsssf 18, s365 1,524, sch 1,232,599, tm 56,920 |
| appearance | 2,776,588 |  |
| event | 979,017 |  |
| standing | 7,051 |  |
| honour | 19,896 |  |
| transfer | 13,162 |  |
| spell | 409,485 |  |
| player_season | 542,562 |  |
| injury | 69,150 |  |
| match_coach | 176,228 |  |

## One match, many sources

Transfermarkt games found as FotMob's own match (2012+): Premier League 5,320 / 5,320 · LaLiga 5,320 / 5,320 · Serie A 5,317 / 5,320 · Ligue 1 4,995 / 4,997 · Bundesliga 4,283 / 4,284 · Champions League 1,763 / 1,871 · Europa League 1,956 / 2,628. The other Transfermarkt leagues (Netherlands, Portugal, Turkey, Belgium…) are not in FotMob's archive, so their games are new matches.

## Main competitions after linking

| competition | seasons | editions | matches | with lineups | champions | final tables |
|---|---|---|---|---|---|---|
| دوري أدنوك للمحترفين | 1973/1974 – 2026/2027 | 53 | 4,103 | 1,998 | 52 | 40 |
| كأس رئيس الدولة | 1974/1975 – 2026/2027 | 51 | 137 | 113 | 49 | 0 |
| دوري روشن السعودي | 1974/1975 – 2026/2027 | 53 | 5,019 | 2,855 | 52 | 37 |
| الدوري الإنجليزي الممتاز | 1888/1889 – 2026/2027 | 128 | 51,435 | 6,069 | 127 | 0 |
| كأس العالم | 1930 – 2026 | 23 | 748 | 104 | 23 | 0 |
| دوري أبطال آسيا للنخبة | 1967 – 2026 | 44 | 1,750 | 1,516 | 43 | 0 |
| كأس الخليج العربي | 1970 – خليجي 9 | 56 | 425 | 15 | 27 | 0 |
| كأس آسيا | 1956 – 2024 | 19 | 421 | 0 | 18 | 0 |

## Arabic names and birth dates

Teams 8,480 of 27,615; players 18,193 of 106,508; competitions 642 of 1,341. Players with a birth date: 66,667 of 106,508.

## Gaps this build shows (the order for phases 2–5)

- **Awards and per-edition honours beyond the champion:** none yet (phase 2).
- **Man of the match:** ratings exist for the stored lineups, the pick is not derived yet (phase 3).
- **World Cup before 2026 in detail:** 1930–2022 are results only (martj42); lineups, goals and awards come with Fjelstul (phase 4).
- **UAE league before 2014 in detail:** tables and champions since 1973/74, matches since 2014 (phase 4).
- **Coaches:** 3 FotMob coach profiles; 6,995 Transfermarkt managers by name, not yet linked (phase 5).
- **Runner-up:** not yet recorded for any edition (phase 2).

## Conflicts between sources

| type | field | kept | other | n |
|---|---|---|---|---|
| match | score | fotmob | sch | 57 |
| match | score | fotmob | tm | 55 |
| match | hs | sch | sch | 51 |
| match | as_ | sch | sch | 47 |
| player | born | fotmob | tm | 26 |
| match | score | tm | sch | 15 |
| match | score | tm | martj42 | 13 |
| match | score | fotmob | martj42 | 6 |
| match | as_ | martj42 | martj42 | 1 |
| match | hs | martj42 | martj42 | 1 |
