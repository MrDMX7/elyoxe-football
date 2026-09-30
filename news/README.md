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

7. **media** (`media.py`, owner 2026-09-30: «أول ما يتوفر فيديو رسمي … ينرفق عدال للهدف اضغط لمشاهدته، ونفس الشي ملخص
   المباراة»): for every match of our competitions that is live or finished in the last 48 h, the official highlights and a
   clip per goal, from what the official channels published after kickoff: the journal's `youtube:` feeds (reused, not
   read twice), the `media:` channels (broadcasters, leagues, confederations, federations; each line says why it is
   official; a channel limited to competitions or to its national team is read only when one of them played), the official
   X accounts' posts that carry a video (the laptop reader marks them `video`), and FotMob's own link in the match file.
   Public: `v1/media/<match>.json` `{generated, match, highlights: [video], goals: {"<minute as shown, 45+2>-<playerId>": [video]}}` and
   `v1/media/recent.json`; a file is written only when its content changes. State (videos 4 days, the match files read,
   embed checks) in `state/news/media.json`. The site's `site/src/media.js` reads the file in the browser («▶ شاهد» by
   each goal, «▶ الملخص» with the match buttons, a sheet with the player). `python -m news.media --dry --explain [id]`
   prints every decision without writing; `media: block:` in sources.yaml takes a wrong video out for good.

   **Only confident matches are attached** (a missing video costs nothing, a wrong one costs the page). Highlights: both
   teams named in the title (Arabic clitics read through, national teams in seven languages from `nations.json`,
   `news/tools/nations.py`, or two flags «🇯🇴 🆚 🇸🇾»), a summary word (ملخص، أهداف المباراة، highlights، resumen، sintesi،
   résumé…), out after the final whistle or at half-time, never live / a full replay / a preview / a press conference /
   women / youth / another sport / a game simulation, every year, season or date in the title this match's, every score in
   it one this match had. Goal clips: the scorer named (full name, or a family name no one else in the match has) or the
   side named after the goal word («GOAL FOR PERU!», «¡GOOL DE MÉXICO!») when that side had one goal so far, a goal word,
   out after the goal's real minute (from FotMob's half start times), tied to the match (a team named, the club's or
   federation's own channel, or the competition's channel within 6 h), and its score, minute, penalty/own-goal/
   equaliser/ordinal words agreeing with that goal. Two goals by one scorer are told apart by those or by when the clip
   came out; otherwise left out. While a match is live, a clip waits for a match file read 10 min after it came out.

   Measured by hand on every attachment: 2026-09-26..30, an international break (50 matches, 1,053 official uploads): 25
   matches got their highlights (48 videos), 8 goals a clip, **0 wrong**; the club weekend 17-23 Sep (99 matches of 11
   competitions, 797 uploads): 46 matches with highlights, 12 goal clips, **0 wrong**. Traps seen in those uploads (each is a case in `tests/test_media.py`):
   US Soccer's clips of Hall's and Berhalter's goals against Peru, posted two days before both scored again against Chile;
   Serie A's «NAPOLI-INTER 3-1 | FULL MATCH | SERIE A 2025/26» two days after this season's Inter 3-2 Napoli; CAF TV's
   WAFCON (women's) highlights between the same countries as the men's qualifiers.

Official videos go to the social strips; they join the news only for a press conference, an injury or a transfer at
«agreed» or later — most of a club channel is training clips. Tools: `tools/probe_feeds.py` (is a feed alive and fresh),
`tools/try_link.py` (what a headline links to), `tools/youtube_ids.py` (handle → channel id, read from the page's
canonical link: a bare "channelId" on the page can be a related channel; `--check <id|@handle>…` prints what decides
whether a channel is official: name, handle, subscribers, badge, description, newest uploads — handles are not proof:
@SPL is a swimming-pool channel, @CAFTV a church), `tools/nations.py` (rebuilds `nations.json` with CLDR, laptop only).
Bulk checks of watch pages get HTTP 429 from YouTube after a few hundred; the pipeline itself reads only feeds and oEmbed.
