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
- [x] Players: a profile for every man with a record, 121k (ceb3c6d): facts, honours, every season (Transfermarkt), archive games, transfers, injuries, caps; Person JSON-LD; thin = noindex; the site's page wins where it has one.
- [x] Referees of 5+ games (1,256) and old clubs of 30+ games (6,964) (118ef80); matches link both.
- [x] Photos for the archive men (a173607, e283f9c): v1/people/qids.json (26k) → photos.build --archive (Wikidata/Commons, QLever fallback) → v1/ph/k<id>.webp; weekly stage photos_archive.
- [x] UAE copies in complete round robins (0e6e685): 2006/07–2010/11 exactly 132.
- [x] Coaches (b63ad90): /coach/k<id>/ for every coach with a bench or an award the site has no /coach/<FotMob id>/ for (≈7k), indexed at 30 games or an award; old matches name both coaches in their info, linked; season pages link them. Ruling: thin coach pages are written (noindex) rather than skipped — a match links its coach — cost if wrong: ~5k thin pages.
- [ ] Stadium pages.

## 23 Nov incidents and fixes
- 35,296 profiles lost: the 01:25 site publish (0e6e685, before p/k* was the archive's) listed the bucket while the archive was uploading them; s3push held its deletes (over 10 %), returned ok=False, and the CLI fallback (`sync --delete`, no guard) deleted them. Fixes (ed286d4): held deletes return ok, the fallback only uploads, the archive re-sends pages its manifest holds but the bucket lost (still_up). Forced archive run 45107983786 restores them.
- The site's own count fell 77,035 → 67,098 when p/k* became the archive's; the 95 % guard refused builds 02:25–04:00 (875c4bd: a change of ARCHIVE_OWNED resets the baseline).
- QA round 4 (120 profile/referee/club pages): 8 lost profiles (404); referee and club last-games rows nested club links in the row link; every archive page had two footers (f0de893).
- Awards (5d1f8f6): no other sports (Gatorade high-school awards), a section award with no Arabic page name keeps its English name, La Liga Player of the Month's Arabic. Ruling: women's football and futsal awards stay (117 award pages on /awards/) — the owner decides scope — cost if wrong: profiles of women say «مسيرته».
- Site sitemap leaves out the archive's paths (fec0b9c): it listed 11,801 old matches, 1,946 seasons, 3,957 profiles.
- photos --archive checkpoints every 250 and resumes «pending» men (0c397a5).
- Archive sweep (3331ba1): after its upload the job deletes keys under ARCHIVE_OWNED its manifest does not hold (20,270 stale old-match copies from the site's 22 Nov publish), held over 10 %.
- Coach photos (1309683): people/qids.json lists coaches as c<id>, the photo stage accepts «association football manager» for them, a coach page shows v1/ph/c<id>.webp or his player photo. The graph had no coach Wikidata ties at all: the awards loader now records them and sets coach.pid by the same item (5d1d539) — live after the next graph build.
- Nationalities in Arabic (bae99eb): a FotMob code reads as the senior national team its men played for (99.9 % of 68,774 players), English names via the national teams plus aliases and gone states.
- Career competitions in Arabic (99c5926): 61 % of 1.29M lines (code-named competitions «FAC» gave way to the line's name; graph/tm_comps_ar.yaml for 135 common unambiguous names). Ruling: names several countries use («Premier League», «Super League») stay in English — cost if wrong: ~40 % of lines English.
- Facts are card rows on profiles and coach pages (3ec4294): the bare list spilled out of its card. Referee pages carry a Person (ec36382).
- Gulf Cup top scorers (1c9ce61): its English article added to comp_pages (27 editions; it had 8 of 56 seasons). Arab Cup and old Euros still lack per-edition scorers (no table: Euro pages list scorers as bullets).
- Profiles restored: 107,007 of 107,007 p/k in S3 (run 45107983786); every archive page one footer.
- Coaches live (run 45114942854): 8,110 coach pages (2,089 indexed), 157,273 pages changed, 21,023 stale pages swept; the 1986 final names Bilardo and Beckenbauer, linked. Site links every coach (1252909); a coach with a site page gets a /coach/k<id>/ pointer to it.
- Photos: 11,000 archive men and 585 coaches (the background limit stopped the batch once; checkpoints kept it).
- Gulf Cup as 27 editions (e5b1ad6): national teams' tournaments are runs of games; «خليجي N» is the Nth; 60-day guard leaves friendlies, qualifiers, Copa América alone (only the Gulf Cup changes).
- QA round 5 (104 coach, profile, referee pages): 0 defects.

## Indexing
- [ ] Sitemap index (50k per file) incl. the archive; robots.txt lists it.
- [ ] IndexNow for archive URLs (new/changed, daily).
- [ ] llms.txt; robots.txt names the AI crawlers explicitly.
- [ ] JSON-LD per page kind (SportsEvent, Person, SportsTeam, BreadcrumbList) checked.

## Costs (estimate given to the owner 22 Nov)
~$12 once (2.5M PUTs), then ~$3–8/month (storage gz, nightly changes); CloudFront free tier covers crawling; Actions free.

## 23 Nov (afternoon): «نحل جميع مشاكل عدم التكامل + التخبيص»
- tools/integrity.py: every page kind sampled from the sitemaps, every internal link followed; broken / old (encyclopedia
  where a page exists) / twin / Latin share with the strings that come back most. First run: 222,168 pages, 720 sampled,
  0 broken links; «Pro League (aside)» ×67 on h2h pages; countries as «gibraltar»; transfers 91 % Latin, old clubs 69 %, profiles 50 %.
- Men's football only (6182ccb, graph/load/mens.py): 174 competitions, 2,120 honours, 722 players out.
- Honours only in our competitions (acfed8f): Transfermarkt-code «CL» crowned Messi; «بطل FAC» beside the FA Cup.
- One page per match (1fe7a09, 19e6fbd): FotMob matches the site has no page for -> /m/k<id>/ (v1/archive/fm2k + shards; site
  link check, the card, the 404); attendance and FotMob ratings on old match pages.
- One page per man (dd21ecc, 66eadd7, 7c87d0c): v1/archive/fm2p; the profile carries the encyclopedia's club, position, shirt,
  value, contract and this season; /db/player/<id>/ points to /p/k<id>/ (noindex, canonical); the card's bio as rows (bff69e8).
- Aside games dropped after counting (c8ded57); countries case-insensitive.
- Arabic names: 10,190 Transfermarkt clubs (names/tm_clubs.py, 3997f35); 592 code-named competitions (names/comps.py, e85f226);
  the archive's men in bulk (names/people_bulk.py, running: 104,776); «ddr» split into the Soviet, Yugoslav, East German leagues,
  the Cup Winners' Cup and the old Intercontinental (league_of).
- Scorers: tournament goalscorer lists read (efe7044: Euro 1960, 1964); Arab Cup and Gulf Cup articles by hand (c69e081, next
  awards stage); seasons lists link scorers (fcef8fe).
- Ruling: the encyclopedia's club pages (/db/club, FotMob clubs outside the site's competitions) stay: they duplicate nothing
  (the archive's /t/k are clubs FotMob has no id for) — cost if wrong: two designs for club pages.
