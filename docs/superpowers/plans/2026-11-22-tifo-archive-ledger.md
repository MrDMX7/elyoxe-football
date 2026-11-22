# Tifo archive — progress ledger (the owner, 22 Nov 2026: «هالمرة اريد تكون الاخيرة… ما نرجع للخلف»)

Spec: docs/superpowers/specs/2026-11-22-tifo-archive-static-design.md. Static pages (owner's choice). Each line: done / open,
with the commit or the evidence. A new session reads this first and continues at the first open line.

## Data
- [x] England: four tiers since 1888, test matches, FA Cup 1871-, League Cup 1960-, Community Shield 1908- (6c603c7, c2279ce): Liverpool–Man Utd 218 = Gemini.
- [x] Final tables computed from matches for league seasons without standings (00a0b0c): 491+ seasons, withheld when the first is not the champion.
- [ ] UAE league 1973/74– complete: source map (research/uae-league-history-sources-2026-11-22.md), then loaders season by season.
- [ ] Other Arab leagues' gaps, same method.
- [ ] Line-ups/scorers/cards/referees before 2010 for the big leagues: sources to weigh.
- [ ] Photos (Wikidata/Commons) for players, coaches, referees, grounds.

## Pages (archive job)
- [ ] Shared module: the site's season and match page code out of build.cjs (lib/archive_pages.cjs), used by both.
- [ ] Site build saves archive shells (state/site/shells.json) with placeholders.
- [ ] Archive job: export (python, from tifo.db) -> render (node) -> upload changed (manifest in state) -> sitemaps.
- [ ] Workflow tifo-archive.yml after each published graph build.
- [ ] Site push: exclude archive-owned paths (c/*/s/*, c/*/seasons/*, m/k*, p/k*, t/k*) and list only its own prefixes.
- [ ] Seasons + matches: Premier League first, then every competition.
- [ ] Players (223k), clubs, coaches, referees, stadiums.

## Indexing
- [ ] Sitemap index (50k per file) incl. the archive; robots.txt lists it.
- [ ] IndexNow for archive URLs (new/changed, daily).
- [ ] llms.txt; robots.txt names the AI crawlers explicitly.
- [ ] JSON-LD per page kind (SportsEvent, Person, SportsTeam, BreadcrumbList) checked.

## Costs (estimate given to the owner 22 Nov)
~$12 once (2.5M PUTs), then ~$3–8/month (storage gz, nightly changes); CloudFront free tier covers crawling; Actions free.
