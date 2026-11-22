# Tifo archive — progress ledger (the owner, 22 Nov 2026: «هالمرة اريد تكون الاخيرة… ما نرجع للخلف»)

Spec: docs/superpowers/specs/2026-11-22-tifo-archive-static-design.md. Static pages (owner's choice). Each line: done / open,
with the commit or the evidence. A new session reads this first and continues at the first open line.

## Data
- [x] England: four tiers since 1888, test matches, FA Cup 1871-, League Cup 1960-, Community Shield 1908- (6c603c7, c2279ce): Liverpool–Man Utd 218 = Gemini.
- [x] Final tables computed from matches for league seasons without standings (00a0b0c): 491+ seasons, withheld when the first is not the champion.
- [x] UAE source map: research/uae-league-history-sources-2026-11-22.md — the UAE FA's JSON API (uaefa.ae/api: match_report, match_highlights2) has line-ups, goals, subs, cards, referees, venues for every top-flight match 2003/04–2014/15; ids from uaepl.ae fixture XHRs (2008/09–) and an id scan (14000–23840) for 2003/04–2007/08. Before 2003/04: RSSSF only (+Soccerway 2000/01–2002/03 results).
- [ ] UAE FA API fetch stage + graph loader (2003/04–2014/15), then RSSSF/Wikipedia gaps 1973–2003.
- [x] Top scorers from the leagues' own lists (1f4b2aa): England 1888/89–, Pichichi, Capocannoniere, Ligue 1, Torjägerkanone, Brazil, Libertadores; ties split per break; junk names («24th title», «(2)») out (9b7ad4d). Argentina waits for a label map («1891 (Amateur)»).
- [ ] Other Arab leagues' gaps, same method.
- [ ] Line-ups/scorers/cards/referees before 2010 for the big leagues: sources to weigh.
- [ ] Photos (Wikidata/Commons) for players, coaches, referees, grounds.

## QA (site/qa/site_qa.cjs, phone width)
- [x] Round 1 (202 pages): countdown, Messi museum, developers table, empty line-up card fixed (6495a27); seasons list one row a season (954dec5).
- [ ] Round 2 after the fixes deploy, more pages a kind; client-side links to unbuilt matches (/commentators/).

## Pages (archive job)
- [ ] Shared module: the site's season and match page code out of build.cjs (lib/archive_pages.cjs), used by both.
- [ ] Site build saves archive shells (state/site/shells.json) with placeholders.
- [ ] Archive job: export (python, from tifo.db) -> render (node) -> upload changed (manifest in state) -> sitemaps.
- [ ] Workflow tifo-archive.yml after each published graph build.
- [ ] Site push: exclude archive-owned paths (c/*/s/*, c/*/seasons/*, m/k*, p/k*, t/k*) and list only its own prefixes.
- [x] Renderer site/archive/build.cjs + export graph/archive_export.py: Premier League locally = 128 seasons, 51,778 match pages (51,907 pages), shell from the site build.
- [ ] Seasons + matches: Premier League live, then every competition.
- [ ] Players (223k), clubs, coaches, referees, stadiums.

## Indexing
- [ ] Sitemap index (50k per file) incl. the archive; robots.txt lists it.
- [ ] IndexNow for archive URLs (new/changed, daily).
- [ ] llms.txt; robots.txt names the AI crawlers explicitly.
- [ ] JSON-LD per page kind (SportsEvent, Person, SportsTeam, BreadcrumbList) checked.

## Costs (estimate given to the owner 22 Nov)
~$12 once (2.5M PUTs), then ~$3–8/month (storage gz, nightly changes); CloudFront free tier covers crawling; Actions free.
