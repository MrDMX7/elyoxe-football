# «تابع اللاعب»: follow a player — design

Owner, 2026-10-09: «ما يصير نسوي تابع اللاعب… ونربطه بالاخبار والنادي والمنتخب». All 20 of the second list and his own
three (minutes played, started, came on) approved: «طبق من افكاري وطبق من افكارك».

## 1. What it is

A follow on the **player himself**, not on a team. Following him puts him in «لاعبيني» (on «فريقي») and lets the visitor
choose alerts. The server resolves, every day, which teams that means: **his current club and his national team**. A
transfer moves the follow to the new club by itself and is an alert of its own. No account, no AI: the same device
subscription as the team alerts (web push), the same quiet hours, the same «بدون حرق».

## 2. The alerts (23)

Grouped by when they can be known. «id» is the event's identity for the never-twice claim (§5).

### A. Match time (the poller, seconds after the feed)

| # | alert | from | id |
|---|---|---|---|
| o1 | **بدأ أساسي** «إدين دجيكو أساسي الليلة: شالكه - فرايبورج» | lineups in the live detail | `start11` |
| o2 | **دخل بديل** «دخل الدقيقة 63'» | substitution event | `subin` |
| 2 | **مب في القائمة** (neither XI nor bench, lineups out) | lineups | `squad_out` |
| 1 | **طلع تبديل** «طلع الدقيقة 78'» (+ «مصاب» when the feed marks it) | substitution event | `subout` |
| 3a | **هدف / صناعة** | goal events (as team alerts) | `goal:<score>` / `assist:<score>` |
| 3b | **بطاقة** صفراء / حمراء | card events | `card:<colour>:<n>` |
| 5 | **ركلة جزاء** سجّلها / ضيّعها | penalty events (missed: to confirm in the plan) | `pen:<n>` |
| o3 | **لعب N دقيقة** + summary at full time | lineups + subs + full time | `end` |
| 3 | **the summary card** (image): minutes, rating, goals, shots | full-time detail | rides on `end` |
| 6 | **رجل المباراة / أعلى تقييم له هالموسم** | rating in lineups (POTM field: to confirm) | `potm` / `best` |
| 4 | **فيديو هدفه نزل** | the journal's media step (as team videos) | `video:<score>` |
| 7 | **مباراته بعد ساعة** + channel for the visitor's country | fixtures + the TV guide (204/281) | `soon` |

The match-time alerts cover every match Tifo follows for **either** of his teams. A national team's friendlies only when
Tifo has the match (the same limit as today).

### B. Daily (a «player watch» job: today's player files against yesterday's)

| # | alert | from | id |
|---|---|---|---|
| — | **انتقل** «رسمي: من شالكه إلى…» | profile team + Transfermarkt history | `move:<to>` |
| — | **انصاب** / **رجع من الإصابة** | profile `injury`, tm.json injuries | `inj:<start>` / `back:<start>` |
| 8 | **موقوف المباراة الياية** | suspensions (219) | `ban:<match>` |
| 9 | **إنذار وحد ويتوقف** | suspensions at-risk list (219) | `risk:<comp>:<n>` |
| 10 | **استدعاء للمنتخب** | callups/<team>.json | `call:<window>` |
| 11 | **رقم قريب** «هدف واحد ويوصل 100» | milestones (241) | `ms:<kind>:<n>` |
| 12 | **سباق الهدافين** «صار ثاني هدافين الدوري» | comp scorers list | `race:<comp>:<rank>` |
| 13 | **في تشكيلة الجولة** | data team of the round (129) | `totr:<comp>:<round>` |
| 15 | **عقده يخلص بعد 6 شهور** | profile `contract` | `contract:<date>` |
| 16 | **قيمته السوقية تغيّرت** | tm.json market value | `mv:<date>` |
| 17 | **تقييمه في EA FC تغيّر** | EA ratings file | `ea:<rating>` |
| 18 | **عيد ميلاده** | profile `born` | `bday:<year>` |

Daily alerts are sent at 10:00 in the visitor's time (their UTC offset is on the subscription), never in quiet hours.

### C. News (the journal, every 15 minutes)

| # | alert | from | id |
|---|---|---|---|
| — | **خبر عنه** (headline as the source wrote it: news rewriting is off since 2026-10-09) | journal stories whose entities name him | `news:<story>` |
| 14 | **إشاعة / مفاوضات / اتفاق / Here we go** — a separate switch, off by default | journal transfer stage | `stage:<story>:<stage>` |

