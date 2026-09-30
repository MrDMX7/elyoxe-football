"""Regression tests for the numbers audit's fixes (2026-09-30): re-poll merges, dormant backfill, season labels and
minutes in the player logs, 365Scores' transient errors and placeholders, bracket slots, and the audit's own pairing."""
import gzip, json, os, time

import pytest

import poller as P
from db import audit as AU, matches as DM, scores365 as S365
from sources.fotmob import FotMob, placeholder_ar


# ------------------------------------------------------------------ poller: a re-poll never adds a goal
def _ev(t, minute, team, pid, eid=None):
    return {"type": t, "minute": minute, "added": None, "team": team, "player": {"id": pid, "name": f"p{pid}"},
            "event_id": eid or f"1-{t}-{minute}-0-{pid}"}


def test_corrected_scorer_is_not_kept_twice():
    prev = [_ev("goal", 38, "home", 7)]
    new = [_ev("goal", 37, "home", 7)]                         # FotMob moved the goal a minute (Tunisia v Botswana)
    assert P._kept_events(prev, new, {"home": 1, "away": 0}) == []
    prev = [_ev("own_goal", 5, "away", None)]
    new = [_ev("own_goal", 5, "away", 1345875)]               # the own goal's player named later (Burundi v Algeria)
    assert P._kept_events(prev, new, {"home": 0, "away": 1}) == []


def test_dropped_card_is_kept_but_never_a_goal_beyond_the_score():
    prev = [_ev("yellow", 30, "home", 3), _ev("goal", 10, "home", 9)]
    new = [_ev("goal", 60, "home", 11)]
    kept = P._kept_events(prev, new, {"home": 1, "away": 0})
    assert [e["type"] for e in kept] == ["yellow"]            # the goal count already makes the score
    kept = P._kept_events(prev, new, {"home": 2, "away": 0})
    assert sorted(e["type"] for e in kept) == ["goal", "yellow"]


def test_goal_gap():
    d = {"score": {"home": 0, "away": 2}, "events": [_ev("goal", 50, "away", 4)]}
    assert P._goal_gap(d)                                       # Botswana v Mozambique: 1 event for 2 goals
    d["events"].append(_ev("goal", 90, "away", 5))
    assert not P._goal_gap(d)
    d["events"][0]["player"] = {"id": None, "name": None}
    assert P._goal_gap(d)                                       # a goal with no scorer yet


# ------------------------------------------------------------------ sources: bracket slots
def test_bracket_slot_names():
    assert placeholder_ar("1A") == "أول المجموعة A"
    assert placeholder_ar("3ACD") == "ثالث A/C/D"
    assert placeholder_ar("Winner Semi-final 1") == "الفايز من نص النهائي 1"
    assert placeholder_ar("Al Ain") is None
    t = FotMob(names={"teams": {}})._team(1870, "1A")
    assert t["placeholder"] and t["logo"] is None and t["name_ar"]


# ------------------------------------------------------------------ player logs
def test_season_labels_follow_fotmob():
    assert DM.season_of(1, "2026-06-20", 77, {}, {77}) == "2026"           # World Cup 2026: one season, not two
    assert DM.season_of(2, "2026-07-10", 77, {}, {77}) == "2026"
    assert DM.season_of(3, "2026-03-01", 47, {}, set()) == "2025/2026"
    assert DM.season_of(4, "2024-01-20", 289, {4: "2023"}, {289}) == "2023"  # AFCON 2023 was played in 2024
    assert DM._label("2025 Qatar") == "2025"


def test_minutes_from_lineup_and_scorers_without_lineup():
    m = {"id": 1, "date": "2014-03-01T18:00:00Z", "comp": 538, "home": [1, "A", 2], "away": [2, "B", 1], "ps": {},
         "lineups": {"h": {"players": [[10, "x", 9, 1, 1, None], [11, "y", 10, 1, 0, None]]}, "a": {"players": [[20, "z", 9, 1, 1, None]]}},
         "events": [[60, "s", "h", 11, "y", 10, "x"], [75, "g", "h", 11, "y", None, None], [88, "r", "a", 20, "z", None, "Red"]]}
    L = DM.build_logs([m])
    assert L[10][0][8] == 60 and L[11][0][8] == 30 and L[20][0][8] == 88
    m2 = {"id": 2, "date": "2014-03-01T18:00:00Z", "comp": 538, "home": [1, "A", 1], "away": [2, "B", 0], "ps": {}, "lineups": {},
          "events": [[30, "g", "h", 55, "s", 66, None]]}
    L = DM.build_logs([m2])
    assert L[55][0][9] == 1 and L[66][0][10] == 1                           # scorer and assister still get the match


def test_scorer_id_zero_resolved_from_lineup():
    m = {"lineups": {"h": {"players": [[132844, "Admir Mehmedi", 1, 1, 1, None]]}, "a": {"players": [[192625, "Patrick Herrmann", 1, 1, 1, None]]}},
         "events": [[9, "g", "a", 0, "Patrick Herrmann", None, None], [51, "g", "h", 0, "Admir Mehmedi", None, None]]}
    DM.resolve_ids(m)
    assert [e[3] for e in m["events"]] == [192625, 132844]


# ------------------------------------------------------------------ 365Scores
def test_s365_server_error_is_not_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(S365, "CACHE", str(tmp_path))
    path = "/web/competitions/history/?x=1"
    f = os.path.join(str(tmp_path), __import__("hashlib").sha1(path.encode()).hexdigest()[:20] + ".json.gz")
    with gzip.open(f, "wt", encoding="utf-8") as g:
        g.write(json.dumps({"_err": 500}))
    old = time.time() - S365.ERR_TTL - 60
    os.utime(f, (old, old))

    class R:
        headers = {}

        def read(self):
            return json.dumps({"table": {"rows": [1]}}).encode()
    monkeypatch.setattr(S365.urllib.request, "urlopen", lambda *a, **k: R())
    assert S365.fetch(path, 6 * 86400) == {"table": {"rows": [1]}}         # a 500 older than ERR_TTL is asked again


def test_placeholder_winner_either_language():
    assert S365.NOWIN.search("No Winner") and S365.NOWIN.search("لا فائز") and not S365.NOWIN.search("Al Ain")


# ------------------------------------------------------------------ the audit's own helpers
def test_audit_pairing():
    assert AU.name_sim("Turkiye", "Turkey") == 1.0
    assert AU.name_sim("Al-Wahda", "Al Wahda") == 1.0
    assert AU.pair_teams({1: "Ajman", 2: "Al-Wahda"}, {10: "Ajman Club", 20: "Al-Wahda"}, {}) == {1: 10, 2: 20}
    m = {"id": 5, "kickoff_utc": "2026-08-14T16:45:00Z", "home": {"id": 1, "name": "Al-Wahda"}, "away": {"id": 2, "name": "Ajman"}}
    g = {"id": 9, "startTime": "2026-08-14T20:45:00+04:00", "homeCompetitor": {"id": 10, "name": "Al-Wahda"}, "awayCompetitor": {"id": 20, "name": "Ajman Club"}}
    assert AU.pair_games([m], [g], {})[5][0]["id"] == 9
    T = AU.table_from_results([(1, 2, 2, 3), (2, 3, 1, 1)])
    assert T[2] == [2, 1, 1, 0, 4, 3, 4]


def test_audit_year_of_365_season():
    assert AU.y365("1973/74") == "1974" and AU.y365("1999-00") == "2000" and AU.y365("2025") == "2025"
