# Tifo archive — progress ledger (the owner, 22 Nov 2026: «هالمرة اريد تكون الاخيرة… ما نرجع للخلف»)

Spec: docs/superpowers/specs/2026-11-22-tifo-archive-static-design.md. Static pages (owner's choice). Each line: done / open,
with the commit or the evidence. A new session reads this first and continues at the first open line.

## Data
- [x] England: four tiers since 1888, test matches, FA Cup 1871-, League Cup 1960-, Community Shield 1908- (6c603c7, c2279ce): Liverpool–Man Utd 218 = Gemini.
- [x] Final tables computed from matches for league seasons without standings (00a0b0c): 491+ seasons, withheld when the first is not the champion.
- [x] UAE source map: research/uae-league-history-sources-2026-11-22.md — the UAE FA's JSON API (uaefa.ae/api: match_report, match_highlights2) has line-ups, goals, subs, cards, referees, venues for every top-flight match 2003/04–2014/15; ids from uaepl.ae fixture XHRs (2008/09–) and an id scan (14000–23840) for 2003/04–2007/08. Before 2003/04: RSSSF only (+Soccerway 2000/01–2002/03 results).
- [x] Seasons pass graph/load/seasons.py (9bb6186, live 22 Nov 15:52): one season one edition — 493 merged, 214 relabelled, 133 detached (Fairs Cup, Chile's league under Sudamericana), 63k games re-filed by FotMob's spans/calendar years, 22k strays aside (other divisions, a club's second record), 859 copies joined.
- [x] A season's tournaments fold into its row (d14be85: Apertura/Clausura, Metropolitano/Nacional) — live with the next graph build.
- [x] UAE FA loader graph/load/uaefa.py + fetcher graph/uaefa_fetch.py (1a9652e): ids 2008/09–2016/17 from uaepl (1,438), scan 2003/04–2007/08 (80/182/132/132/132).
- [x] UAE FA data live (graph build 16:47 UTC): 2,096 games 2003/04–2016/17; every UAE season 2003/04–2014/15 with line-ups, goals, referee; 631 men tied to FotMob's (9fb26fd).
- [x] Argentina's top scorer per tournament since 1891 from RSSSF (e45a17a, next graph build): 223 of 226 rows land; shown in the season's parts.
- [x] Transfermarkt's whole transfer history, 1.1M moves (eabeab7, weekly tmdata stage); reaches pages with phase 2 (profiles).
- [ ] ESPN 2001–2010 (graph/espn_fetch.py on the laptop → state/graph/espn.json → graph build): big five + UCL, AFC CL 2006–09, AFCON 2004–10, Asian Cup 2007. England fetched: 380 games a season with squads.
- [ ] RSSSF/Wikipedia gaps 1973–2003 (tables 1975/76–1982/83).
- [x] Top scorers from the leagues' own lists (1f4b2aa): England 1888/89–, Pichichi, Capocannoniere, Ligue 1, Torjägerkanone, Brazil, Libertadores; ties split per break; junk names («24th title», «(2)») out (9b7ad4d). Argentina waits for a label map («1891 (Amateur)»).
- [ ] Other Arab leagues' gaps, same method.
- [ ] Line-ups/scorers/cards/referees before 2010 for the big leagues: sources to weigh.
- [ ] Photos (Wikidata/Commons) for players, coaches, referees, grounds.

## QA (site/qa/site_qa.cjs, phone width)
- [x] Round 1 (202 pages): countdown, Messi museum, developers table, empty line-up card fixed (6495a27); seasons list one row a season (954dec5).
- [x] Round 2 (309 pages, 14 defects): pre-merge season pages (replaced by the archive run), countdown CSS clash, encyclopedia photo width, Messi tables, browser-drawn links → 404 forwards to the encyclopedia (bf5f611).
- [ ] Round 3 over the whole site after the next site build (the 404 forward and CSS fixes live).

## Pages (archive job)
- [ ] Shared module: the site's season and match page code out of build.cjs (lib/archive_pages.cjs), used by both.
- [ ] Site build saves archive shells (state/site/shells.json) with placeholders.
- [x] Archive job tools/archive_job.py: DB from S3 -> graph/archive_export -> site/archive/build.cjs (thin pages noindex, out of sitemaps) -> upload changed by md5 manifest (state/archive/manifest.json) -> sitemap-archive*.xml -> IndexNow.
- [x] Workflow .github/workflows/tifo-archive.yml (after «Tifo database», or dispatch; skips when the DB is unchanged).
- [x] Site: ARCHIVE_OWNED excludes (c/*/s/*, c/*/seasons/*, m/k*, sitemap-archive*) and a listing that never reads m/k*; robots names the search and AI crawlers and lists sitemap-archive.xml; llms.txt.
- Ruling: the archive owns season pages, season lists and archive matches only (p/k, t/k, coach, r stay with the site until phase 2/3) — the site still writes p/k pages hourly, so listing them must stay — cost if wrong: none, ownership moves later.
- [x] Renderer site/archive/build.cjs + export graph/archive_export.py: Premier League locally = 128 seasons, 51,778 match pages (51,907 pages), shell from the site build.
- [x] Seasons + matches live for all 61 competitions (run 45045946013, 22 Nov 16:49–18:01 UTC): 354,179 pages (2,354 seasons, 351,761 matches), 301,725 sent, IndexNow 10,000. QA of 31 seasons pages: 0 defects; no duplicate seasons in Bundesliga/Libertadores/Argentina/Sudamericana/LaLiga.
- [ ] Players (223k), clubs, coaches, referees, stadiums.

## Indexing
- [ ] Sitemap index (50k per file) incl. the archive; robots.txt lists it.
- [ ] IndexNow for archive URLs (new/changed, daily).
- [ ] llms.txt; robots.txt names the AI crawlers explicitly.
- [ ] JSON-LD per page kind (SportsEvent, Person, SportsTeam, BreadcrumbList) checked.

## Costs (estimate given to the owner 22 Nov)
~$12 once (2.5M PUTs), then ~$3–8/month (storage gz, nightly changes); CloudFront free tier covers crawling; Actions free.
