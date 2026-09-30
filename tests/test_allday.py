"""v1/all (compute/allday.py, sources/s365.py, Poller.write_all): every match of the day, on real captures —
FotMob's day list of 2026-09-30 at ~22:15 UAE (31 leagues, 76 matches, 18 live) and 365Scores payloads."""
import json
from datetime import datetime, timezone

import pytest

import config
from compute import allday as A
from sources import s365
from store import dumps, gz
from timeutil import parse_utc

NOW = datetime(2026, 9, 30, 18, 15, tzinfo=timezone.utc)
NAMES = {"teams": {"6713": "أمريكا", "9762": "تشيلي"}, "competitions": {"114": "المباريات الودية", "329": "كأس الخليج العربي"},
         "countries": {"INT": "دولي", "NOR": "النرويج", "UAE": "الإمارات العربية المتحدة", "ENG": "إنجلترا"}}


@pytest.fixture
def day(fx):
    return fx("fotmob_day_all_20260930.json")


@pytest.fixture
def s365fx(fx):
    return fx("s365_games_samples.json")


def _build(day, extra=None, ours=None, order=None):
    comps = config.competitions()
    ours = {c["id"] for c in comps} if ours is None else ours
    order = {c["id"]: i for i, c in enumerate(comps)} if order is None else order
    return A.build("20260930", day, NAMES, ours, order, {5789, 7795}, extra, NOW)


def test_every_match_is_there_once(day):
    doc = _build(day)
    ids = [m["id"] for lg in doc["leagues"] for m in lg["matches"]]
    raw_ids = [m["id"] for lg in day["leagues"] for m in lg["matches"]]
    assert sorted(ids) == sorted(raw_ids) and len(ids) == len(set(ids)) == doc["n"] == 76
    assert doc["live"] == 18
    # groups of one competition are one league (EURO U21 qualifying: 5 group entries), each match keeps its group
    u21 = [lg for lg in doc["leagues"] if lg["id"] == 10437]
    assert len(u21) == 1 and len(u21[0]["matches"]) == 8 and {m.get("g") for m in u21[0]["matches"]} >= {"Grp. A", "Grp. B"}
    assert u21[0]["name"] == "EURO U21 Qualification"
    assert len(gz(dumps(doc))) < 12000                                  # 76 matches, ~8 KB on the wire


def test_rows_are_compact_and_right(day):
    doc = _build(day)
    by = {m["id"]: m for lg in doc["leagues"] for m in lg["matches"]}
    usa = by[5991874]                                                    # USA 4-2 Chile, friendly, finished
    assert usa == {"id": 5991874, "utc": "2026-09-30T00:00:00Z", "status": "finished", "home": [6713, "أمريكا", 4],
                   "away": [9762, "تشيلي", 2], "ours": True}
    live = [m for m in by.values() if m["status"] in ("live", "ht")]
    assert len(live) == 18 and all(m.get("minute") for m in live)
    assert all(len(m["home"]) >= 3 and isinstance(m["home"][2], int) for m in live)
    sched = [m for m in by.values() if m["status"] == "scheduled"]
    assert sched and all(len(m["home"]) == 2 for m in sched)            # no score before kickoff
    assert all("minute" not in m for m in by.values() if m["status"] not in ("live", "ht"))


def test_league_order_ours_then_arab_then_europe(day):
    doc = _build(day)
    L = doc["leagues"]
    flags = [bool(lg.get("ours")) for lg in L]
    assert flags == sorted(flags, reverse=True)                          # every «ours» league before the others
    ours = [lg["id"] for lg in L if lg.get("ours")]
    order = {c["id"]: i for i, c in enumerate(config.competitions())}
    assert ours == sorted(ours, key=lambda i: order[i])                  # competitions.yaml order (UAE first)
    rest = [lg for lg in L if not lg.get("ours")]
    tiers = [A._rank(lg, order)[0] for lg in rest]
    assert tiers == sorted(tiers)
    eng = [lg for lg in rest if lg["cc"] == "ENG"]
    assert [lg["name"] for lg in eng][-1] == "Women's League Cup"         # women's after the men's leagues of a country
    gulf = next(lg for lg in L if lg["id"] == 329)
    assert gulf["name_ar"] == "كأس الخليج العربي" and gulf.get("ours") and gulf["country_ar"] == "دولي"


