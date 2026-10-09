# «تابع اللاعب» Phase 1 (match time) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A visitor follows a player on his `/p/` page and gets web-push alerts for his matches with his club or his national team: before kickoff, the lineup, his minutes, goals, assists, cards, penalties, the full-time line, man of the match, his goal's video.

**Architecture:** The cards API stores a player subscription (`TIFOPUSH#P<pid>`) and a follow index (`TIFOFOLLOW` / `P<pid>`). A laptop job turns the index into `state/push_players.json` (each followed player's club and national team). The poller's existing `push.plan()` (it already sees every live, prematch and final detail) asks a new pure module, `pushplayer.py`, for the player events in that detail and hands them to the existing sender Lambda in the same jobs, with `P<pid>` audiences next to the team ones. The sender sends each endpoint once per job (player text first), caps player alerts per device per day, and picks the visitor's channel line by country. The client adds «تابع اللاعب» and a sheet to `/p/` pages (`site/src/notify.js`).

**Tech Stack:** Python 3.13 (poller, sender, cards Lambda; pytest), ES5 browser modules (notify.js, pages.js, app.js; node-run tests), DynamoDB `cards`, S3 data bucket `state/`, AWS SAM (saas/football/deploy.sh, saas/cards/deploy.sh).

**Spec:** `saas/football/docs/superpowers/specs/2026-10-09-player-follow-design.md` (§2 A, §3 pieces 1-3 and 6, §4, §5).

## Deviations from the spec (decided while planning)

- The followed players' teams go to `state/push_players.json` (private, poller state), not a public `v1/push/players.json`:
  which players people follow is not something to publish.
- «رجل المباراة» = the match's highest FotMob rating among both lineups (FotMob's detail has no POTM field in our schema).
- «أعلى تقييم له هالموسم» (spec 2 A #6, second half) moves to phase 2: it needs his season's match ratings (the daily job).
- `/db/player/` pages get «تابع اللاعب» in phase 3 with «لاعبيني»: they use the legacy page shell, not v5.

## Global Constraints

- Copy: light Emirati, Western digits, a score as one `dir="rtl"`-safe run «2 - 1» with spaced hyphen, never «وش، مين، زي، تبي، الجاي، جديد».
- The player's name: `names/players_ar.json` Arabic name, else the feed's name; never «<TBD>».
- No AI anywhere in this feature.
- Defaults (phase 1's share of the owner's 8): `start11, subin, goal, assist, card, end`. Everything else off until the visitor turns it on.
- Per-device cap: at most `PLAYER_DAILY_CAP = 20` player alerts per endpoint per UAE day (team alerts are not counted).
- The summary card is drawn in the browser (the player page's existing «صورة لأي قسم»), never rendered on a server.
- Never twice: every player event is claimed in `TIFOPUSHSENT#<match>` before its first send (the existing `push.claim`).
- A device may follow at most 30 players.
- «بدون حرق»: only `soon` and `start11` are kept (the client drops the rest before subscribing).
- Measure the poller's billed duration before (Task 1) and after (Task 7); more than +15 % at p95 is a stop.

## Review Focus

1. **A goal by a followed player whose team the visitor also follows**: one push, the player's text. Task 4 tests it.
2. **A predicted lineup (`lastStarting11`)**: never «أساسي» or «مب في القائمة»; only a confirmed lineup (`standard`). Task 3 tests it.
3. **A followed player with no national team or club in the map** (a free agent, a new follow not yet mapped): no crash, no alert. Task 3 tests it.
4. **A substitution the feed fills in late** (first_seen older than 10 minutes): not sent, like late goals. Task 3 tests it.
5. **The visitor's country unknown or without a channel row**: «مباراته بعد ساعة» without the channel line, never «القناة: undefined». Task 4 tests it.

---

### Task 1: Baseline the poller's duration

**Files:**
- Create: `tools/poller_time.py`
- Create: `docs/superpowers/plans/2026-10-09-player-follow-phase1.baseline.json` (output)

**Interfaces:**
- Produces: `python -m tools.poller_time --hours 24 [--out FILE]` printing `{"n", "p50", "p95", "max"}` of `Billed Duration` (ms) from the poller's CloudWatch REPORT lines.

- [ ] **Step 1: Write the script**

```python
"""Billed duration of elyoxe-football-poller from its CloudWatch REPORT lines (player-follow plan, Task 1 and Task 7).
  python -m tools.poller_time --hours 24 [--out FILE]"""
import argparse, json, re, statistics, time

import boto3

GROUP = "/aws/lambda/elyoxe-football-poller"
BILLED = re.compile(r"Billed Duration: (\d+) ms")


def durations(hours, client=None):
    logs = client or boto3.client("logs", region_name="ap-south-1")
    kw = {"logGroupName": GROUP, "startTime": int((time.time() - hours * 3600) * 1000), "filterPattern": "REPORT"}
    out = []
    while True:
        r = logs.filter_log_events(**kw)
        out += [int(m.group(1)) for e in r.get("events", []) for m in [BILLED.search(e["message"])] if m]
        if not r.get("nextToken"):
            return out
        kw["nextToken"] = r["nextToken"]


def summary(xs):
    if not xs:
        return {"n": 0}
    xs = sorted(xs)
    return {"n": len(xs), "p50": int(statistics.median(xs)), "p95": xs[int(len(xs) * 0.95) - 1], "max": xs[-1]}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--hours", type=float, default=24); ap.add_argument("--out")
    a = ap.parse_args(argv)
    s = summary(durations(a.hours)); s["hours"] = a.hours; s["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(json.dumps(s))
    if a.out:
        open(a.out, "w").write(json.dumps(s, indent=1))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test the pure part**

Add to `tests/test_push.py`:

```python
def test_poller_time_summary():
    from tools.poller_time import summary
    assert summary([]) == {"n": 0}
    s = summary(list(range(1, 101)))
    assert s == {"n": 100, "p50": 50, "p95": 95, "max": 100}
```

Run: `python -m pytest -q tests/test_push.py -k poller_time` → PASS.

- [ ] **Step 3: Record the baseline**

Run (Git Bash: the log group is a path): `MSYS_NO_PATHCONV=1 python -m tools.poller_time --hours 24 --out docs/superpowers/plans/2026-10-09-player-follow-phase1.baseline.json`
Expected: one JSON line with n > 1000.

- [ ] **Step 4: Commit**

```bash
git add tools/poller_time.py tests/test_push.py docs/superpowers/plans/2026-10-09-player-follow-phase1.baseline.json
git commit -m "tools: poller billed-duration baseline (player follow, before)"
```

---

### Task 2: Cards API: player subscriptions, follow index, device cap

**Files:**
- Modify: `saas/cards/src/app.py` (`tifo_push_sub`, constants near `TIFOPUSH_EVENTS`)
- Test: `saas/cards/tests/test_tifo_api.py`

**Interfaces:**
- Produces: `POST /api/tifo/push/sub {player, events, quiet, cc, subscription}` → item `TIFOPUSH#P<pid>` / `<sha256(endpoint)[:32]>` with `{player, endpoint, p256dh, auth, events, cc, quiet?, created, ttl}`; follow index `TIFOFOLLOW` / `P<pid>` `{n}` (n = devices following, never below 0); device list `TIFOPUSHDEV#<sk>` / `players` `{ids: [pid…]}`.
- Produces: `DELETE /api/tifo/push/sub {player, endpoint}` → removes the subscription, decrements the index, drops pid from the device list.
- Player events accepted: `TIFOPUSH_PEVENTS = ("soon", "start11", "squad_out", "subin", "subout", "goal", "assist", "card", "pen", "end", "potm", "video")`; default `TIFOPUSH_PDEFAULT = ("start11", "subin", "goal", "assist", "card", "end")`.

- [ ] **Step 1: Write the failing tests**

```python
def test_player_subscribe_index_and_unsubscribe(fake):
    body = {"player": 15403, "events": ["start11", "goal", "hack"], "cc": "ae", "subscription": SUB}
    assert app.handler(ev("POST", "/api/tifo/push/sub", body), None)["statusCode"] == 204
    item = next(v for (p, s), v in fake.items.items() if p == "TIFOPUSH#P15403")
    assert item["events"] == ["start11", "goal"] and item["cc"] == "AE" and item["player"] == 15403
    assert fake.items[("TIFOFOLLOW", "P15403")]["n"] == 1
    sk = item["sk"]
    assert fake.items[(f"TIFOPUSHDEV#{sk}", "players")]["ids"] == [15403]
    # the same device again: no double count
    app.handler(ev("POST", "/api/tifo/push/sub", body), None)
    assert fake.items[("TIFOFOLLOW", "P15403")]["n"] == 1
    assert app.handler(ev("DELETE", "/api/tifo/push/sub", {"player": 15403, "endpoint": SUB["endpoint"]}), None)["statusCode"] == 204
    assert not any(p == "TIFOPUSH#P15403" for (p, s) in fake.items)
    assert fake.items[("TIFOFOLLOW", "P15403")]["n"] == 0
    assert fake.items[(f"TIFOPUSHDEV#{sk}", "players")]["ids"] == []

def test_player_defaults_and_device_cap(fake, monkeypatch):
    app.handler(ev("POST", "/api/tifo/push/sub", {"player": 1, "subscription": SUB}), None)
    item = next(v for (p, s), v in fake.items.items() if p == "TIFOPUSH#P1")
    assert item["events"] == list(app.TIFOPUSH_PDEFAULT) and "cc" not in item
    monkeypatch.setattr(app, "TIFOPUSH_MAX_PLAYERS", 2)
    assert app.handler(ev("POST", "/api/tifo/push/sub", {"player": 2, "subscription": SUB}), None)["statusCode"] == 204
    r = app.handler(ev("POST", "/api/tifo/push/sub", {"player": 3, "subscription": SUB}), None)
    assert r["statusCode"] == 409 and "30" not in r["body"]       # the message names the app's own limit
    assert app.handler(ev("POST", "/api/tifo/push/sub", {"player": 2, "subscription": SUB}), None)["statusCode"] == 204   # re-save is fine

def test_player_and_team_need_one_of_them(fake):
    assert app.handler(ev("POST", "/api/tifo/push/sub", {"subscription": SUB}), None)["statusCode"] == 400
    assert app.handler(ev("POST", "/api/tifo/push/sub", {"player": "x", "subscription": SUB}), None)["statusCode"] == 400
```

The in-memory `Table` needs `get_item`; add to the class at the top of the test file:

```python
    def get_item(self, Key): it = self.items.get((Key["pk"], Key["sk"])); return {"Item": dict(it)} if it else {}
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd saas/cards && python -m pytest -q tests/test_tifo_api.py -k player`
Expected: FAIL (400 «الفريق مطلوب»).

- [ ] **Step 3: Implement**

Next to `TIFOPUSH_EVENTS` / `TIFOPUSH_DEFAULT` in `src/app.py`:

```python
TIFOPUSH_PEVENTS = ("soon", "start11", "squad_out", "subin", "subout", "goal", "assist", "card", "pen", "end", "potm", "video")
TIFOPUSH_PDEFAULT = ("start11", "subin", "goal", "assist", "card", "end")   # owner 2026-10-09: 8 defaults (6 in phase 1)
TIFOPUSH_MAX_PLAYERS = 30
```

At the top of `tifo_push_sub`, after `sk = …`, branch on `player`:

```python
    if b.get("player") is not None:
        if not str(b.get("player")).isdigit(): raise HttpError(400, "اللاعب مطلوب")
        return _tifo_push_player(b, sub, ep, sk, method, now)
```

and the helper:

```python
def _tifo_push_player(b, sub, ep, sk, method, now):
    """«تابع اللاعب» (spec 2026-10-09 §3.1): one item per device and player, the follow index TIFOFOLLOW/P<pid> (how many
    devices follow him: the laptop's pushplayers job reads it), and the device's own list (30 players at most)."""
    pid = int(b["player"]); pk = f"TIFOPUSH#P{pid}"
    dev = {"pk": f"TIFOPUSHDEV#{sk}", "sk": "players"}
    ids = [int(x) for x in ((table.get_item(Key=dev).get("Item") or {}).get("ids") or [])]
    had = table.get_item(Key={"pk": pk, "sk": sk}).get("Item") is not None
    if method == "DELETE":
        table.delete_item(Key={"pk": pk, "sk": sk})
        if had:
            cur = int((table.get_item(Key={"pk": "TIFOFOLLOW", "sk": f"P{pid}"}).get("Item") or {}).get("n", 0))
            table.put_item(Item={"pk": "TIFOFOLLOW", "sk": f"P{pid}", "n": max(0, cur - 1), "at": now})
        table.put_item(Item={**dev, "ids": [x for x in ids if x != pid], "ttl": now + 180 * 86400})
        return resp(204, None)
    if not had and pid not in ids and len(ids) >= TIFOPUSH_MAX_PLAYERS:
        raise HttpError(409, f"تتابع {len(ids)} لاعب، شيل واحد أول")
    keys = sub.get("keys") or {}; p256, auth = str(keys.get("p256dh") or ""), str(keys.get("auth") or "")
    if not (re.fullmatch(r"[A-Za-z0-9_-]{80,100}={0,2}", p256) and re.fullmatch(r"[A-Za-z0-9_-]{16,24}={0,2}", auth)): raise HttpError(400, "اشتراك غير صالح")
    ev = list(dict.fromkeys(e for e in (b.get("events") or TIFOPUSH_PDEFAULT) if e in TIFOPUSH_PEVENTS)) or list(TIFOPUSH_PDEFAULT)
    item = {"pk": pk, "sk": sk, "player": pid, "endpoint": ep, "p256dh": p256, "auth": auth, "events": ev, "created": now, "ttl": now + 180 * 86400}
    cc = str(b.get("cc") or "").upper()
    if re.fullmatch(r"[A-Z]{2}", cc): item["cc"] = cc
    q = _push_quiet(b.get("quiet"))
    if q: item["quiet"] = q
    table.put_item(Item=item)
    if not had:
        cur = int((table.get_item(Key={"pk": "TIFOFOLLOW", "sk": f"P{pid}"}).get("Item") or {}).get("n", 0))
        table.put_item(Item={"pk": "TIFOFOLLOW", "sk": f"P{pid}", "n": cur + 1, "at": now})
    if pid not in ids:
        table.put_item(Item={**dev, "ids": ids + [pid], "ttl": now + 180 * 86400})
    return resp(204, None)
```

Update the route comment block above `tifo_push_sub` with the `player` form.

- [ ] **Step 4: Run the tests**

Run: `cd saas/cards && python -m pytest -q tests/test_tifo_api.py && python scripts/local_test.py`
Expected: all PASS, local_test silent with exit 0.

- [ ] **Step 5: Commit**

```bash
git add src/app.py tests/test_tifo_api.py
git commit -m "api: «تابع اللاعب» subscriptions (TIFOPUSH#P<pid>), the follow index and a 30-player cap per device"
```

---

### Task 3: `pushplayer.py`: which match events concern a followed player

**Files:**
- Create: `saas/football/pushplayer.py`
- Test: `saas/football/tests/test_pushplayer.py`

**Interfaces:**
- Consumes: `push.total_minute`, `push._age_min`, `push.FRESH_MINUTES`, `push.STALE_MINUTES`, `push.KICKOFF_WINDOW`, `push.END_WINDOW`, `push.player_ar`, `push._name`, `push._score`.
- Produces:
  - `lineup(full) -> {"start": {pid: side}, "bench": {pid: side}, "confirmed": bool}`
  - `minutes_played(full, pid, end_minute) -> int | None`
  - `events_for(d, full, followed, sent, now) -> [(key, kind, pid, e|None, extra)]`: `followed` = `{pid(str): {"club": int|None, "national": int|None}}`; `sent` = the match's marks (state/push.json keys); key = `p<pid>:<kind>[:<id>]`; goals and assists are NOT here (Task 4 adds them to the team goal jobs).
  - `payload(kind, d, pid, e, names_ar, extra) -> {title, body, url, tag, kind}` (+ `cc_body` for `soon`).
  - `KINDS`, `DEFAULTS`.

- [ ] **Step 1: Write the failing tests**

```python
"""pushplayer.py: the match-time events of a followed player (spec 2026-10-09 §2 A) and their Arabic payloads."""
import datetime as dt

import pushplayer as PP

NOW = dt.datetime(2026, 10, 11, 17, 0, tzinfo=dt.timezone.utc)
F = {"15403": {"club": 10189, "national": 8}, "2777": {"club": 49678, "national": None}, "99": {"club": None, "national": None}}


def det(status="live", minute=70, ko="2026-10-11T16:00:00Z", lu_type="standard", events=(), score=(1, 0)):
    d = {"id": 5, "status": status, "minute": minute, "kickoff_utc": ko, "comp_name_ar": "الدوري الألماني",
         "home": {"id": 10189, "name_ar": "شالكه"}, "away": {"id": 7, "name_ar": "فرايبورج"},
         "score": {"home": score[0], "away": score[1]}, "periods": {"firstHalfStarted": ko, "gameEnded": "2026-10-11T17:52:00Z"}}
    full = dict(d, events=list(events), lineups={"type": lu_type,
        "home": {"starters": [{"id": 15403, "name": "Edin Dzeko", "rating": 7.9}], "subs": [{"id": 555, "name": "Sub Guy", "rating": 6.1}]},
        "away": {"starters": [{"id": 1, "name": "A", "rating": 8.4}], "subs": []}})
    return d, full


def ev_(t, minute, pid, out=None, detail=None, seen="2026-10-11T16:59:00Z"):
    e = {"type": t, "minute": minute, "team": "home", "player": {"id": pid, "name": "x"}, "first_seen": seen, "event_id": f"{t}-{minute}-{pid}"}
    if out: e["player_out"] = {"id": out, "name": "y"}
    if detail: e["detail"] = detail
    return e


def kinds(rows):
    return [(k, kind, pid) for k, kind, pid, e, x in rows]


def test_confirmed_lineup_gives_start11_and_squad_out():
    d, full = det(status="scheduled", minute=None, ko="2026-10-11T17:40:00Z")
    rows = kinds(PP.events_for(d, full, {"15403": F["15403"], "77": {"club": 10189, "national": None}}, [], NOW))
    assert ("p15403:start11", "start11", "15403") in rows
    assert ("p77:squad_out", "squad_out", "77") in rows


def test_predicted_lineup_says_nothing():
    d, full = det(status="scheduled", minute=None, ko="2026-10-11T17:40:00Z", lu_type="lastStarting11")
    assert [r for r in kinds(PP.events_for(d, full, F, [], NOW)) if r[1] in ("start11", "squad_out")] == []


def test_soon_only_in_its_window_and_only_for_his_teams():
    d, full = det(status="scheduled", minute=None, ko="2026-10-11T18:00:00Z", lu_type=None)
    rows = kinds(PP.events_for(d, full, F, [], NOW))
    assert ("p15403:soon", "soon", "15403") in rows and not any(r[2] in ("2777", "99") for r in rows)
    d, full = det(status="scheduled", minute=None, ko="2026-10-11T19:30:00Z", lu_type=None)
    assert kinds(PP.events_for(d, full, F, [], NOW)) == []


def test_sub_in_out_cards_and_missed_penalty():
    evs = [ev_("sub", 63, 555, out=15403, detail="injury"), ev_("yellow", 65, 15403), ev_("missed_penalty", 66, 15403)]
    d, full = det(events=evs)
    rows = kinds(PP.events_for(d, full, {"15403": F["15403"], "555": {"club": 10189, "national": None}}, [], NOW))
    assert ("p555:subin", "subin", "555") in rows and ("p15403:subout", "subout", "15403") in rows
    assert ("p15403:card:yellow", "card", "15403") in rows and ("p15403:pen:66", "pen", "15403") in rows


def test_already_sent_and_late_events_are_skipped():
    evs = [ev_("yellow", 65, 15403), ev_("sub", 20, 555, out=1, seen="2026-10-11T16:30:00Z")]
    d, full = det(events=evs)
    rows = kinds(PP.events_for(d, full, {"15403": F["15403"], "555": {"club": 10189, "national": None}}, ["p15403:card:yellow"], NOW))
    assert rows == []


def test_end_minutes_and_man_of_the_match():
    evs = [ev_("sub", 63, 555, out=15403)]
    d, full = det(status="finished", minute=None, events=evs)
    rows = PP.events_for(d, full, {"15403": F["15403"], "555": {"club": 10189, "national": None}, "1": {"club": 7, "national": None}}, [], NOW)
    ends = {pid: x for k, kind, pid, e, x in rows if kind == "end"}
    assert ends["15403"]["min"] == 63 and ends["555"]["min"] == 27
    assert [pid for k, kind, pid, e, x in rows if kind == "potm"] == ["1"]          # 8.4 is the match's best rating


def test_unmapped_player_never_crashes():
    d, full = det(status="scheduled", minute=None, ko="2026-10-11T18:00:00Z")
    assert all(r[2] != "99" for r in kinds(PP.events_for(d, full, F, [], NOW)))


def test_payload_copy():
    d, full = det()
    names = {"15403": {"ar": "إدين دجيكو"}}
    p = PP.payload("subout", d, "15403", ev_("sub", 63, 555, out=15403, detail="injury"), names, {})
    assert p["title"] == "طلع إدين دجيكو مصاب" and p["body"] == "الدقيقة 63' · شالكه 1 - 0 فرايبورج" and p["kind"] == "subout"
    p = PP.payload("end", dict(d, status="finished"), "15403", None, names, {"min": 78, "g": 1, "a": 0, "r": 7.9})
    assert p["title"] == "انتهت: شالكه 1 - 0 فرايبورج" and p["body"] == "إدين دجيكو لعب 78 دقيقة، وسجّل هدف واحد · تقييمه 7.9"
    assert p["url"] == "/p/15403/#m5"
    p = PP.payload("soon", d, "15403", None, names, {"cc": {"AE": "beIN SPORTS 1"}})
    assert p["title"] == "إدين دجيكو يلعب بعد ساعة" and p["cc_body"] == {"AE": "شالكه - فرايبورج · الدوري الألماني · beIN SPORTS 1"}
    assert "undefined" not in p["body"] and "None" not in p["body"]
    for k in PP.KINDS:
        s = str(PP.payload(k, d, "15403", ev_("yellow", 40, 15403), names, {"min": 9, "g": 0, "a": 0, "r": None, "cc": {}}))
        assert not any(w in s for w in ("وش", "مين", "زي", "تبي", "<TBD>", "None")), k
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd saas/football && python -m pytest -q tests/test_pushplayer.py`
Expected: FAIL (`No module named 'pushplayer'`).

- [ ] **Step 3: Implement `pushplayer.py`**

```python
"""«تابع اللاعب» phase 1 (docs/superpowers/specs/2026-10-09-player-follow-design.md §2 A): the match-time events of the
followed players in one match detail, and their Arabic payloads. Pure: push.plan() calls it with the followed players
(state/push_players.json, written by pushplayers.py) and hands the jobs to the same sender. Goals and assists are not here:
push.plan() adds the scorer's and the assister's audiences to the team goal job itself, so a device that follows both the
team and the scorer gets one push (spec §5)."""
from timeutil import parse_utc

import push as P

KINDS = ("soon", "start11", "squad_out", "subin", "subout", "goal", "assist", "card", "pen", "end", "potm", "video")
DEFAULTS = ("start11", "subin", "goal", "assist", "card", "end")
SOON = (50, 70)                       # «مباراته بعد ساعة»: once, while kickoff is 50-70 minutes away
CARDS = {"yellow": "إنذار لـ{n}", "second_yellow": "طرد! إنذار ثاني لـ{n}", "red": "طرد! بطاقة حمراء لـ{n}"}


def _pid(x):
    return str((x or {}).get("id") or "")


def lineup(full):
    lu = full.get("lineups") or {}
    out = {"start": {}, "bench": {}, "confirmed": lu.get("type") == "standard"}
    for side in ("home", "away"):
        s = lu.get(side) or {}
        for p in s.get("starters") or []:
            out["start"][_pid(p)] = side
        for p in s.get("subs") or []:
            out["bench"][_pid(p)] = side
    return out


def _rating(full, pid):
    lu = full.get("lineups") or {}
    for side in ("home", "away"):
        for p in ((lu.get(side) or {}).get("starters") or []) + ((lu.get(side) or {}).get("subs") or []):
            if _pid(p) == pid:
                return p.get("rating")
    return None


def minutes_played(full, pid, end_minute):
    """Starter: until he went off (or the end); substitute: from when he came on. None when he did not play."""
    L, evs = lineup(full), full.get("events") or []
    on = next((P.total_minute(e.get("minute"), e.get("added")) for e in evs if e.get("type") == "sub" and _pid(e.get("player")) == pid), None)
    off = next((P.total_minute(e.get("minute"), e.get("added")) for e in evs if e.get("type") == "sub" and _pid(e.get("player_out")) == pid), None)
    if pid in L["start"]:
        return int(off if off is not None else end_minute)
    if on is not None:
        return int((off if off is not None else end_minute) - on)
    return None


def _fresh(e, now, now_min):
    if P._age_min(e.get("first_seen"), now) > P.FRESH_MINUTES:
        return False
    mn = P.total_minute(e.get("minute"), e.get("added"))
    return not (now_min is not None and mn is not None and now_min - mn > P.STALE_MINUTES)


def events_for(d, full, followed, sent, now):
    """[(key, kind, pid, event | None, extra)] not in `sent`. followed: {pid: {"club", "national"}}."""
    if not followed:
        return []
    sent, out = set(sent or []), []
    teams = {(d.get("home") or {}).get("id"), (d.get("away") or {}).get("id")} - {None}
    mine = {pid for pid, t in followed.items() if t and ({t.get("club"), t.get("national")} - {None}) & teams}
    st, L = d.get("status"), lineup(full)
    ko = parse_utc(d.get("kickoff_utc"))

    def add(key, kind, pid, e=None, extra=None):
        if key not in sent:
            out.append((key, kind, pid, e, extra or {}))
    if st == "scheduled" and ko:
        to_ko = (ko - now).total_seconds() / 60
        if SOON[0] <= to_ko <= SOON[1]:
            for pid in sorted(mine):
                add(f"p{pid}:soon", "soon", pid)
    near = st == "scheduled" or (st in ("live", "ht") and P._age_min(d.get("kickoff_utc"), now) <= P.KICKOFF_WINDOW)
    if L["confirmed"] and near:
        for pid in sorted(followed):
            if pid in L["start"]:
                add(f"p{pid}:start11", "start11", pid)
            elif pid in mine and pid not in L["bench"]:
                add(f"p{pid}:squad_out", "squad_out", pid)
    evs = full.get("events") or []
    now_min = P._match_minute(d, evs)
    for e in evs:
        t = e.get("type")
        if t not in ("sub", "yellow", "second_yellow", "red", "missed_penalty") or not _fresh(e, now, now_min):
            continue
        pin, pout = _pid(e.get("player")), _pid(e.get("player_out"))
        if t == "sub":
            if pin in followed:
                add(f"p{pin}:subin", "subin", pin, e)
            if pout in followed:
                add(f"p{pout}:subout", "subout", pout, e)
        elif t == "missed_penalty" and pin in followed:
            add(f"p{pin}:pen:{P.total_minute(e.get('minute'), e.get('added'))}", "pen", pin, e)
        elif pin in followed:
            add(f"p{pin}:card:{t}", "card", pin, e)
    if st == "finished" and P._age_min((d.get("periods") or {}).get("gameEnded"), now) <= P.END_WINDOW:
        end_min = max(90, now_min or 90)
        goals = [e for e in evs if e.get("type") in ("goal", "penalty_goal")]
        for pid in sorted(followed):
            m = minutes_played(full, pid, end_min)
            if m is None:
                continue
            add(f"p{pid}:end", "end", pid, None, {"min": m, "r": _rating(full, pid),
                                                   "g": sum(1 for e in goals if _pid(e.get("player")) == pid),
                                                   "a": sum(1 for e in goals if _pid(e.get("assist")) == pid)})
        rated = [(r, pid) for pid in list(L["start"]) + list(L["bench"]) for r in [_rating(full, pid)] if r is not None]
        if rated:
            best = max(rated)[1]
            if best in followed:
                add(f"p{best}:potm", "potm", best, None, {"r": max(rated)[0]})
    return out


GAMES_MIN = ["دقيقة", "دقيقتين", "دقايق", "وحدة"]
GOALS = ["هدف", "هدفين", "أهداف", "واحد"]


def _count(k, w):
    return f"{w[0]} {w[3]}" if k == 1 else w[1] if k == 2 else f"{k} {w[2] if k <= 10 else w[0]}"


def payload(kind, d, pid, e, names_ar, extra):
    """{title, body, url, tag, kind} (+ cc_body for «soon»: the visitor's channel line by country)."""
    mid, h, a = d["id"], P._name(d.get("home")), P._name(d.get("away"))
    n = P.player_ar({"id": pid, "name": (e or {}).get("player", {}).get("name") if _pid((e or {}).get("player")) == pid else ""}, names_ar) \
        or (names_ar.get(pid) or {}).get("ar") or "لاعبك"
    sc = P._score(d.get("score"))
    mn = f"الدقيقة {P._minute(e)}'" if e else ""
    base = {"url": f"/m/{mid}/", "tag": f"p{pid}-{mid}", "kind": kind}
    if kind == "soon":
        line = f"{h} - {a}" + (f" · {d['comp_name_ar']}" if d.get("comp_name_ar") else "")
        cc = {c: f"{line} · {ch}" for c, ch in ((extra or {}).get("cc") or {}).items() if ch}
        return {**base, "title": f"{n} يلعب بعد ساعة", "body": line, **({"cc_body": cc} if cc else {})}
    if kind == "start11":
        return {**base, "title": f"{n} أساسي", "body": f"{h} - {a}"}
    if kind == "squad_out":
        return {**base, "title": f"{n} مب في القائمة", "body": f"{h} - {a}"}
    if kind == "subin":
        return {**base, "title": f"دخل {n}", "body": f"{mn} · {h} {sc} {a}"}
    if kind == "subout":
        hurt = " مصاب" if (e or {}).get("detail") == "injury" else ""
        return {**base, "title": f"طلع {n}{hurt}", "body": f"{mn} · {h} {sc} {a}"}
    if kind == "card":
        return {**base, "title": CARDS.get((e or {}).get("type"), "بطاقة لـ{n}").format(n=n), "body": f"{mn} · {h} {sc} {a}"}
    if kind == "pen":
        return {**base, "title": f"{n} ضيّع ركلة جزاء", "body": f"{mn} · {h} {sc} {a}"}
    if kind == "end":
        x = extra or {}
        did = [s for s in (x.get("g") and "سجّل " + _count(x["g"], GOALS), x.get("a") and "صنع " + _count(x["a"], GOALS)) if s]
        r = f" · تقييمه {x['r']}" if x.get("r") is not None else ""
        return {**base, "url": f"/p/{pid}/#m{mid}", "title": f"انتهت: {h} {sc} {a}",
                "body": f"{n} لعب {_count(int(x.get('min') or 0), GAMES_MIN)}{'، و' + ' و'.join(did) if did else ''}{r}"}
    if kind == "potm":
        return {**base, "url": f"/p/{pid}/#m{mid}", "title": f"{n} أحسن لاعب في المباراة", "body": f"تقييمه {(extra or {}).get('r')} · {h} {sc} {a}"}
    if kind in ("goal", "assist", "video"):          # built by push.py inside the team jobs; here only for completeness
        return {**base, "title": f"{n}", "body": f"{h} {sc} {a}"}
    return {**base, "title": n, "body": f"{h} - {a}"}
```

- [ ] **Step 4: Run the tests**

Run: `cd saas/football && python -m pytest -q tests/test_pushplayer.py`
Expected: PASS. Fix any copy mismatch in the module, never in the test's Arabic.

- [ ] **Step 5: Commit**

```bash
git add pushplayer.py tests/test_pushplayer.py
git commit -m "push: the match-time events of followed players and their payloads (pushplayer.py)"
```

---

### Task 4: `push.py`: hand player events over, one push per endpoint, the daily cap, the channel by country

**Files:**
- Modify: `saas/football/push.py` (`EVENTS`, `JOB_TTL`, `plan`, `video_jobs`, `run_jobs`; new `cap_ok`)
- Test: `saas/football/tests/test_push.py`

**Interfaces:**
- Consumes: `pushplayer.events_for`, `pushplayer.payload`; `p.aux("push_players")` = `{pid: {"club", "national", "cc"?}}`; `p.aux("guide_cc")` is NOT used: the channel comes from `v1/guide/<iso2>.json` read through `p.store.get_json` (Step 3).
- Produces: jobs whose `payloads` may hold `"P<pid>"` audiences with `kind` (per-audience event) and `cc_body`; `run_jobs` sends each endpoint once per job, player audiences first; `cap_ok(table, sk, day, cap=PLAYER_DAILY_CAP) -> bool`.

- [ ] **Step 1: Write the failing tests**

```python
def _fake_table():
    class T:
        def __init__(s): s.items = {}
        def put_item(s, Item, ConditionExpression=None):
            k = (Item["pk"], Item["sk"])
            if ConditionExpression and k in s.items: raise Exception("ConditionalCheckFailedException")
            s.items[k] = dict(Item)
        def update_item(s, Key, UpdateExpression, ExpressionAttributeValues, ConditionExpression=None, **kw):
            k = (Key["pk"], Key["sk"]); it = s.items.setdefault(k, {**Key, "n": 0})
            if ConditionExpression and it["n"] >= ExpressionAttributeValues[":cap"]: raise Exception("ConditionalCheckFailedException")
            it["n"] += 1
        def delete_item(s, Key): s.items.pop((Key["pk"], Key["sk"]), None)
        def query(s, **kw): return {"Items": []}
    return T()


def test_a_goal_reaches_a_device_once_with_the_players_text():
    sub = {"pk": "x", "sk": "dev1", "endpoint": "https://fcm.googleapis.com/fcm/send/1", "events": ["goal"]}
    sent = []
    job = {"match": 5, "key": "goal:1-0", "kind": "goal", "urgency": "high", "exp": 2e9, "min": 30,
           "payloads": {"10189": {"title": "هدف! شالكه 1 - 0 فرايبورج", "body": "team"},
                        "P15403": {"title": "هدف! إدين دجيكو", "body": "player", "kind": "goal"}}}
    def subs(table, aud): return [sub]
    import push as P
    orig = P._subs; P._subs = subs
    try:
        rep = P.run_jobs([job], _fake_table(), send=lambda s, d, u: sent.append(d["body"]) or "ok")
    finally:
        P._subs = orig
    assert sent == ["player"] and rep[0]["ok"] == 1


def test_assist_audience_uses_its_own_event_choice():
    import push as P
    sub_no = {"pk": "x", "sk": "a", "endpoint": "https://fcm.googleapis.com/fcm/send/a", "events": ["goal"]}
    sub_yes = {"pk": "x", "sk": "b", "endpoint": "https://fcm.googleapis.com/fcm/send/b", "events": ["assist"]}
    job = {"match": 5, "key": "goal:1-0", "kind": "goal", "urgency": "high", "exp": 2e9,
           "payloads": {"P9": {"title": "صناعة! سالم", "body": "a", "kind": "assist"}}}
    sent = []
    orig = P._subs; P._subs = lambda t, a: [sub_no, sub_yes]
    try:
        P.run_jobs([job], _fake_table(), send=lambda s, d, u: sent.append(s["sk"]) or "ok")
    finally:
        P._subs = orig
    assert sent == ["b"]


def test_player_daily_cap_and_channel_by_country():
    import push as P
    t = _fake_table()
    assert all(P.cap_ok(t, "dev1", "2026-10-11", cap=2) for _ in range(2)) and not P.cap_ok(t, "dev1", "2026-10-11", cap=2)
    sub = {"pk": "x", "sk": "dev2", "endpoint": "https://fcm.googleapis.com/fcm/send/2", "events": ["soon"], "cc": "AE"}
    sub2 = dict(sub, sk="dev3", endpoint="https://fcm.googleapis.com/fcm/send/3", cc="BH")
    job = {"match": 5, "key": "p15403:soon", "kind": "soon", "urgency": "normal", "exp": 2e9,
           "payloads": {"P15403": {"title": "إدين دجيكو يلعب بعد ساعة", "body": "شالكه - فرايبورج", "kind": "soon",
                                   "cc_body": {"AE": "شالكه - فرايبورج · beIN SPORTS 1"}}}}
    got = []
    orig = P._subs; P._subs = lambda tb, a: [sub, sub2]
    try:
        P.run_jobs([job], t, send=lambda s, d, u: got.append((s["sk"], d["body"], "cc_body" in d, "kind" in d)) or "ok")
    finally:
        P._subs = orig
    assert got == [("dev2", "شالكه - فرايبورج · beIN SPORTS 1", False, False), ("dev3", "شالكه - فرايبورج", False, False)]
```

and, for `plan()` (with the poller fake already used in this file: reuse its `Pz`/fake poller helper; if the file builds its poller inline, build one the same way and set `p.aux("push_players")` to `{"15403": {"club": 10189, "national": None}}`):

```python
def test_plan_adds_player_audiences_to_goal_jobs_and_player_jobs(monkeypatch, tmp_path):
    import push as P
    monkeypatch.setattr(P, "_names_ar", lambda: {"15403": {"ar": "إدين دجيكو"}})
    p = _poller(tmp_path)                                          # the file's existing fake poller
    p.aux("push_players").update({"15403": {"club": 10189, "national": None}})
    d, full = _goal_detail(scorer=15403, assist=None)              # the file's existing goal fixture builder, live, 1-0
    jobs = P.plan(p, d, full, invoke=lambda ev: None)
    goal = next(j for j in jobs if j["kind"] == "goal")
    assert "P15403" in goal["payloads"] and goal["payloads"]["P15403"]["kind"] == "goal"
    assert list(goal["payloads"])[0] == "P15403"                   # player audiences first
```

If `tests/test_push.py` has no `_poller`/`_goal_detail` helpers, write them at the top of the new tests from the fixture `tests/fixtures/fotmob_match_live_ht_6052047.json` exactly as the existing plan() tests construct their detail (read them first; the names here are the plan's, adapt to the file).

- [ ] **Step 2: Run them to see them fail**

Run: `cd saas/football && python -m pytest -q tests/test_push.py -k "player or assist or cap"`
Expected: FAIL.

- [ ] **Step 3: Implement**

In `push.py`:

```python
import pushplayer as PP      # top, after `import json, os, re, time`

TEAM_EVENTS = ("start", "goal", "end", "video")
EVENTS = TEAM_EVENTS + tuple(k for k in PP.KINDS if k not in TEAM_EVENTS)
JOB_TTL = {"start": 600, "goal": 600, "end": 900, "video": 1800, "soon": 1800, "start11": 1800, "squad_out": 1800,
           "subin": 600, "subout": 600, "assist": 600, "card": 600, "pen": 600, "potm": 3600}
PLAYER_DAILY_CAP = 20         # player alerts per device per UAE day (owner 2026-10-09: «اذا تشوف اشياء تسوي مشاكل»)
```

`cap_ok`:

```python
def cap_ok(table, sk, day, cap=PLAYER_DAILY_CAP):
    """One more player alert for this device today? A conditional counter TIFOPUSHCAP#<device>/<UAE day>, kept 3 days."""
    try:
        table.update_item(Key={"pk": f"TIFOPUSHCAP#{sk}", "sk": day}, UpdateExpression="ADD n :one SET #t = :ttl",
                          ConditionExpression="attribute_not_exists(n) OR n < :cap", ExpressionAttributeNames={"#t": "ttl"},
                          ExpressionAttributeValues={":one": 1, ":cap": cap, ":ttl": int(time.time()) + 3 * 86400})
        return True
    except Exception as ex:
        if _conditional_failed(table, ex):
            return False
        raise
```

In `plan()`, after `todo = events_to_send(...)` (and before `if not todo: return []`), add the player part:

```python
    followed = p.aux("push_players") if hasattr(p, "aux") else {}
    pev = PP.events_for(d, full, followed, sent["keys"], p.now()) if followed else []
    if not todo and not pev:
        return []
```

(and remove the old `if not todo: return []`). After `jobs = [...]` (the team jobs), add the scorer and assister to each goal job, players first, then the player jobs:

```python
    for j, (key, kind, e, mn, again) in zip(jobs, todo):
        if kind != "goal" or not e:
            continue
        aud = {}
        for role, who in (("goal", e.get("player")), ("assist", e.get("assist"))):
            pid = str((who or {}).get("id") or "")
            if pid and pid in followed:
                n = player_ar(who, names_ar) or pid
                t = f"هدف! {n}" if role == "goal" else f"صناعة! {n}"
                aud[f"P{pid}"] = {"title": t, "body": f"{_name(d.get('home'))} {_score(e.get('score') or d.get('score'))} {_name(d.get('away'))} · الدقيقة {_minute(e)}'",
                                  "url": f"/m/{mid}/", "tag": f"p{pid}-{mid}", "kind": role}
        if aud:
            j["payloads"] = {**aud, **j["payloads"]}
    cc_of = _channels(p, d) if any(kind == "soon" for _, kind, _, _, _ in pev) else {}
    for key, kind, pid, e, extra in pev:
        x = dict(extra, cc=cc_of) if kind == "soon" else extra
        jobs.append(_job(mid, key, kind, {f"P{pid}": PP.payload(kind, d, pid, e, names_ar, x)}))
```

`names_ar = _names_ar()` must be set before the player part (move it above `todo` handling). `_channels`:

```python
def _channels(p, d):
    """{ISO2: channel} for this match from v1/guide/<iso2>.json (pages «وين أشوف»), for the countries players' followers
    are in; a country with no row gives nothing (the push then has no channel line, never a guess)."""
    out = {}
    for cc in {str(v.get("cc") or "").upper() for v in (p.aux("push_players") or {}).values() if v.get("cc")}:
        g = p.store.get_json(f"guide/{cc.lower()}.json") or {}
        row = next((m for m in g.get("matches") or [] if str(m.get("id")) == str(d["id"])), None)
        ch = row and row.get("channel_known") and (row.get("channel_ar") or (row.get("broadcasters") or [None])[0])
        if ch:
            out[cc] = ch
    return out
```

(Read `docs/SCHEMA.md` § `guide/{iso2}.json` and one real file to fix the key names `matches`/`id`/`channel_ar` before this step; adjust only these three names.)

In `run_jobs`, replace the inner loop over payloads:

```python
        for aud, data in sorted(job["payloads"].items(), key=lambda kv: not str(kv[0]).startswith("P")):
            k = data.get("kind") or kind
            is_player = str(aud).startswith("P")
            subs = subs_override if subs_override is not None else _subs(table, aud)
            for s in subs:
                if not wants(s, k) or s["endpoint"] in done_eps:
                    continue
                if in_quiet(s, t):
                    done_eps.add(s["endpoint"])
                    stats["quiet"] += 1
                    continue
                if n >= MAX_SENDS:
                    break
                if is_player and subs_override is None and not cap_ok(table, s["sk"], time.strftime("%Y-%m-%d", time.gmtime(t + 4 * 3600))):
                    stats.setdefault("capped", 0); stats["capped"] += 1
                    continue
                done_eps.add(s["endpoint"])
                body = (data.get("cc_body") or {}).get(str(s.get("cc") or "").upper()) or data["body"]
                out = {kk: vv for kk, vv in data.items() if kk not in ("kind", "cc_body")}
                out["body"] = body
                r = send(s, out, job["urgency"], JOB_TTL.get(k, 600)) if with_ttl else send(s, out, job["urgency"])
                # from here the existing lines stay as they are: n += 1, then ok / gone (delete the subscription) / error (log)
```

`video_jobs`: add the scorer's audience like the goal job (kind `video`, title «فيديو هدف <name> نزل», url the same `#v=` link), players first.

`wants()` is unchanged: a player subscription stores player kinds, a team one team kinds; `goal`/`video`/`end` exist in both lists and mean the same thing.

- [ ] **Step 4: Run all push tests**

Run: `cd saas/football && python -m pytest -q tests/test_push.py tests/test_push_dedupe.py tests/test_pushplayer.py`
Expected: PASS (the existing dedupe tests prove team behaviour is unchanged).

- [ ] **Step 5: Commit**

```bash
git add push.py tests/test_push.py
git commit -m "push: player audiences (one push per device, player text first), a daily cap per device, the channel by country"
```

---

### Task 5: Poller: plan on prematch details; `pushplayers.py`: the followed players' teams

**Files:**
- Modify: `saas/football/poller.py:489` (the `PUSH.plan` condition)
- Create: `saas/football/pushplayers.py`
- Modify: `saas/football/tools/runner.py` (`job_journal`)
- Test: `saas/football/tests/test_pushplayer.py` (map builder)

**Interfaces:**
- Consumes: DynamoDB `cards` `TIFOFOLLOW` items (Task 2); `v1/player/<id>/profile.json` through the data CloudFront.
- Produces: `state/push_players.json` = `{pid: {"club": int|None, "national": int|None, "cc": None}}` (cc stays None in phase 1: the channel line is chosen per subscription by the sender; `cc` here is reserved for phase 3's «لاعبيني»), written with `Store.put_state`. `build_map(follow_ids, get_profile) -> dict` pure.

- [ ] **Step 1: Write the failing test**

```python
def test_map_from_profiles():
    import pushplayers as M
    prof = {"15403": {"bio": {"team": 10189}, "career": {"national team": {"seasons": [["2024", 8, "Bosnia", 3, 0, 0]]}}},
            "2777": {"bio": {"team": 49678}, "career": {}}, "5": None}
    m = M.build_map(["15403", "2777", "5"], lambda pid: prof.get(pid))
    assert m == {"15403": {"club": 10189, "national": 8, "cc": None}, "2777": {"club": 49678, "national": None, "cc": None},
                 "5": {"club": None, "national": None, "cc": None}}
    old = {"seasons": [["2019", 8, "Bosnia", 3, 0, 0]]}
    assert M.national_of({"career": {"national team": old}}) is None          # more than 3 years without a cap
```

- [ ] **Step 2: Run it to see it fail**

Run: `python -m pytest -q tests/test_pushplayer.py -k map` → FAIL.

- [ ] **Step 3: Implement**

`pushplayers.py`:

```python
"""«تابع اللاعب»: the followed players' club and national team, for the poller (state/push_players.json). Runs with the
journal (every 15 min, laptop): the follow index TIFOFOLLOW (cards API, Task 2) -> each player's profile.json -> the map.
  python -m pushplayers"""
import json, os, time, urllib.request

YEAR = int(time.strftime("%Y"))
DATA = os.environ.get("TIFO_DATA", "https://d1n5aqaqkowltp.cloudfront.net")
BUCKET = os.environ.get("BUCKET", "elyoxe-football-574771023173-ap-south-1")


def national_of(prof):
    s = (((prof or {}).get("career") or {}).get("national team") or {}).get("seasons") or []
    if not s:
        return None
    try:
        recent = YEAR - int(str(s[0][0])[:4]) <= 3
    except ValueError:
        recent = False
    return int(s[0][1]) if recent and s[0][1] else None


def build_map(ids, get_profile):
    out = {}
    for pid in ids:
        p = get_profile(pid) or {}
        club = (p.get("bio") or {}).get("team")
        out[pid] = {"club": int(club) if club else None, "national": national_of(p), "cc": None}
    return out


def _profile(pid):
    try:
        with urllib.request.urlopen(f"{DATA}/player/{pid}/profile.json", timeout=20) as r:
            raw = r.read()
            if raw[:2] == b"\x1f\x8b":
                import gzip
                raw = gzip.decompress(raw)
            return json.loads(raw)
    except Exception:
        return None


def followed_ids(table):
    from boto3.dynamodb.conditions import Key
    items, kw = [], {"KeyConditionExpression": Key("pk").eq("TIFOFOLLOW")}
    while True:
        r = table.query(**kw); items += r.get("Items") or []
        if not r.get("LastEvaluatedKey"):
            return sorted(str(i["sk"])[1:] for i in items if int(i.get("n", 0)) > 0)
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def main():
    import boto3
    from store import Store
    ids = followed_ids(boto3.resource("dynamodb", region_name="ap-south-1").Table("cards"))
    m = build_map(ids, _profile)
    Store(BUCKET).put_state("push_players.json", m)
    print(json.dumps({"followed": len(ids), "mapped": sum(1 for v in m.values() if v["club"] or v["national"])}))


if __name__ == "__main__":
    main()
```

(Check `Store(BUCKET)`'s constructor in store.py first; if it needs a client or a local flag, pass what news/run.py passes.)

`tools/runner.py` `job_journal`: after `news.run`, run the map (never fatal):

```python
    rc2, tail2 = run(log, [PY, "-m", "pushplayers"], timeout=5 * 60)
    if rc2:
        log.w(f"pushplayers exit {rc2} (not fatal)")
```

`poller.py`: let `plan()` see prematch details too:

```python
        if d["status"] in S.LIVE_STATUSES or d["status"] == S.FINISHED or (d["status"] == S.SCHEDULED and why == "prematch"):
```

(`events_to_send` sends nothing for a scheduled match: its «start» needs a live status; only the player part acts.)

- [ ] **Step 4: Run the football suite**

Run: `cd saas/football && python -m pytest -q tests`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pushplayers.py poller.py tools/runner.py tests/test_pushplayer.py
git commit -m "push: the followed players' teams every 15 min (pushplayers.py); the poller plans on prematch details for lineups"
```

---

### Task 6: The client: «تابع اللاعب», its sheet, the match line on his page

**Files:**
- Modify: `saas/football/site/src/notify.js` (player functions)
- Modify: `saas/football/site/src/v5/pages.js` (`P.player` header button + sheet)
- Modify: `saas/football/site/src/v5/app.js` (`#m<mid>` opens his line for that match)
- Modify: `saas/football/site/build.cjs` (load notify.js on `player` pages)
- Test: `saas/football/tests/test_engagement_ui.py`, `saas/football/tests/test_player_seo.py`

**Interfaces:**
- Produces (notify.js): `TifoNotify.playerSheet({id, name}) -> html`, `TifoNotify.playerBody({id, name}) -> html`, `TifoNotify.setPlayer(pid, events) -> Promise`, `TifoNotify.playerState(pid) -> {events}`; storage `localStorage tifo.push.players = {pid: [events]}`; `POST /api/tifo/push/sub {player, events, quiet, cc, subscription}`; event `tifo:notify-player {player, events}`.
- Groups in the sheet: «قبل المباراة» (soon, start11, squad_out) · «في المباراة» (subin, subout, goal, assist, card, pen) · «بعد المباراة» (end, potm, video). Defaults ticked: `start11, subin, goal, assist, card, end`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_engagement_ui.py`, extend `SCRIPT`'s printed object with `pnf: N.playerBody({id: 15403, name: 'إدين <b>'}), pnfSheet: N.playerSheet({id: 1, name: 'x'})`, then:

```python
def test_player_sheet(out):
    h = out["pnf"]
    assert 'data-nf-player="15403"' in h and "إدين &lt;b&gt;" in h
    for k in ("soon", "start11", "squad_out", "subin", "subout", "goal", "assist", "card", "pen", "end", "potm", "video"):
        assert f'data-pe="{k}"' in h, k
    for k in ("start11", "subin", "goal", "assist", "card", "end"):
        assert re.search(rf'data-pe="{k}"[^>]*aria-checked="true"', h), k      # the owner's defaults
    for k in ("soon", "squad_out", "subout", "pen", "potm", "video"):
        assert re.search(rf'data-pe="{k}"[^>]*aria-checked="false"', h), k
    assert 'id="sh-pnotify"' in out["pnfSheet"]
```

In `tests/test_player_seo.py` `PAGE`, the `full` render must carry the button: assert `'data-sheet="sh-pnotify"' in h and "تابع اللاعب" in h`.

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest -q tests/test_engagement_ui.py tests/test_player_seo.py` → FAIL.

- [ ] **Step 3: Implement**

`notify.js` (inside the IIFE, next to `body`/`sheet`; export the four new names where `body`/`sheet` are exported):

```js
  var PGROUPS = [["قبل المباراة", [["soon", "مباراته بعد ساعة"], ["start11", "أساسي"], ["squad_out", "مب في القائمة"]]],
    ["في المباراة", [["subin", "دخل بديل"], ["subout", "طلع تبديل"], ["goal", "هدف"], ["assist", "صناعة"], ["card", "بطاقة"], ["pen", "ضيّع ركلة جزاء"]]],
    ["بعد المباراة", [["end", "دقايقه وأرقامه"], ["potm", "أحسن لاعب في المباراة"], ["video", "فيديو هدفه"]]]];
  var PDEF = ["start11", "subin", "goal", "assist", "card", "end"];
  function pst() { try { return JSON.parse(ls.get("tifo.push.players") || "{}"); } catch (e) { return {}; } }
  function playerState(pid) { var ev = pst()[pid]; return { events: ev ? ev.slice() : null }; }
  function playerBody(p) {
    var on = (playerState(p.id).events || PDEF);
    return '<div data-nf-player="' + esc(p.id) + '"><p class="note">تنبيه على جوالك عن ' + esc(p.name) + " مع ناديه ومنتخبه، بدون حساب:</p>" +
      PGROUPS.map(function (g) { return '<section class="grp"><div class="gh"><h2>' + g[0] + '</h2></div><div class="card">' + g[1].map(function (x) {
        var c = on.indexOf(x[0]) >= 0; return '<button type="button" class="row" data-pe="' + x[0] + '" role="switch" aria-checked="' + c + '"><span class="rt">' + x[1] + '</span><span class="sw" aria-hidden="true"></span></button>'; }).join("") + "</div></section>"; }).join("") +
      '<p class="gf" data-nf-msg role="status"></p></div>';
  }
  function playerSheet(p) { return '<dialog class="sheet" id="sh-pnotify" aria-labelledby="sh-pnotify-t"><div class="sh-grab"></div><div class="sh-hd"><h2 id="sh-pnotify-t">تابع ' + esc(p.name) + '</h2><button type="button" class="sh-x" data-close aria-label="سكّر">✕</button></div><div class="sh-bd">' + playerBody(p) + "</div></dialog>"; }
  function country() { return (ls.get("tifo.country") || "").toUpperCase(); }
  function wireP(pid, ev) {
    var send = ev.filter(function (x) { return !nospoil() || x === "start11" || x === "soon"; }), s = st();
    if (!send.length) return subscription(false).then(function (x) { if (x) return post("DELETE", { player: +pid, endpoint: x.endpoint }); });
    return subscription(true).then(function (x) { var q = s.quiet ? { s: s.quiet.s, e: s.quiet.e, o: offset() } : null;
      return post("POST", { player: +pid, events: send, quiet: q, cc: country() || null, subscription: x.toJSON() }); });
  }
  function setPlayer(pid, events) {
    var all = PGROUPS.reduce(function (a, g) { return a.concat(g[1].map(function (x) { return x[0]; })); }, []);
    var ev = events.filter(function (x, i) { return all.indexOf(x) >= 0 && events.indexOf(x) === i; }), go = permit();
    return go.then(function () { var s = pst(); if (ev.length) s[pid] = ev; else delete s[pid]; ls.set("tifo.push.players", JSON.stringify(s));
      D.dispatchEvent(new CustomEvent("tifo:notify-player", { detail: { player: +pid, events: ev } })); return wireP(pid, ev); });
  }
```

Wire the switches in the existing click handler (`onClick`): a `[data-pe]` inside `[data-nf-player]` toggles `aria-checked`, collects the checked keys of that block and calls `setPlayer(block.dataset.nfPlayer, keys)` with the same `say()/fail()` messages as teams («تمام، بتوصلك التنبيهات.» / «وقّفنا تنبيهات هاللاعب.»). `resync()` also re-sends `pst()` entries through `wireP` (so «بدون حرق» and quiet hours reach players).

`pages.js` `P.player`: in the `follow` block, after the team pill, add (only when `x.follow`):

```js
'<button type="button" class="pill" data-sheet="sh-pnotify">' + I("bell", "", 2) + "<span>تابع اللاعب</span></button>"
```

and in the returned `sheets`, append `(x && x.follow && root.TifoNotify ? "" : "")` — the sheet itself is added by build.cjs (Step below) so pages.js stays free of notify.js.

`build.cjs` player page: add the sheet to `v5.sheets` and load the script:

```js
    v5.sheets = (v5.sheets || "") + (ENG.notifyMod ? ENG.notifyMod.playerSheet({ id, name: nm }) : "");
```

(`ENG.notifyMod` = `require("./src/notify.js")`, set where `ENG.notify` is resolved; read that block first.) In the `<script>` list, change `["team", "match"].includes(o.page)` for `ENG.notify` to `["team", "match", "player"]`.

`app.js`: on a player page, `#m<mid>` (the «انتهت» push opens it) opens the «المباريات» pane and scrolls to that match's row in `#plm` (rows link `/m/<mid>/`), adding the class `hl`; the page's «صورة لأي قسم» makes the image. In `deepLink()`, before the segment logic:

```js
    var mm = /^m(\d{3,12})$/.exec(h); if (mm && PG === "player") { var sg = $('.seg[data-seg="p"]'); if (sg) selectSeg(sg, "mt", false);
      setTimeout(function () { var a = $('#plm a[href*="/' + mm[1] + '/"], #plm a[href*="id=' + mm[1] + '"]'); if (a) { a.classList.add("hl"); a.scrollIntoView({ block: "center" }); } }, 900); return; }
```

- [ ] **Step 4: Run the tests and a limited build**

Run: `cd saas/football && python -m pytest -q tests/test_engagement_ui.py tests/test_player_seo.py && node --check site/src/notify.js site/src/v5/pages.js site/src/v5/app.js site/build.cjs`
Then (worktree, Git Bash): `MSYS_NO_PATHCONV=1 TIFO_ONLY='^/p/(15403|2777)/' TIFO_WORLD=0 TIFO_FETCH_CACHE="$TEMP/tifo-fc" node site/build.cjs --out out-test` and check `out-test/p/15403/index.html` has `id="sh-pnotify"`, `data-sheet="sh-pnotify"` and the notify.js `<script>`.
Expected: PASS; both markers present.

- [ ] **Step 5: Commit**

```bash
git add site/src/notify.js site/src/v5/pages.js site/src/v5/app.js site/build.cjs tests/test_engagement_ui.py tests/test_player_seo.py
git commit -m "site: «تابع اللاعب» on player pages (the sheet, his defaults, «بدون حرق»), #m<mid> opens his line for that match"
```

---

### Task 7: Ship, prove on a live match, measure

**Files:**
- Modify: `saas/football/docs/ENGAGEMENT.md` (a «تابع اللاعب» section: events, storage, API, the cap)
- Create: `docs/superpowers/plans/2026-10-09-player-follow-phase1.after.json`

- [ ] **Step 1: Deploy (each needs the owner's «انشر»)**

1. Cards (Fold): `cd /root/workspace/saas/cards && git pull --ff-only origin main && bash deploy.sh`
2. Football Lambdas (poller + sender; the sender's package must include `pushplayer.py`): `cd saas/football && ./deploy.sh` (check `template.yaml`'s CodeUri / deploy.sh's file list includes the new module; add it if the package is an explicit list).
3. The site: merge to `main`; the hourly runner publishes.

- [ ] **Step 2: Prove it on a live match**

Pick a tracked match within 90 minutes and a starter in its predicted lineup. Subscribe a test device with `tools/push_e2e.py` (extend it with `--player <pid>`: the same flow as `--team`, posting `{player}`); watch the sender's log for `p<pid>:soon`, `p<pid>:start11`, then the minute events. Expected: each arrives once; a goal by him arrives once on a device that also follows his team.

- [ ] **Step 3: Measure the poller after 24 h**

Run: `MSYS_NO_PATHCONV=1 python -m tools.poller_time --hours 24 --out docs/superpowers/plans/2026-10-09-player-follow-phase1.after.json`
Expected: p95 within +15 % of the baseline. Above it: stop and report (spec constraint), do not ship phase 2.

- [ ] **Step 4: Document and commit**

```bash
git add docs/ENGAGEMENT.md docs/superpowers/plans/2026-10-09-player-follow-phase1.after.json
git commit -m "docs: «تابع اللاعب» phase 1 (events, storage, the cap, the measured poller time)"
```
