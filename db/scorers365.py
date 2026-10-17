"""Scorers and cards from 365Scores for the finished matches FotMob covers with a score only (the audit's «scorers_missing»:
135 pages on 2026-10-17, Arab Cup qualifiers, Gulf and African ties, national friendlies). Owner 2026-10-17 «أفوضك».
  1. the ids come from the latest audit (state/audit/<date>.json, finding scorers_missing, key `matches`);
  2. each match's sides are mapped to 365Scores through v1/s365/fmmap.json (FotMob team id -> 365 id), the home side's
     results list is paged back to the kickoff date, and the game whose opponent matches is read in full;
  3. its goals (field, penalty, own) and cards become events in FotMob's shape (sources/fotmob._events), Arabic player names
     from 365Scores, no FotMob player id (the page shows the name; the goal-clip key falls back to 0);
  4. the match file is rewritten only when the new goal count is higher than the page's and never above the score per side
     (the audit's «a merge must never add a goal» rule holds: file_goals_exceed_score stays impossible); filled_by records it.
Runs daily after db.matches in db/refresh.py; a later FotMob refetch without events is refilled the next day.
    python -m db.scorers365 [--upload] [--limit 50] [--only <mid,mid>]"""
import argparse, json, re, sys, time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from store import Store, S3Backend, local_store                                   # noqa: E402
from db.scores365 import fetch, QA as Q                                                # noqa: E402  (the gzip file cache, 365's query string)

BUCKET = "elyoxe-football-574771023173-ap-south-1"
GOAL_TYPES = {"goal", "own_goal", "penalty_goal"}


def latest_audit(store):
    today = datetime.now(timezone.utc) + timedelta(hours=4)
    for i in range(0, 4):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        a = store.get_state(f"audit/{d}.json")
        if a:
            return d, a
    return None, None


def low_cov_ids(audit):
    for f in audit.get("findings") or []:
        if f.get("check") == "scorers_missing":
            return [int(x) for x in (f.get("matches") or f.get("examples") or [])]
    return []


def results_until(team365, ymd, maxpages=6):
    """The team's past games back to the date (newest first; 365 pages 12 at a time)."""
    url = f"/web/games/results/?{Q}&competitors={team365}"
    out = []
    for _ in range(maxpages):
        j = fetch(url, 20 * 3600)
        gs = (j or {}).get("games") or []
        out += gs
        if not gs or min((g.get("startTime") or "9")[:10] for g in gs) <= ymd:
            break
        nxt = ((j or {}).get("paging") or {}).get("previousPage")
        if not nxt:
            break
        url = nxt if nxt.startswith("/") else "/" + nxt
    return out


def find_game(md, fm):
    """The 365 game of this match: through whichever side fmmap knows (one is enough: a team plays one game a day), on the
    kickoff date (±1 day for time zones), with the same score the page has (the sides may be listed the other way round).
    Returns (game id, 365 id of OUR home side or None when unknown, reason)."""
    h365, a365 = fm.get(str(md["home"]["id"])), fm.get(str(md["away"]["id"]))
    if not h365 and not a365:
        return None, None, "no 365 id for either side"
    ko = (md.get("kickoff_utc") or "")[:10]
    if not ko:
        return None, None, "no kickoff"
    day = datetime.strptime(ko, "%Y-%m-%d")
    near = {(day + timedelta(days=k)).strftime("%Y-%m-%d") for k in (-1, 0, 1)}
    sc = md["score"]
    known = h365 or a365
    for g in results_until(known, (day - timedelta(days=1)).strftime("%Y-%m-%d")):
        if (g.get("startTime") or "")[:10] not in near:
            continue
        hc, ac = g.get("homeCompetitor") or {}, g.get("awayCompetitor") or {}
        ids = {hc.get("id"), ac.get("id")}
        if h365 and a365 and ids != {h365, a365}:
            continue
        gs = (hc.get("score"), ac.get("score"))
        same = (gs == (sc["home"], sc["away"])) and (known in ids)
        flipped = (gs == (sc["away"], sc["home"])) and (known in ids)
        if not (same or flipped):
            continue
        # our home side on 365: the mapped id if it is the home side there, else the other competitor
        if h365:
            home365 = h365
        else:
            home365 = ac.get("id") if a365 == hc.get("id") else hc.get("id")
        return g["id"], home365, None
    return None, None, "no game on that date with that score"