def test_arab_national_teams_are_ours_in_any_competition(day):
    comps = config.competitions()
    arab = {c["fotmob_team"] for c in config.countries() if c.get("arab") and c.get("fotmob_team")}
    doc = A.build("20260930", day, NAMES, set(), {}, arab, None, NOW)      # as if the Gulf Cup were not ours
    by = {m["id"]: m for lg in doc["leagues"] for m in lg["matches"]}
    assert by[6052087].get("ours") and by[6052086].get("ours")           # Bahrain-Yemen, UAE-Qatar
    assert not by[5991874].get("ours")                                   # USA-Chile
    assert not any(lg.get("ours") for lg in doc["leagues"]) and comps


def test_live_rows_and_hot(day):
    doc = _build(day)
    rows = A.live_rows(doc, NOW)
    assert sum(r["status"] in ("live", "ht") for r in rows) == 18
    assert all(set(r) <= {"id", "status", "minute", "home", "away", "pen", "sd", "lg"} for r in rows)
    old = [r for r in rows if r["status"] == "finished"]
    assert all(0 <= (NOW - parse_utc(next(m["utc"] for lg in doc["leagues"] for m in lg["matches"] if m["id"] == r["id"]))).total_seconds() <= 3 * 3600 for r in old)
    assert A.hot(doc, NOW)
    quiet = {"leagues": [{"id": 1, "matches": [{"id": 1, "status": "scheduled", "utc": "2026-09-30T20:00:00Z"}]}]}
    assert not A.hot(quiet, NOW)
    assert A.hot(quiet, datetime(2026, 9, 30, 19, 57, tzinfo=timezone.utc))            # kicks off in 3 min
    assert A.hot(quiet, datetime(2026, 9, 30, 20, 10, tzinfo=timezone.utc))            # 10 min late, still «scheduled»
    assert not A.hot(quiet, datetime(2026, 9, 30, 21, 0, tzinfo=timezone.utc))         # 1 h late: no coverage, not hot


def test_365_arab_leagues(s365fx):
    L = s365.leagues(s365fx["arab_20260919"])
    assert {lg["id"] for lg in L} == {"365:565", "365:5524"}                           # Jordan league, Lebanon cup
    jor = next(lg for lg in L if lg["id"] == "365:565")
    assert jor["cc"] == "JOR" and jor["country_ar"] == "الأردن" and jor["src"] == "365" and jor["name"] == "الدوري الأردني"
    m = jor["matches"][0]
    assert str(m["id"]).startswith("365:") and m["status"] == "finished" and isinstance(m["home"][2], int)
    leb = next(lg for lg in L if lg["id"] == "365:5524")
    assert all(x.get("g", "").startswith("المجموعة") for x in leb["matches"])
    post = s365.leagues(s365fx["postponed_20260830"])
    st = [x["status"] for lg in post for x in lg["matches"]]
    assert "postponed" in st and "finished" in st
    assert all(len(x["home"]) == 2 for lg in post for x in lg["matches"] if x["status"] == "postponed")   # -1 is no score


def test_365_status_words(s365fx):
    L = s365.leagues(s365fx["mixed_20260930"], only_cc=None)
    ms = [m for lg in L for m in lg["matches"]]
    live = [m for m in ms if m["status"] in ("live", "ht")]
    assert len(live) == 4 and all(m.get("minute") for m in live) and all("'" not in m["minute"] for m in live)
    assert {m["status"] for m in ms} >= {"live", "scheduled", "finished"}
    assert s365.status({"statusGroup": 3, "statusText": "شوط", "shortStatusText": "شوط"}) == ("ht", "HT")
    assert s365.status({"statusGroup": 4, "statusText": "ألغيت"}) == ("cancelled", None)


