# Tifo engagement: alerts, predictions, commentators, the audit badge

Items 7, 8, 3 and 16, picked by the owner on 2026-10-06. This file is the contract between the engagement code and the v5
shell (`site/redesign/v5/`, owned by the design agent): what each module draws, the hooks the shell calls, the data files
and the API behind them, and how it all ships.

| item | backend | public data | UI module (global) |
|---|---|---|---|
| 7 «نبّهني» | `push.py` (poller plan + sender Lambda), `news/media.py` (goal videos), saas/cards `/api/tifo/push/sub` | `/v1/push.json` | `site/src/notify.js` (`TifoNotify`) |
| 8 «توقع وتحدى ربعك» | saas/cards `src/tifo_predict.py` (`/api/tifo/predict/*`, scorer every 10 min) | none (API only) | `site/src/predict.js` (`TifoPredict`) |
| 3 «المعلقين» | `news/tvindex.py` (journal, after `news/commentators.py`) | `/v1/tv/commentators.json` | `site/src/voices.js` (`TifoVoices`) |
| 16 «الأرقام مدققة» | `db/audit.py` (daily, `db.refresh`) | `/v1/audit/latest.json` | the shell draws the badge |

## How the modules fit the v5 shell

- **Markup is v5's:** `.grp > .gh > h2`, `.card`, `.row > .rt > small`, `.rv`, `.sw` (UISwitch, `role="switch"` +
  `aria-checked`), `.seg` with `.seg-th` and `button[data-t]`, `.pill` / `.pill.pri`, `.note`, `.gf`, `.empty`, and
  `<dialog class="sheet">` with `.sh-grab`, `.sh-hd`, `.sh-x[data-close]`, `.sh-bd`. Each module injects a few rules of its
  own (`#nf-css`, `#tp-css`, `#voice-css`) on the v5 tokens (`--label`, `--label2`, `--fill`, `--accent`, `--accent-bg`,
  `--r-s`) with fallbacks, so it reads right on any skin.
- **Two halves per module:** pure renderers (data in, HTML string out) that also run in Node (`module.exports`), so
  `site/redesign/v5/build.cjs` can prerender them like `ui.js`; and a browser half that wires what is on the page.
- **Loading:** add the files to the v5 bundle (`build.cjs` `["ui.js", "pages.js", "app.js"]` → append `notify.js`,
  `predict.js`, `voices.js` from `site/src/`), or load them as their own deferred scripts on the pages that use them. Each
  is ES5, self-contained, and does nothing on a page without its elements.
- **Copy:** light Emirati (الحين، الياية، شوف، نبّهني، سكّر، توقعاتي), never وش، زي، تبي، الجاي، جديد، مين; Western digits; a
  score between two names is one `dir="rtl"` run with a spaced hyphen («2 - 1»). `tests/test_engagement_ui.py` checks it.
- **v5's own click handler** (`app.js`) also sees the segmented control and the `[data-close]` buttons; both paths are
  idempotent.

## 7. «نبّهني»: alerts per team

**What a subscriber chooses (per team):** «لا شي» / «الأهداف بس» (`goal`) / «كل شي» (`start`, `goal`, `end`), a switch for
«فيديو الهدف لما ينزل» (`video`), and quiet hours for all teams (minutes after local midnight; default 1:00–7:00 when
switched on). Sent to the server with the subscription: `POST /api/tifo/push/sub {team, events, quiet: {s, e, o},
subscription}`; `o` is the device's UTC offset, re-sent on every change. No choice left = `DELETE`. «بدون حرق» on
(`tifo.nospoil` or `body.nospoil`): only `start` is sent.

**Hooks:**

