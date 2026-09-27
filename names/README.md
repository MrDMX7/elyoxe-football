# Arabic player names (tifo.elyoxe.com)

FotMob gives player names in Latin script only. This directory holds the Arabic
spelling for **every player the site shows**, keyed by FotMob player id.

| file | what |
|---|---|
| `players_ar.json` | `{fotmob_id: {latin, ar, source, qid, checked}}` (plus `wd_label` when the Wikidata Arabic was shortened or replaced, see below) |
| `review_uae.csv` | every UAE Pro League player (comp 538) and UAE national-team player (team 5789), sorted by club, for a one-time review by the owner. Columns `id, latin, ar, source, team` |
| `build_names.py` | the builder. Incremental: it skips ids already in `players_ar.json` and resolves only new players |

## Counts (first build, 2026-09-27)

Pool: **7,070 players**, all resolved.

| source | players | share |
|---|---|---|
| `wikidata` (Arabic label, or an Arabic alias) | 3,495 | 49.4% |
| `arwiki` (Arabic Wikipedia title) | 65 | 0.9% |
| `generated` (Gemini transliteration) | 3,510 | 49.6% |

- Of the `generated` entries, 1,671 matched a Wikidata item that has no Arabic label; `qid` is kept for them.
- 159 Wikidata entries were **trimmed** from the full legal name to the name FotMob uses, for example «فابيو فيرجينيو دي ليما» → «فابيو ليما». The original is kept in `wd_label`.
- 116 were **dropped to generated** because the Wikidata Arabic renders a different form of the name, for example Diney Borges → «ديني إديلسون». The original is kept in `wd_label`.
- 252 more were **dropped to generated** because their only Arabic was an `arz` (Egyptian Wikipedia) label or used پ/چ/ڤ/گ. These are bot transliterations such as «ديجو زيڤوليك», and the model gives «دييغو زيفوليتش» instead. The arz form is kept in `wd_label`.
- `review_uae.csv`: 443 players, of which 162 are `wikidata`, 5 `arwiki` and 276 `generated`. Emirati squad players are mostly missing from Wikidata.

## Where the pool comes from

The pool is read from the public feed `https://tifo.elyoxe.com/v1/` (gzip):

- `comp/{id}/players.json` (the players in each competition) and `comp/{id}/stats.json` (the goals and assists lists), for every competition in `index.json`.
- `team/{id}.json` squads, for every team in `teams.json` that has a file. Today that is the 14 UAE clubs plus the UAE national team.
- Lineups (starters, subs, unavailable) from `match/{id}.json`: every finished UAE Pro League match, plus finished matches of the last 21 days in every competition (`--match-days`). The builder takes these from `comp/{id}/fixtures.json`, because `day/` only keeps the last few days.

## Method

1. **Wikidata.** Wikidata has no FotMob-id property (checked 2026-09-27), so the builder searches CirrusSearch with `"<name>" haswbstatement:P106=Q937857` (footballers only), then scores each candidate on four things:
   - how well the name fits the en/fr/es/pt/de/it labels and aliases;
   - nationality: the FotMob code goes to a national team (P3441), then to its country, and is compared with the player's P1532 and P27;
   - birth year against the age FotMob gives;
   - club (P54) against Wikidata items found for the FotMob team name and for "<team> national football team".

   A match is accepted only if all of these hold:
   - the top candidate clearly beats the runner-up;
   - it has positive evidence;
   - it has no birth-year contradiction.

   A nationality mismatch (common for naturalised Gulf players) is accepted only with a club match, or with an exact birth year and no rival candidate. A one-word name (mononym) needs strong evidence.

   The Arabic form is picked in this order: the `ar` label, then the arwiki title, then the `ar` aliases. The builder never uses `arz` labels, which are Egyptian-Wikipedia bot transliterations. Among these, the builder prefers the form with as many words as the FotMob name.
2. **Check.** Some matches have an Arabic name longer than the FotMob name, or an English label that differs from it. For these, Gemini is asked which words of the Arabic render the FotMob name. The answer is accepted only if every word is copied from the Wikidata Arabic, so the entry keeps source `wikidata`/`arwiki`. If no words fit, the player goes to step 3.
3. **Gemini** (`gemini-3.5-flash`, key `GEMINI_API_KEY` from `~/workspace/content-pipeline/.env`).
   - Names go in batches of 50, with the nationality (and club) as a hint.
   - The prompt asks for the spelling Arab sports media use: Spanish j = خ, Portuguese «جونيور», French silent endings, the particles «دي»/«دا»/«فان».
   - Arab players get their real Arabic name. «عبدالله» is written as one word, and «عبد» + name as two words.
   - Every string in the `responseSchema` has a `maxLength`; without it the model loops.
4. **Normalize.**
   - Diacritics and tatweel are removed, and a trailing «(لاعب كرة قدم)» is dropped.
   - Persian ی/ک are mapped to ي/ك, and zero-width characters and NBSP are removed.
   - Anything with Latin letters or پ چ ڤ ژ گ is rejected.

## Re-running (hourly job)

```
python3 build_names.py                    # collect the pool, resolve new ids, rewrite both outputs
python3 build_names.py --no-gemini        # Wikidata only; unresolved ids wait for the next run
python3 build_names.py --retry-generated  # re-try Wikidata for generated ids that have no qid
python3 build_names.py --reuse-pool --limit 500   # resume in chunks from the cached pool
```

- **Cache.** Caches live in `--cache` (default `~/.cache/tifo-names`): HTTP searches, entities, the audit log `wd_audit.jsonl` and team QIDs. On a cold cache the team-QID map costs about 950 Wikidata calls (roughly 10 minutes, once).
- **Cost of a run.** Collecting the pool takes about 3-4 minutes of feed requests. Each new player then takes about 1 s against Wikidata.
- **IPv4.** The script forces IPv4, because the phone's resolver stalls about 5 s on AAAA lookups.
- **Names.** FotMob renames update `latin` in place. The Arabic is not re-derived.
- **Owner corrections.** Put the corrected `ar` into `players_ar.json` and set `source` to `"manual"`. Existing ids are never overwritten, and `--retry-generated` only touches `generated` entries.

## Known weak spots

- Some Wikidata Arabic labels are bot transliterations, not media spellings (e.g. «موستافا ازادزوى», «ياكو ميت»). They are marked `wikidata`, but they deserve a look for the most-shown players.
- Emirati squad players: 62% are `generated`. `review_uae.csv` exists for exactly this.