def convert(game, md, h365):
    """365 events -> FotMob-shaped events: goals with the running score, cards; substitutions are left out."""
    g = game.get("game") or {}
    mem = {m["id"]: m for m in g.get("members") or [] if m.get("id")}
    swapped = (g.get("homeCompetitor") or {}).get("id") != h365       # 365 may list the sides the other way round
    hid, aid = md["home"]["id"], md["away"]["id"]
    out, score = [], {"home": 0, "away": 0}
    for e in sorted(g.get("events") or [], key=lambda e: (float(e.get("gameTime") or 0), e.get("addedTime") or 0)):
        et = (e.get("eventType") or {}).get("id")
        if et not in (1, 2, 3):
            continue
        is_home = (e.get("competitorId") == (g.get("homeCompetitor") or {}).get("id")) != swapped
        side = "home" if is_home else "away"
        name = (mem.get(e.get("playerId")) or {}).get("name")
        sub = ((e.get("eventType") or {}).get("subTypeName") or "").lower()
        mn = int(float(e.get("gameTime") or 0))
        base = {"minute": mn, "added": int(e["addedTime"]) if e.get("addedTime") else None, "team": side, "team_id": hid if is_home else aid,
                "player": {"id": None, "name": name} if name else None, "assist": None, "player_out": None, "score": None, "detail": None}
        if et == 1:
            own = "own" in sub or "عكسي" in sub
            typ = "own_goal" if own else "penalty_goal" if ("penalty" in sub or "جزاء" in sub) else "goal"
            score[side] += 1
            base["score"] = dict(score)
            if typ == "goal" and sub and "ميداني" not in sub and "field" not in sub:
                base["detail"] = (e.get("eventType") or {}).get("subTypeName")
        else:
            typ = "red" if et == 3 and "second" not in sub and "ثاني" not in sub else "second_yellow" if et == 3 else "yellow"
        base["type"] = typ
        base["event_id"] = f"{md['id']}-{typ}-{mn}-{side}-365{(mem.get(e.get('playerId')) or {}).get('athleteId') or 0}"
        out.append(base)
    return out, score


def side_goals(evs):
    s = {"home": 0, "away": 0}
    for e in evs or []:
        if e.get("type") in GOAL_TYPES and e.get("team") in s:
            s[e["team"]] += 1
    return s


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload", action="store_true"); ap.add_argument("--limit", type=int, default=200); ap.add_argument("--only", default="")
    a = ap.parse_args(argv)
    store = Store(S3Backend(BUCKET)) if a.upload else local_store()
    reader = Store(S3Backend(BUCKET))
    date, audit = latest_audit(reader)
    ids = [int(x) for x in a.only.split(",") if x] or low_cov_ids(audit or {})
    fm = ((reader.get_json("s365/fmmap.json") or {}).get("map") or {})
    print(f"audit {date}: {len(ids)} low-coverage matches; fmmap {len(fm)} teams")
    t0, filled, skipped = time.time(), 0, {}
    for mid in ids[: a.limit]:
        md = reader.get_json(f"match/{mid}.json")
        if not md or md.get("status") != "finished" or not md.get("score"):
            skipped["not finished"] = skipped.get("not finished", 0) + 1
            continue
        gid, home365, why = find_game(md, fm)
        if not gid:
            skipped[why] = skipped.get(why, 0) + 1
            continue
        game = fetch(f"/web/game/?{Q}&gameId={gid}", None)        # a finished game is kept for good
        if not game:
            skipped["game 404"] = skipped.get("game 404", 0) + 1
            continue
        evs, got = convert(game, md, home365)
        have, sc = side_goals(md.get("events")), md["score"]
        if got["home"] > sc["home"] or got["away"] > sc["away"]:
            skipped["365 goals exceed the score"] = skipped.get("365 goals exceed the score", 0) + 1
            continue
        if got["home"] + got["away"] <= have["home"] + have["away"]:
            skipped["nothing new"] = skipped.get("nothing new", 0) + 1
            continue
        keep = [e for e in md.get("events") or [] if e.get("type") not in GOAL_TYPES and not e.get("type", "").endswith("yellow") and e.get("type") != "red"]
        md["events"] = sorted(keep + evs, key=lambda e: ((e.get("minute") or 0), (e.get("added") or 0)))
        md["filled_by"] = "365scores:events"
        md["events_source"] = {"name": "365Scores", "game": gid, "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        store.put_json(f"match/{mid}.json", md, cache="static")
        filled += 1
        print(f"  {mid} {md['home']['name']} {sc['home']}-{sc['away']} {md['away']['name']}: {got['home']}+{got['away']} goals, 365 game {gid}")
    print(f"scorers365: {filled} filled, skipped {skipped} in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