| call | does |
|---|---|
| `TifoNotify.sheet({id, name})` | `<dialog class="sheet" id="sh-notify">` for a team page. Replaces v5's stub sheet in `pages.js` (team page); keep the «نبّهني» pill `data-sheet="sh-notify"` |
| `TifoNotify.body({id, name})` | the same body without the dialog (a sheet the shell draws itself, or a settings page) |
| `TifoNotify.mount(root)` | wires every `[data-nf-team]` block under `root`; call after inserting the HTML (idempotent) |
| `TifoNotify.state(teamId)` | `{events, mode: "off"/"goals"/"all", video}`, e.g. to light the pill («التنبيهات شغّالة») |
| `TifoNotify.set(teamId, events)` | from a tap only (Safari asks for permission only inside a user gesture) |
| `TifoNotify.quiet()` / `.setQuiet({s, e} or null)` | quiet hours for every team (a row in المزيد › الإعدادات can use these) |
| `TifoNotify.resync()` | sends every team again: call it when «بدون حرق» changes (v3's `tifo:nospoil` event is already heard) |
| `TifoNotify.supported()` | `"yes"`, `"ios-install"` (iPhone outside the installed app: the body shows how to install), `"no"` |
| `TifoNotify.openClip()` | on a match page: a «فيديو الهدف نزل» push opens `/m/<id>/#v=<goal key>`; this clicks that goal's «▶ شاهد» (`[data-goal-key]` row, `site/src/media.js`) once it is drawn |

Storage `localStorage tifo.push = {teams: {id: [events]}, quiet: {s, e} | null}`, the live site's key (teams chosen there
carry over). Event `tifo:notify {team, events}` after each change. The service worker (`site/src/sw.js`) is unchanged:
payload `{title, body, url, tag, team}`, `url` same-origin.

**What arrives:** kickoff «بدت المباراة / الإمارات - قطر»; goal «هدف! الإمارات 1 - 0 قطر / سجّل X في الدقيقة 23' · رأسية من ركنية»;
full time «انتهت: الإمارات 2 - 1 قطر / <competition>»; video «فيديو الهدف نزل / X 23' · الإمارات 1 - 0 قطر».

**Never twice** (the 2026-10-02..06 timeouts handed the same goals over every minute): a goal's identity is the score it
made (`goal:2-1`), so a minute moved by FotMob (87' -> 88') or a scorer filled in later is the same goal; the sender claims
each event in DynamoDB (`TIFOPUSHSENT#<match>`, conditional put after a consistent read) before its first send; the poller
writes its marks to `state/push.json` right after the hand-over. Videos come from the journal's media step, never from the
poller's minute loop. Details: `push.py` docstring, `docs/SCHEMA.md` § Web push; proof: `tests/test_push_dedupe.py`.

## 8. «توقع وتحدى ربعك»: predictions with friends

**Play:** guess the score of an upcoming match; 5 points for the exact score, 3 for the right goal difference (a draw with
another score counts), 2 for the right winner or draw. The final score before penalties from Tifo's match file, an
awarded result included. Locks at kickoff by the server's clock. Private leagues (names from a fixed list, up to 50
players) joined with a link shared on WhatsApp. A nickname and a device key, a recovery code for another phone; no
account, email or password.

**Hooks:**

