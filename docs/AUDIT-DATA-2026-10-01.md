# Tifo data audit — 2026-10-01

Generated 2026-10-01T00:30:02Z by `python -m db.audit` in 240 s (freshness 6 s, matches 155 s, standings 21 s, scorers 31 s, derived 18 s, champions 5 s, identity 4 s, gaps 0 s); 168 FotMob requests (0 failed), 46 365Scores requests (errors: none), 6189 published files read. Window: the last 14 days; sample 60.

Verdicts: **ours** = our code is wrong · **stale** = the source moved on and our copy didn't · **gap** = missing, fillable · **source** = the sources disagree (`favors` = which one the evidence supports) · **unknown**.

## Summary

| area | checked | errors | warnings | info |
|---|---|---|---|---|
| champions | 8696 | 11 | 5 | 0 |
| derived | 182619 | 2 | 2 | 0 |
| freshness | 91 | 0 | 0 | 0 |
| gaps | 21637 | 0 | 1 | 15 |
| identity | 136171 | 0 | 1 | 1 |
| matches | 13404 | 0 | 2 | 0 |
| scorers | 1645 | 0 | 8 | 0 |
| standings | 5394 | 0 | 8 | 0 |

## matches

### file_goals_missing — 1 (warn, stale)
- Thailand v Kuwait (114, 2026-06-05): the page names 0+0 scorers for a 2-2 score (coverage ratings) (/m/5737468/)
### finished_without_page — 1 (warn, gap)
- كأس العرش المغربي (11840): 2 finished matches have no match file (no events or lineups on their pages)

## standings

### table_vs_365 — 8 (warn, source)
- دوري أدنوك للمحترفين (538)  Al-Wahda: ours P5 W3 D0 L2 6-5 9 pts; 365Scores P5 W3 D0 L2 5-5 9 pts — favors **fotmob** — 365Scores' own results add up to our row: its table is out of step with its results (/c/uae-pro-league/)
- دوري أدنوك للمحترفين (538)  Ajman: ours P5 W3 D0 L2 11-12 9 pts; 365Scores P5 W3 D0 L2 11-11 9 pts — favors **fotmob** — 365Scores' own results add up to our row: its table is out of step with its results (/c/uae-pro-league/)
- الدوري الكويتي الممتاز (529)  Al-Arabi: ours P3 W0 D2 L1 7-8 2 pts; 365Scores P3 W0 D2 L1 6-7 2 pts — favors **fotmob** — 365Scores' own results add up to our row: its table is out of step with its results (/c/kuwait-premier-league/)
- الدوري الكويتي الممتاز (529)  Al-Salibikhaet: ours P3 W0 D2 L1 4-5 2 pts; 365Scores P3 W0 D2 L1 3-4 2 pts — favors **fotmob** — 365Scores' own results give P3 W1 D2 L0 5-4, neither its table nor ours; Al Sahel SC v Al-Salibikhaet 2026-08-27: FotMob 1-0, 365Scores 0-1 «Ended» (FotMob's goal events add up to 1-0; 365Scores' goal events add up to 0-0) (/c/kuwait-premier-league/)
- دوري يلو السعودي (10721)  Al-Ula FC: ours P5 W5 D0 L0 10-1 15 pts; 365Scores P5 W5 D0 L0 8-1 15 pts — favors **fotmob** — 365Scores' own results add up to our row: its table is out of step with its results (/c/saudi-first-division/)
- دوري يلو السعودي (10721)  Al-Wehda: ours P6 W1 D5 L0 9-7 8 pts; 365Scores P6 W1 D5 L0 9-6 8 pts — favors **fotmob** — 365Scores' own results add up to our row: its table is out of step with its results (/c/saudi-first-division/)
- دوري يلو السعودي (10721)  Jeddah: ours P6 W2 D2 L2 6-7 8 pts; 365Scores P6 W2 D2 L2 6-5 8 pts — favors **fotmob** — 365Scores' own results add up to our row: its table is out of step with its results (/c/saudi-first-division/)
- دوري يلو السعودي (10721)  Al Akhdoud: ours P5 W1 D3 L1 7-7 6 pts; 365Scores P5 W1 D3 L1 6-7 6 pts — favors **fotmob** — 365Scores' own results add up to our row: its table is out of step with its results (/c/saudi-first-division/)

## scorers