def test_365_url_and_index():
    u = s365.day_url([565, 5479], "20261009")
    assert u.endswith("&competitions=565,5479&startDate=09/10/2026&endDate=09/10/2026") and "langId=27" in u
    idx = {"comps": [[565, "الدوري الأردني", "Pro League", 119, 0, 20, "", "", 0, 5, 1, 0],
                     [9999, "دوري السيدات", "Women", 119, 0, 1, "", "", 1, 0, 1, 0],
                     [549, "دوري الخليج العربي", "Pro League", 124, 0, 50, "", "", 0, 30, 0, 0]]}
    assert s365.comps_from_index(idx) == [565]
    assert s365.comps_from_index({}) == list(s365.DEFAULT_COMPS)


def test_365_leagues_merge_into_the_document(day, s365fx):
    doc = _build(day, extra=s365.leagues(s365fx["arab_20260919"]))
    ids = [lg["id"] for lg in doc["leagues"]]
    assert "365:565" in ids and doc["sources"] == ["fotmob", "365scores"]
    first_rest = next(i for i, lg in enumerate(doc["leagues"]) if not lg.get("ours"))
    assert doc["leagues"][first_rest]["id"] in ("365:565", "365:5524")   # Arab leagues lead the non-ours ones


# ---------------------------------------------------------------- the poller
def _poller(tmp_path, now):
    import poller as P
    from store import Store, LocalBackend
    p = P.Poller(Store(LocalBackend(tmp_path)))
    p.load()
    p.now_fn = lambda: now
    return p


def test_poller_writes_all_and_live_from_the_day_request(tmp_path, day, s365fx, monkeypatch):
    import poller as P
    p = _poller(tmp_path, NOW)
    calls, n365 = [], []
    p.fm.day_raw = lambda ymd: calls.append(ymd) or json.loads(json.dumps(day))
    monkeypatch.setattr(s365, "fetch_day", lambda http, comps, ymd: n365.append((http, ymd)) or (s365fx["arab_20260919"] if ymd == "20260930" else {}))
    p.refresh_s365()                                                     # the chore: today, yesterday, tomorrow
    assert sorted(y for _, y in n365) == ["20260929", "20260930", "20261001"] and all(h is P.HTTP365 for h, _ in n365)
    p.day_file("20260930", "hot")
    assert calls == ["20260930"]                                          # one FotMob request for both files
    doc = p.store.get_json("all/20260930.json")
    assert doc["n"] == 76 + 6 and doc["live"] == 18
    assert p.store.b.meta("v1/all/20260930.json")["CacheControl"].startswith("public, max-age=20")
    live = p.store.get_json("all/live.json")
    assert live["live"] == 18 and live["days"] == ["20260930"]
    assert p.store.b.meta("v1/all/live.json")["CacheControl"].startswith("public, max-age=10")
    assert p.all_hot("20260930")
    # an idle minute: refreshed because a match is live (not only ours)
    p.all_at.clear()
    p.refresh_all("20260930")
    assert calls == ["20260930", "20260930"]
    # writing the lists never asks 365Scores (a slow answer must not eat a live pass); its chore keeps its cadence
    n = len(n365)
    p.refresh_all("20260930")
    p.refresh_s365()
    assert len(n365) == n
    assert p.store.get_json("all/20260930.json")["n"] == 82               # the cached Arab leagues are still in
    p.day_file("20261001", "warm")                                        # tomorrow: 5-minute cache, no live rows
    assert p.store.b.meta("v1/all/20261001.json")["CacheControl"].startswith("public, max-age=300")
    assert p.store.get_json("all/live.json")["days"] == ["20260930"]


def test_poller_all_feed_failure_never_costs_the_day_file(tmp_path, day, monkeypatch):
    p = _poller(tmp_path, NOW)
    p.fm.day_raw = lambda ymd: json.loads(json.dumps(day))
    monkeypatch.setattr(A, "build", lambda *a, **k: 1 / 0)
    p.day_file("20260930", "hot")
    assert p.store.get_json("day/20260930.json") and not p.store.get_json("all/20260930.json")
    assert p.store.health["all:today"]["ok"] is False