### D. «لاعبيني»

| # | what | where |
|---|---|---|
| 20 | **صفحة لاعبيني**: every followed player's next match (club or national), on one timeline, and their latest news | «فريقي» section + `/mine/players/` (noindex, personal) |
| 19 | **ملخص الأحد**: each player's week (matches, minutes, goals, news) | push on Sunday 10:00; email for newsletter subscribers who opt in |

## 3. The pieces

1. **Subscription** (cards `/api/tifo/push/sub`, extended): `{player, events, quiet, o, nospoil, subscription}` →
   `TIFOPUSH#P<pid>` / `<endpoint hash>`. `DELETE` the same. Rate limits as team subscriptions; a device may follow up to 30
   players. Stored: the events chosen, quiet hours, offset. No IP.
2. **Player → teams map** (`v1/push/players.json`, written by the daily job): `{pid: {club, national, name_ar}}` for every
   followed player (the set of `TIFOPUSH#P*` pks, read once a day). The poller reads it to know which lineups to watch.
3. **Match time** (`push.py`): `plan()` already sees every live detail. It also finds followed players in the lineups,
   substitutions, goals, cards and penalties, and builds per-player payloads. Same hand-over (one async invoke), same
   sender with a `P<pid>` audience next to the team ones.
4. **Player watch** (new daily runner job on the laptop, after `tifo-names`): reads the followed players' profile.json /
   tm.json / suspensions / callups / milestones / scorers / team of the round / EA file, compares with yesterday's snapshot
   (`state/playerwatch.json`), and hands over the changes. Writes `players.json` (piece 2).
5. **News** (`news/run.py`): after clustering, a story whose entities include a followed player hands over `news`; a
   transfer story with a stage hands over `stage` (only to subscriptions with the switch on).
6. **Client** (`site/src/notify.js`, `pages.js`): «تابع اللاعب» on `/p/` and `/db/player/` next to «تابع <club>»; a sheet
   with the switches grouped A/B/C (defaults: o1, o2, 3a, 3b, o3, transfer, injury, news; the rest off); «لاعبيني» on
   «فريقي»; localStorage `tifo.push.players`.
7. **Weekly** (Sunday 10:00, runner): the digest push; the email to newsletter subscribers who ticked «لاعبيني» (the
   newsletter's double opt-in).

## 4. Copy

Light Emirati, Western digits, a score as one `dir="rtl"` run, the player's Arabic name (players_ar.json), never «وش/مين/
زي/تبي». Examples: «إدين دجيكو أساسي الليلة» · «دخل إدين دجيكو الدقيقة 63'» · «هدف! إدين دجيكو يسجّل لشالكه 1 - 0» ·
«انتهت: إدين دجيكو لعب 78 دقيقة وسجّل هدف» · «رسمي: إدين دجيكو ينتقل من شالكه إلى…» · «إدين دجيكو رجع من الإصابة».

## 5. Never twice, never stale

The team alerts' rules carry over: a claim `TIFOPUSHSENT#P<pid>#<scope>` / `<id>` (scope = match id, or the day for
daily alerts) before the first send; the poller's marks in state/push.json; a match event older than 10 minutes is
history. A goal is both a team and a player alert: a device that follows the team AND the scorer gets one push (the
sender merges per endpoint, the player's text wins).

## 6. Phases

1. **Match time**: A (all 12) + the follow button, the sheet, the subscription, players.json.
2. **Daily**: B (all 12) + the player watch job.
3. **News and «لاعبيني»**: C, D.

Each phase ships on its own: tests, a live check on a real match or a real day, then the next.

## 7. Tests

- Pure payload builders per alert (Arabic copy rules, as tests/test_engagement_ui.py).
- Lineup/substitution/card fixtures from saved FotMob details (tests/fixtures) through `plan()`.
- The daily diff on two snapshots.
- The claim on the in-memory table (as tests/test_push_dedupe.py).
- End to end with `tools/push_e2e.py` on a live match, as the team alerts were proven on 2026-09-28.

## 8. Limits, said plainly

- Match alerts only for matches Tifo follows. National-team friendlies only when Tifo has them.
- Injury, transfer, contract and value alerts are as fresh as the sources: once a day.
- iPhone: alerts only after «أضف إلى الشاشة الرئيسية» (Apple's rule; the same today for teams).
- POTM and missed penalties depend on fields the plan must confirm in FotMob's detail. An alert with no field is dropped,
  not guessed.