### log_vs_leaders — 2 (warn, stale)
- Ali Saleh: 2 goals in كأس الخليج العربي 2026 on the leaderboard, 1 in his match log (/p/721345/)
- Rami Al-Wasmani: 2 goals in كأس الخليج العربي 2026 on the leaderboard, 0 in his match log (/p/1008981/)
### vs_365 — 5 (warn, source)
- كأس الخليج العربي (329) Ali Saleh: 2 goals on our leaderboard (FotMob), 1 at 365Scores — favors **unknown** — UAE v Qatar 2026-09-30: FotMob credits him 1, 365Scores 2 (/p/721345/)
- كأس آسيا تحت 23 سنة (9571) Yuto Ozeki: 2 goals on our leaderboard (FotMob), 3 at 365Scores — favors **unknown** — no single match differs in the paired games (the lists count different matches) (/p/1436716/)
- دوري أبطال آسيا للنخبة (525) Brayan Perea: 1 goals on our leaderboard (FotMob), 2 at 365Scores — favors **unknown** — no single match differs in the paired games (the lists count different matches) (/p/281999/)
- الرابطة المحترفة الأولى التونسية (544) Achraf Ben Dhiaf: 2 goals on our leaderboard (FotMob), 1 at 365Scores — favors **unknown** — no single match differs in the paired games (the lists count different matches) (/p/639369/)
- دوري يلو السعودي (10721) João Silva: 3 goals on our leaderboard (FotMob), 2 at 365Scores — favors **unknown** — no single match differs in the paired games (the lists count different matches) (/p/1356320/)
### vs_fotmob — 1 (warn, stale)
- الدوري الأمريكي (130): 1 of our top scorers' goals differ from FotMob now (ours 2026-09-29T22:02:47Z): Rafael Navarro 14→15.0

## derived

