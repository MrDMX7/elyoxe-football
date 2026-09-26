"""FotMob adapter: statuses, competition mapping, composite tables, match detail extras."""
import config
from sources.fotmob import FotMob, status_of
from sources import schema as S


def test_status_mapping():
    assert status_of({"started": True, "finished": False, "liveTime": {"short": "16‎’‎"}}) == ("live", None, "16")
    assert status_of({"started": True, "liveTime": {"short": "HT", "shortKey": "halftime_short"}})[0] == "ht"
    assert status_of({"started": True, "finished": True, "reason": {"short": "Pen"}}) == ("finished", "Pen", None)
    assert status_of({"cancelled": True, "reason": {"short": "PP", "longKey": "postponed"}})[0] == "postponed"
    assert status_of({"started": False})[0] == "scheduled"
    assert status_of({"awarded": True, "finished": True})[0] == "awarded"


def test_day_maps_group_ids_to_competition(fx):
    ms = FotMob().day_from_raw(fx("fotmob_day_20260926.json"))
    gulf = [m for m in ms if m["comp"] == 329]
    assert len(gulf) == 2
    assert all(m["group_id"] == 943992 and m["stage"] == "Gulf Cup Grp. A" for m in gulf)
    kw = next(m for m in gulf if m["home"]["name"] == "Kuwait")
    assert kw["status"] == "finished" and kw["score"] == {"home": 2, "away": 3}
    assert kw["kickoff_uae"] == "2026-09-26T19:55:00+04:00"
    pens = [m for m in ms if m["penalties"]]
    assert pens and pens[0]["penalties"] == {"home": 3, "away": 4}
    S.validate_matches(ms)


def test_league_table_keeps_source_order(fx):
    c = FotMob().competition_from_raw({"id": 538}, fx("fotmob_league_538.json"), with_leaders=False)
    rows = c["standings"]["groups"][0]["rows"]
    assert [r["rank"] for r in rows] == list(range(1, 15))
    # 4 Al-Wasl, 5 Sharjah, 6 Al-Wahda: the official order (a pts/GD/GF re-sort would differ)
    assert [r["team"]["id"] for r in rows[3:6]] == [102111, 102124, 102122]
    assert rows[0]["gf"] == 11 and rows[0]["ga"] == 2
    assert c["standings"]["legend"][-1]["ranks"] == [13, 14]
    assert len(c["matches"]) == 42
    S.validate_standings(c["standings"])


def test_composite_group_tables(fx):
    c = FotMob().competition_from_raw({"id": 329}, fx("fotmob_league_329.json"), with_leaders=False)
    st = c["standings"]
    assert st["composite"] and [g["name"] for g in st["groups"]] == ["Grp. A", "Grp. B"]
    assert all(len(g["rows"]) == 4 for g in st["groups"])
    assert any(r["team"]["id"] == 5789 for r in st["groups"][1]["rows"])
    assert st["bracket"] and st["bracket"][0]["ties"][0]["tbd"]


def test_match_detail_uae(fx):
    d = FotMob().match_from_raw(fx("fotmob_match_uae_5898782.json"))
    S.validate_detail(d)
    assert d["comp"] == 538 and d["score"] == {"home": 2, "away": 2}
    assert d["halftime_score"] == {"home": 0, "away": 2}
    assert d["periods"]["firstHalfStarted"] == "2026-08-14T14:10:17Z"       # Oslo 16:10:17 -> UTC
    subs = [e for e in d["events"] if e["type"] == "sub"]
    first = subs[0]
    assert first["player"]["name"] == "Wesley Delgado" and first["player_out"]["name"] == "Nassim Chadli"
    assert sum(e["type"] == "penalty_goal" for e in d["events"]) == 2
    goal = next(e for e in d["events"] if e["type"] == "goal")
    assert goal["assist"]["name"] == "Carlos Alberto"
    assert d["lineups"]["home"]["formation"] == "4-2-3-1" and d["lineups"]["home"]["starters"][0]["country"] == "UAE"
    gk = d["lineups"]["home"]["starters"][0]
    assert gk["xy"] and 0 <= gk["xy"]["x"] <= 1 and gk["role"] == "GK" or gk["role"] is None
    assert d["h2h"]["summary"] == {"home_wins": 10, "draws": 5, "away_wins": 3} and len(d["h2h"]["matches"]) == 18
    assert d["venue"]["name"] == "Al Maktoum Stadium"
    assert d["xg"] is None and d["shotmap"] is None       # "ratings" coverage: no xG in the UAE league


def test_match_detail_xg_coverage(fx):
    d = FotMob().match_from_raw(fx("fotmob_match_pl_xg.json"))
    assert d["coverage"] == "xG"
    assert d["xg"] and isinstance(d["xg"]["home"], float)
    assert d["shotmap"] and all("xg" in s for p in d["shotmap"].values() for s in p["shots"])
    assert d["momentum"] and "minute" in d["momentum"][0]
    assert d["referee"]["name"] and d["referee"]["source_stats"]["matches"] > 0
    assert d["highlights"]["url"].startswith("https://www.youtube.com/")
    cards = [e for e in d["events"] if e["type"] == "yellow"]
    assert cards and cards[0]["reason_key"].startswith("card_desc_")


def test_live_halftime_detail(fx):
    d = FotMob().match_from_raw(fx("fotmob_match_live_ht_6052047.json"))
    assert d["status"] == "ht" and d["minute"] == "HT"
    assert d["lineups"]["away"]["unavailable"][0]["type"] == "injury"


def test_team_national_squad(fx):
    t = FotMob().team_from_raw(fx("fotmob_team_5789.json"))
    assert t["national"] and t["id"] == 5789
    players = [p for g in t["squad"] for p in g["players"]]
    assert all(p["club_id"] for p in players)
    assert any(f["comp"] == 290 and f["time_tbd"] for f in t["fixtures"])


def test_every_configured_competition_has_arabic_name():
    for c in config.competitions():
        assert c["name_ar"] and c["kind"] in ("league", "cup", "tournament", "supercup")
        if c["kind"] == "league" and c.get("magic", True):
            assert c.get("matches_per_team"), c["id"]