| call | does |
|---|---|
| `TifoPredict.block(md)` | the match page's «توقعك للنتيجة» group: two steppers, «احفظ توقعي», the rule line. Pure (prerender it). For scheduled matches it replaces v5's local «منو بيفوز؟» pick; keep it on live and finished pages too (it shows the pick, the result and the points) |
| `TifoPredict.mount(root)` | wires every `[data-predict]` block (`data-mid`, `data-kick`, `data-status`, `data-hn`, `data-an`); a player's pick and points load from the API |
| `TifoPredict.page(el)` | «توقعاتي» into `el`: the player (or the nickname form and «استرجع توقعاتي»), the points, the leagues (a sheet with the table, share, copy, leave), the picks, the recovery code, rename. `?j=<invite>` shows the join card first |
| `TifoPredict.me()` / `.token()` | the player (or `null`) / the device token |
| `TifoPredict.NAMES`, `.COMPS` | the league names (the server's order) and the competition presets |

**Pages for the shell:** `/predict/` (personal: `noindex`): a shell with one element passed to `TifoPredict.page(el)`.
Entry points: a row «توقعاتي» in المزيد and in «فريقي», the «توقعاتي» link in each match block. Shared links are
`https://tifo.elyoxe.com/predict/?j=<invite>`.

**API** (`saas/cards src/tifo_predict.py`, behind `/api/tifo/*` with the edge's X-Origin-Key; a player is the header
`X-Tifo-Player: <pid>.<key>`):

| route | body / query | answer | limits |
|---|---|---|---|
| `POST /api/tifo/predict/me` | `{nick}` | 201 `{pid, token, code, nick}` (token and code shown once) | 5/h and 20/day per IP, 5,000/day overall |
| `GET /api/tifo/predict/me` | player | `{pid, nick, pts, ex, df, oc, n, np, leagues, picks}` (80 newest picks) | 1,200 reads/h per IP |
| `PATCH /api/tifo/predict/me` | `{nick}` | `{nick}` (league tables follow) | 3/day per player |
| `POST /api/tifo/predict/recover` | `{code}` | `{pid, token, nick}`: a new device key (5 kept) | 10/h per IP, 3,000/day overall |
| `POST /api/tifo/predict/code` | player | `{code}`: the old code stops working | 3/day per player |
| `PUT /api/tifo/predict/pick` | `{match, h, a}` (0–20) | `{match, h, a, at, ko}`; 409 «انقفل التوقع، المباراة بدت» after kickoff, «موعد المباراة ما تحدد للحين» when the time is TBD, more than 30 days ahead refused; 404 when Tifo has no match file | 150 writes/h per player, 600/h per IP, 300,000 picks/day overall |
| `GET /api/tifo/predict/match?id=` | player | `{match, ko, locked, pick, result, pts, k}` | reads |
| `GET /api/tifo/predict/picks?ids=1,2,…` | player | `{picks: {match: {h, a, pts, k}}}` (60 ids) | reads |
| `POST /api/tifo/predict/league` | `{name: 0–9, comps: [ids] (≤ 5, none = every match)}` | 201 `{lid, name, owner_nick, n, comps, invite, url, cap}` | 3/day per player, 20 leagues per player |
| `GET /api/tifo/predict/league?id=[&match=]` | member | `{league, members (ranked: points, then exact, difference, winner), me[, match]}`; `match`: everybody's pick after kickoff, only how many picked before | reads |
| `POST /api/tifo/predict/join` | `{invite}` | `{…league, already}`; 409 when full (50) or at 20 leagues | 20/day per player |
| `POST /api/tifo/predict/leave` | `{lid}` | 204; the last one out deletes the league and its link | writes |
| `GET /api/tifo/predict/invite?code=` | none | `{name, owner_nick, n, cap, full}` (the join card) | 120/h per IP |

Errors are `{error: "<Arabic sentence>"}` with 400/401/404/409/429/503. A 401 on a stored token means the device must
register or recover again (the module clears it).

**Nicknames** (`saas/cards src/tifo_badwords.py`): 2–20 letters, digits, spaces, `_ . -`; no links, handles or phone
numbers; nothing that passes for Tifo's staff; Arabic (Gulf, Levantine, Egyptian, Maghrebi), English and Arabizi
insults, obscenities and slurs, read through diacritics, tatweel, repeated letters, dots between letters and leetspeak.
No other free text anywhere (league names come from the list).

**Scoring** (EventBridge every 10 min, `{"tifo_predict": "score"}`): a match with picks (`TP#PEND`) is read 105 min after
kickoff; once its file is final every pick is scored in its own transaction (the pick at result version v, the player's
totals, the totals of each league it counts in), so a run that dies or a second run never counts a pick twice. Re-read at
+1, +3 and +7 days for awarded results (the difference moves every total, only in the leagues that counted it); a later
decision by hand: `{"tifo_predict": "recheck", "match": <id>}` once the match file has it. Postponed: waits for the new
kickoff; cancelled or abandoned for 3 days, or no result after 14: void.

**DynamoDB** (the `cards` table, pay per request; layout in the `tifo_predict.py` docstring): players `TP#P#<pid>/META`
and their picks `PK#<ko>#<match>`; a match's picks `TP#M#<match>/P#<pid>` and `RESULT`; codes `TP#CODE#<hmac>`; leagues
`TP#L#<lid>/META` and members `M#<pid>`; invites `TP#INV#<code>`; the queues `TP#PEND` and `TP#RECHECK`. Keys and codes are
stored only as HMACs; no IP at rest (rate limits key an HMAC of it, in rows that expire after 2 h or 2 days).

## 3. «المعلقين»: commentators

**Data** `/v1/tv/commentators.json` (`news/tvindex.py`, refreshed with every commentators run, schema in `docs/SCHEMA.md`):
for each famous voice (the `FAMOUS`/`VARIANTS` spellings of `news/commentators.py`) his matches today and next, the
recent ones, his channels and competitions with counts, and since when we have him; the matches those lists name, with
whether each has its own page. Facts from Kooora's daily lists only; nothing about a person is written or generated.

**Hooks:**

| call | does |
|---|---|
| `TifoVoices.load()` | the index (one fetch per page) |
| `TifoVoices.page(index, keyOrSlug)` | a commentator's page body: name, one fact line («علّق على 14 مباراة من 30 سبتمبر 2026، أكثرها على beIN SPORTS 1.»), «معلّقي المفضل» pill, «اليوم والياي», «آخر مبارياته», «القنوات», «البطولات», the source line. Pure |
| `TifoVoices.list(index)` | `/commentators/`: every famous voice, the ones with a match today first |
| `TifoVoices.picker(index)` | the «معلّقك المفضل» sheet body (a switch per voice), e.g. in المزيد › الإعدادات |
| `TifoVoices.mount(root)` | wires the `[data-voice]` pills and switches; fills the `<time data-voice-time>` in the visitor's zone |
| `TifoVoices.favs()` / `.setFavs([keys])` | `localStorage tifo.voices`; event `tifo:voices` |
| `TifoVoices.decorate(root)` | after a day list renders: rows (`.mr[data-mid]` in v5, `a.m[data-mid]` on the live site) of matches a favourite voice calls get `class="fav-voice"` and a «🎙 name · channel» line |

**Pages for the shell:** `/commentators/` (the live page today is `site/src/tv.js`'s shell) and one page per voice,
`/commentators/<slug>/` (`slug` from the index, Arabic with hyphens; encode it in links). Prerender both at build time
from the index (indexable: «معلق مباراة …» searches); the browser refreshes nothing else than the times.

## 16. «الأرقام مدققة»: the audit badge

`/v1/audit/latest.json`, written after each full daily audit (`db/audit.py`, laptop `db.refresh` at 04:30 UAE):

```json
{"generated": "2026-10-05T01:23:07Z", "ok": false, "checked": 369880, "errors": 8, "warnings": 24,
 "areas": {"matches": {"ar": "المباريات", "checked": 13359, "errors": 0, "warnings": 2, "ok": true}, "...": {}}}
```

Areas: freshness «تحديث البيانات», matches «المباريات», standings «جداول الترتيب», scorers «الهدافين», derived
«المواجهات وتاريخ الأندية», champions «الأبطال», identity «هوية اللاعبين والأندية», gaps «النواقص». `ok` = no error (an area
that crashed or checked nothing is never ok). Counts only; the findings stay private (`state/audit/<date>.json`). The
numbers count findings, not wrong values, so a badge reads honestly as «فحصنا 369,880 رقم اليوم» and, when `ok` is false,
«فيه 8 ملاحظات نشتغل عليها». A file older than 2 days means the audit did not run.

## Shipping

Any order is safe: an old cards API drops `video` and `quiet` (the sender then has nobody asking for videos), an old
sender ignores both, and the UI talks only to routes that exist.

1. **saas/cards** (`docs/engagement/cards-predictions.patch`: `src/tifo_predict.py`, `src/tifo_badwords.py`, the
   `/api/tifo/predict/*` routes and the scorer event in `src/app.py`, `video` + `quiet` on `/api/tifo/push/sub`, the
   `TifoPredictScore` schedule in `template.yaml`, three test files):
   ```
   git -C C:/Users/requi/workspace/saas/cards switch -c predictions
   git -C C:/Users/requi/workspace/saas/cards apply --index C:/Users/requi/workspace/saas/football/docs/engagement/cards-predictions.patch
   cd C:/Users/requi/workspace/saas/cards && python -m pytest tests -q -p no:cacheprovider && python scripts/local_test.py
   git -C C:/Users/requi/workspace/saas/cards commit -m "Tifo predictions and push choices"
   ```
   then deploy from the machine that deploys cards: `./deploy.sh` (runs `scripts/local_test.py` first; adds one
   EventBridge rule; no IAM change: transactions use the actions `DynamoDBCrudPolicy` already grants).
2. **This repo:** merge the branch into main, then the poller stack from the phone: `./deploy.sh` (tests gate, then the
   poller and the push sender, which share the bundle; it keeps the live `ALERT_TO`). Watch the poller's CloudWatch
   `Duration` / `Max Memory Used` for an hour.
3. **Site stack, once** (the `x-viewer-ip` function on `/api/tifo/*`), the stack only, no site build:
   `aws cloudformation deploy --region ap-south-1 --stack-name elyoxe-tifo-site --template-file site/template.yaml --no-fail-on-empty-changeset`
4. **Laptop jobs** need nothing: the journal (`tools.runner journal`, every 15 min) runs `news/media.py` (goal videos; its
   first run only records) and `news/tvindex.py` (first run reads the days since 2026-09-30) from main; `db.refresh`
   writes `/v1/audit/latest.json` after its next full audit (04:30 UAE). Stop the video pushes with `TIFO_VIDEO_PUSH=0`
   in the job's environment or `python -m news.run --no-push`.
5. **The shell:** the hooks above; nothing in `site/build.cjs` or the live templates was changed.
