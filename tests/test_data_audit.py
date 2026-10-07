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


# ------------------------------------------------------------------ results decided after the match
def _row(tid, rank, p, w, d, l_, gf, ga, pts, zone=None):
    return {"rank": rank, "team": {"id": tid, "name": str(tid)}, "played": p, "won": w, "drawn": d, "lost": l_, "gf": gf, "ga": ga,
            "gd": gf - ga, "pts": pts, "zone": zone}


def test_awarded_result_moves_the_table_and_the_fixture():
    from compute import awarded as AW
    aw = {6028541: {"home": 3, "away": 0, "source": "FA"}}
    m = {"id": 6028541, "status": "finished", "score": {"home": 1, "away": 1}, "home": {"id": 1}, "away": {"id": 2}}
    st = {"groups": [{"rows": [_row(3, 1, 8, 3, 3, 2, 12, 9, 12), _row(2, 2, 8, 1, 4, 3, 6, 11, 7, "z2"), _row(1, 3, 8, 2, 3, 3, 8, 10, 9, "z3")]}]}
    assert AW.apply_to_standings(st, [m], aw)[0]["awarded"] == "3-0"
    rows = {r["team"]["id"]: r for r in st["groups"][0]["rows"]}
    assert (rows[1]["won"], rows[1]["drawn"], rows[1]["gf"], rows[1]["ga"], rows[1]["pts"]) == (3, 2, 10, 9, 11)   # Al Minaa
    assert (rows[2]["drawn"], rows[2]["lost"], rows[2]["gf"], rows[2]["ga"], rows[2]["pts"]) == (3, 4, 5, 13, 6)   # Naft Maysan
    assert [r["team"]["id"] for r in st["groups"][0]["rows"]] == [3, 1, 2] and rows[1]["rank"] == 2 and rows[1]["zone"] == "z2"
    f = AW.apply_to_match(m, aw)
    assert f["status"] == "awarded" and f["score"] == {"home": 3, "away": 0} and f["score_played"] == {"home": 1, "away": 1}
    assert AW.apply_to_match(f, aw) is f                                    # FotMob showing the decision: nothing to do
    st2 = {"groups": [{"rows": [_row(1, 1, 8, 3, 2, 3, 10, 9, 11), _row(2, 2, 8, 1, 3, 4, 5, 13, 6)]}]}
    assert AW.apply_to_standings(st2, [dict(m, status="awarded", score={"home": 3, "away": 0})], aw) == []


def test_phantom_goal_dropped_from_a_finished_match():
    from sources.fotmob import drop_phantom_goals
    evs = [_ev("goal", 45, "home", 1), _ev("goal", 51, "home", 2), _ev("goal", 56, "home", 2), _ev("goal", 89, "away", 3),
           {**_ev("goal", 90, "home", None), "player": {"id": None, "name": "<TBD>"}}]
    out = drop_phantom_goals(evs, {"home": 3, "away": 1})                  # 5030320: FotMob's own score is 3-1
    assert [(e["minute"], e["team"]) for e in out] == [(45, "home"), (51, "home"), (56, "home"), (89, "away")]
    assert drop_phantom_goals(evs[:4], {"home": 3, "away": 1}) == evs[:4]


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


# ------------------------------------------------------------------ «الأرقام مدققة»: the public badge file (item 16)
def _doc(findings, areas=AU.AREAS):
    summary = {a: {"checked": {"rows": 1}, "findings": {}} for a in AU.AREAS}
    summary["matches"] = {"checked": {"fixture_vs_fotmob": 210, "score_vs_365": 201}, "findings": {}}
    summary["champions"] = {"checked": {"lists": 61}, "findings": {}}
    return {"date": "2026-10-05", "generated": "2026-10-05T01:23:07Z", "params": {"areas": sorted(areas)}, "summary": summary,
            "findings": findings, "requests": {"fotmob": 900}, "timing": {"matches": 192}, "notes": ["internal"]}


def test_public_summary_counts_only_and_nothing_internal():
    f = [{"area": "champions", "check": "duplicate_season", "level": "error", "verdict": "ours", "key": "comp:1", "msg": "secret",
          "url": "/c/x/"},
         {"area": "matches", "check": "file_goals_missing", "level": "warn", "verdict": "stale", "key": "match:9", "msg": "m"},
         {"area": "gaps", "check": "x", "level": "info", "verdict": "gap", "key": "k", "msg": "i"}]
    pub = AU.public_summary(_doc(f))
    assert set(pub) == {"generated", "ok", "checked", "errors", "warnings", "areas"}
    assert pub["generated"] == "2026-10-05T01:23:07Z" and pub["checked"] == 478 and pub["errors"] == 1 and pub["warnings"] == 1
    assert pub["ok"] is False and pub["areas"]["matches"] == {"ar": "المباريات", "checked": 411, "errors": 0, "warnings": 1, "ok": True}
    assert pub["areas"]["champions"]["ok"] is False and list(pub["areas"]) == list(AU.AREAS)
    blob = json.dumps(pub, ensure_ascii=False)
    assert not any(s in blob for s in ("secret", "comp:1", "/c/x/", "match:9", "fotmob", "internal", "duplicate_season"))
    assert AU.public_summary(_doc(f[1:]))["ok"] is True                       # warnings and info alone: ok


def test_public_summary_a_crashed_area_is_never_ok_and_partial_runs_never_publish(tmp_path):
    from store import Store, LocalBackend
    crash = [{"area": "standings", "check": "audit_crashed", "level": "warn", "verdict": "ours", "key": "audit:standings", "msg": "x"}]
    assert AU.public_summary(_doc(crash))["areas"]["standings"]["ok"] is False
    empty = _doc([])
    empty["summary"]["gaps"]["checked"] = {}
    assert AU.public_summary(empty)["areas"]["gaps"]["ok"] is False and AU.public_summary(empty)["ok"] is False   # checked nothing
    store = Store(LocalBackend(tmp_path))
    assert AU.publish(store, _doc([], ("matches",)), {"matches"}) is None and store.get_json("audit/latest.json") is None
    pub = AU.publish(store, _doc([]), set(AU.AREAS))
    assert store.get_json("audit/latest.json") == pub and pub["ok"] is True
    meta = json.loads((tmp_path / "v1" / "audit" / "latest.json.meta").read_text())
    assert meta["CacheControl"].startswith("public, max-age=3600")


def test_card_and_goal_signatures_sort_with_a_missing_minute_or_player():
    # 2026-10-07: a card with no minute (or no player id) crashed the matches area, so «الأرقام مدققة» left every page
    from db import audit as AU
    card = AU.CARDS if isinstance(AU.CARDS, str) else next(iter(AU.CARDS))
    goal = next(iter(AU.G))
    evs = [{"type": card, "minute": 30, "player": {"id": 7}}, {"type": card, "minute": None, "player": None},
           {"type": card, "minute": 12, "player": {"id": 3}}]
    sig = AU._card_sig(evs)
    assert [x[1] for x in sig] == [12, 30, None]
    assert AU._card_sig(list(reversed(evs))) == sig                      # the order the events came in never matters
    gs = AU._goal_sig([{"type": goal, "minute": None, "player": {"id": 1}}, {"type": goal, "minute": 5, "player": None, "assist": {"id": 2}}])
    assert [x[1] for x in gs] == [5, None]
