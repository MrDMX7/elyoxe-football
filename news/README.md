# news/ — Tifo's journal (أخبار تيفو)

Owner 2026-09-30: «آلية تجيب أحدث الأخبار من كل مكان… ونربط كل خبر بنادي/مدرب/لاعب». Same plugin pattern as saas/cinema:
one reader per source kind, one item shape, rules first, Claude last.

```
python -m news.run [--local DIR] [--no-llm]      # the Fold runs it every 15 min: automation/phone/run-job.sh tifo-journal
```

1. **read** (`readers.py`): 11 RSS feeds, a rotating slice of 39 Arabic Google News queries, 20 official YouTube channels
   (`sources.yaml`), and 26 X accounts. X has no paid API here: `xreader.js` runs on the **laptop** (Task Scheduler «Tifo X
   reader», every 30 min, `xreader-task.vbs` = no console window), Edge parked off-screen with the @Elyoxe session
   (`automation/browse/profiles/x-reader/x-cookies.json`, exported from the Fold with `--export-cookies`), 5 accounts a run,
   read-only, and uploads `state/news/x-inbox.json`. It moved off the Fold the same day it was built: a browser every 30 min
   drained the phone's battery (owner 2026-09-30). Laptop off = the news carries on without X. If X logs the session out,
   the log says `NOT SIGNED IN`: sign in again in the Fold's screen browser and re-export.
2. **link** (`entities.py`): teams, players, coaches from the site's own data. Strong names link alone, weak surnames only
   next to their club, the clubs that share a name (النصر ×3) only with a nisba or a league cue, a country is a national
   team only after «منتخب» or at the headline start. `aliases.yaml` adds short forms. Every rule has a live mistake in
   `tests/test_news.py`.
3. **classify** (`classify.py`): transfer / injury / presser / statement / official / match / other, and the transfer
   stage (rumour → talks → agreed → here we go → official). Other sports and women's-team items are told apart.
4. **cluster** (`cluster.py`): one story per event across languages, merged on the entities the HEADLINE names (a passing
   mention of Messi is not the same story).
5. **summarize** (`summarize.py`): one Arabic headline + two sentences per story from all its sources, `claude -p` Haiku on
   the owner's subscription (payload over stdin). 25 per run, newest first; failure = the best original headline.
6. **publish** (public, `v1/news/`): `latest.json` (150 stories), `e/<team|player|coach>-<id>.json` (the stories whose
   headline names it), `transfers.json` (per player, furthest stage), `social.json` + `social/<team|comp|player>-<id>.json`
   (official videos). State (items 5 days, stories 10) in `state/news/state.json`.

Official videos go to the social strips; they join the news only for a press conference, an injury or a transfer at
«agreed» or later — most of a club channel is training clips. Tools: `tools/probe_feeds.py` (is a feed alive and fresh),
`tools/try_link.py` (what a headline links to), `tools/youtube_ids.py` (handle → channel id, read from the page's
canonical link: a bare "channelId" on the page can be a related channel).