### h2h_missing_meetings — 1 (error, stale)
- 34 of 85 head-to-head files: finished meetings of this season or last (our archive) are missing: 102101-102111: 2 (1000004914, 1000004918); 102101-102122: 3 (1000005227, 1000005228, 1000020529); 102111-102118: 2 (1000003440, 1000003448); 102117-102122: 1 (1000010302); 102117-102124: 2 (1000004912, 1000004916); 102118-182933: 1 (1000020528); 102119-102122: 2 (4877532, 5134948); 102119-102123: 4 (4941020, 1000004913, 1000004915)
### history_duplicate_rows — 1 (error, ours)
- 43 of 678 club histories: the same match (date + opponent) listed twice: 10015 (None): 1; 10076 (River Plate): 3; 10077 (Boca Juniors): 1; 10081 (Huracán): 1; 10083 (San Lorenzo): 1; 10086 (Argentinos Juniors): 1; 10087 (Banfield): 1; 10093 (None): 1
### h2h_index_count — 1 (warn, stale)
- 6 of 85 head-to-head files: h2h/index.json counts differ from the files: 102119-102122: index 21, file 20; 102119-102124: index 25, file 24; 102119-1552577: index 1, file 0; 102122-182933: index 23, file 22; 102123-149993: index 14, file 13; 149993-149994: index 13, file 12
### history_blank_opponent — 1 (warn, ours)
- 30 of 678 club histories: an opponent without a name: 101711 (Al-Arabi); 101713 (Kuwait SC); 101745 (Al Ahly SC); 101746 (Ismaily SC); 101747 (Tala'ea El Gaish); 101752 (Ghazl Al Mahalla); 101754 (Al Sharkeyah-ENPPI); 101757 (Al Mokawloon Al Arab)

## champions

### alltime_titles — 9 (error, ours)
- دوري أدنوك للمحترفين (538): the all-time table counts 17 titles for 15 completed, non-void seasons (the season in play or a cancelled one counted)
- دوري روشن السعودي (536): the all-time table counts 17 titles for 16 completed, non-void seasons (the season in play or a cancelled one counted)
- دوري نجوم قطر (535): the all-time table counts 17 titles for 16 completed, non-void seasons (the season in play or a cancelled one counted)
- الدوري الكويتي الممتاز (529): the all-time table counts 18 titles for 17 completed, non-void seasons (the season in play or a cancelled one counted)
- الدوري المصري الممتاز (519): the all-time table counts 17 titles for 14 completed, non-void seasons (the season in play or a cancelled one counted)
- البطولة الاحترافية المغربية (530): the all-time table counts 17 titles for 16 completed, non-void seasons (the season in play or a cancelled one counted)
- الرابطة المحترفة الأولى الجزائرية (516): the all-time table counts 17 titles for 16 completed, non-void seasons (the season in play or a cancelled one counted)
- الرابطة المحترفة الأولى التونسية (544): the all-time table counts 17 titles for 16 completed, non-void seasons (the season in play or a cancelled one counted)
- دوري نجوم العراق (524): the all-time table counts 17 titles for 16 completed, non-void seasons (the season in play or a cancelled one counted)
### duplicate_season — 1 (error, ours)
- الدوري الإسباني (87): season 2015 listed 2 times: نادي برشلونة, ريال بيتيس (/c/laliga/)
### year_offset — 1 (error, ours)
- كأس السوبر المصري (10314): our years look shifted against 365Scores' (agree at 0: 10, at -1: 22, at +1: 10) (/c/egypt-super-cup/)
### winner_vs_365 — 5 (warn, source)
- كأس الملك السعودي (9942): 3 of 37 seasons name another champion than 365Scores: 1967, 1968, 1969 — favors **365** — 365Scores checked against RSSSF for the 9 Arab leagues: right in every season but one swapped pair (audit 2026-09-30) (/c/saudi-kings-cup/)
- كأس السوبر المصري (10314): 9 of 19 seasons name another champion than 365Scores: 2003, 2004, 2005, 2010, 2016, 2017, 2019, 2020 — favors **unknown** — 365Scores checked against RSSSF for the 9 Arab leagues: right in every season but one swapped pair (audit 2026-09-30) (/c/egypt-super-cup/)
- دوري نجوم العراق (524): 1 of 31 seasons name another champion than 365Scores: 2022 — favors **365** — 365Scores checked against RSSSF for the 9 Arab leagues: right in every season but one swapped pair (audit 2026-09-30) (/c/iraq-stars-league/)
- الدوري الأمريكي (130): 1 of 1 seasons name another champion than 365Scores: 2017 — favors **unknown** — 365Scores checked against RSSSF for the 9 Arab leagues: right in every season but one swapped pair (audit 2026-09-30) (/c/mls/)
- الدوري الأرجنتيني (112): 6 of 18 seasons name another champion than 365Scores: 1913, 1933, 1970, 1971, 1984, 2011 — favors **unknown** — 365Scores checked against RSSSF for the 9 Arab leagues: right in every season but one swapped pair (audit 2026-09-30) (/c/argentina-liga-profesional/)

## identity

### placeholder_birth_date — 1 (warn, gap)
- 190 site players and 995 encyclopedia players have a placeholder birth date (0001-01-01): it must show as unknown, never as an age
### linked_name_differs — 1 (info, unknown)
- 194 EA FC cards carry a name unlike ours (nicknames, or namesakes to look at): Mauro Júnior (873556) = Mauro Jaqueson J. Ferreira Santos; Valentino Livramento (1107910) = Tino Livramento; Pep Chavarría (988805) = Josep María Chavarría Pérez; Djordje Petrović (1067256) = Đorđe Petrović; Flavien Boyomo (1187734) = Enzo Boyomo; Alberto Costa (1387439) = Alberto Oliveira Baio; Valentín Castellanos (823658) = Taty Castellanos; Anastasios Douvikas (873270) = Tasos Douvikas

## gaps

### team_name_ar_missing — 1 (warn, gap)
- 52 teams in our competitions have no Arabic name: JSM Laayoune (102040), Kabuscorp Palanca (114403), ES Hamam Sousse (147865), Panthère FC (150115), Al-Ahli (161717), Virunga (164857), Rayon Sport (165039), Academia F. Amadou Diallo (194004), Telephonat Bani Sweif (289697), CO Korhogo (405618), Hang Yuen FC (446686), Dekernes (517927), KMKM FC (558370), Widad Temara (570488), UNAM (589564)
### champions_missing — 12 (info, gap)
- تصفيات كأس آسيا (10609): no champions list
- تصفيات كأس العالم - آسيا (10197): no champions list
- تصفيات كأس العرب (11156): no champions list
- كأس آسيا تحت 23 سنة (9571): no champions list
- تصفيات دوري أبطال آسيا للنخبة (10622): no champions list
- كأس القارات للأندية (10703): no champions list
- تصفيات كأس أمم أفريقيا (10608): no champions list
- تصفيات كأس العالم - أمريكا الجنوبية (10199): no champions list
- تصفيات كأس العالم - الكونكاكاف (10198): no champions list
- تصفيات كأس العالم - أوروبا (10195): no champions list
- تصفيات كأس العالم - أفريقيا (10196): no champions list
- مباريات ودية دولية (114): no champions list
### club_card_fields — 1 (info, gap)
- 887 site clubs; empty: founded 554, trophies 234, stadium 50
### player_bio_fields — 1 (info, gap)
- 19797 site players; empty in FotMob: contract 11729, foot 7480, mv 6215, h 5645, shirt 2012, pos 14; still empty after the 365Scores/Transfermarkt fills: contract 10321, foot 6513, mv 5995, h 5161, shirt 1804, pos 14
### scorers_missing — 1 (info, gap)
- 132 finished match pages name fewer scorers than goals ({'lower': 131, 'ratings': 1}): FotMob gives these matches a score only; 365Scores often has the scorers
