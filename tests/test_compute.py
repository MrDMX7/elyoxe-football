"""Computed extras: magic numbers, prayer times, .ics, weather, season aggregates, tracked filter."""
from datetime import date, datetime, timezone

import pytest

import poller as P
from compute import ics, magic, prayer, season, weather
from compute.venues import Venues
from sources.fotmob import FotMob
from store import Store, LocalBackend


def _row(tid, pts, played):
    return {"rank": 0, "team": {"id": tid, "name": str(tid)}, "pts": pts, "played": played}


def test_magic_numbers_hand_built():
    st = {"groups": [{"rows": [_row(1, 60, 24), _row(2, 50, 24), _row(3, 30, 24), _row(4, 10, 24)]}],
          "legend": [{"label": "Relegation", "key": "relegation", "ranks": [4]}]}
    m = magic.magic_numbers(st, 26)
    t1, t2, t4 = m["teams"]["1"], m["teams"]["2"], m["teams"]["4"]
    # rival max: team 2 can reach 56 -> team 1 needs 57, has 60: title clinched
    assert t1["title"]["state"] == "clinched"
    assert t2["title"]["state"] == "eliminated"          # 60 > 50 + 6
    # safety = finish top 3: team 4 can reach 16 < team 3's 30 already -> relegated
    assert t4["safety"]["state"] == "eliminated"
    st["groups"][0]["rows"][0]["pts"] = 54
    m = magic.magic_numbers(st, 26)
    assert m["teams"]["1"]["title"] == {"needed": 3, "state": "open", "own_hands": True, "wins_needed": 1}


def test_prayer_matches_adhan_reference(fx):
    worst = 0
    for r in fx("prayer_adhan.json"):
        t = prayer.prayer_times(r["lat"], r["lon"], date.fromisoformat(r["date"]))
        for k in ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"):
            ref = datetime.fromisoformat(r[k].replace("Z", "+00:00"))
            worst = max(worst, abs((t[k] - ref).total_seconds()))
    assert worst <= 60


def test_prayer_clash_flags():
    # 16 Oct 2026, 17:05 UAE kickoff at Hamdan bin Zayed (Madinat Zayed): Maghrib 18:02 falls at half-time
    ko = datetime(2026, 10, 16, 13, 5, tzinfo=timezone.utc)
    c = prayer.clashes(ko, 23.669151, 53.69423)
    assert [x["prayer"] for x in c["clashes"]] == ["maghrib"]
    assert c["clashes"][0]["segment"] == "halftime" and c["estimated_window"]
    # a 19:45 kickoff meets Isha (19:16 is before kickoff; nothing) -> no clash that evening
    late = prayer.clashes(datetime(2026, 10, 16, 15, 45, tzinfo=timezone.utc), 23.669151, 53.69423)
    assert late["clashes"] == []


def test_ics_uid_stable_and_sequence_bumps():
    m = {"id": 1, "comp": 538, "round": "6", "kickoff_utc": "2026-10-16T13:05:00Z", "status": "scheduled",
         "home": {"id": 1, "name": "A", "name_ar": "أ"}, "away": {"id": 2, "name": "B", "name_ar": "ب"}}
    seq = {}
    s1 = ics.bump_sequences([m], seq)
    moved = dict(m, kickoff_utc="2026-10-17T15:45:00Z")
    s2 = ics.bump_sequences([moved], seq)
    assert s1["1"][0] == 0 and s2["1"][0] == 1
    again = ics.team_calendar({"id": 1, "name": "A"}, [moved], {}, ics.bump_sequences([moved], seq))
    assert again == ics.team_calendar({"id": 1, "name": "A"}, [moved], {}, ics.bump_sequences([moved], seq))
    cal = ics.team_calendar({"id": 1, "name": "A", "name_ar": "أ"}, [moved], {538: "دوري"}, s2)
    assert "UID:1@football.elyoxe" in cal and "SEQUENCE:1" in cal and "DTSTART:20261017T154500Z" in cal
    tbd = {"id": None, "ext_id": "uaepl:x", "comp": 538, "kickoff_utc": None, "date_uae": "2026-11-02", "time_tbd": True,
           "status": "scheduled", "home": m["home"], "away": m["away"]}
    cal2 = ics.team_calendar({"id": 1, "name": "A"}, [tbd], {}, {})
    assert "DTSTART;VALUE=DATE:20261102" in cal2
    assert all(len(line.encode()) <= 75 for line in cal2.split("\r\n"))


def test_heat_index():
    assert weather.heat_index_c(35, 60) == pytest.approx(45.1, abs=0.6)       # NWS table: 95 F / 60 % = 113 F
    assert weather.heat_category(weather.heat_index_c(35, 60)) == "danger"
    assert weather.heat_category(weather.heat_index_c(22, 40)) == "none"


def test_weather_at_kickoff_picks_hour():
    hourly = {"time": ["2026-09-27T17:00", "2026-09-27T18:00"], "temperature_2m": [33, 32],
              "relative_humidity_2m": [60, 62], "apparent_temperature": [38, 37]}
    w = weather.at_kickoff(hourly, "2026-09-27T18:10:00Z")
    assert w["available"] and w["temp_c"] == 32 and w["hour_utc"] == "2026-09-27T18:00Z"


def test_venue_resolution_and_distance():
    v = Venues()
    m = {"id": 1, "comp": 538, "home": {"id": 149994}, "away": {"id": 209190}}
    s = v.resolve(m, uaepl_name="Rashid bin Saeed Stadium")
    assert s["id"] == "rashid-bin-saeed-stadium" and s["in_uae"]
    d = v.distances(s)
    assert d["ajman"] < 10 and d["abu-dhabi"] > 150
    assert v.resolve(m)["source"] == "home-team default"


def test_season_aggregates_from_details(fx):
    d = FotMob().match_from_raw(fx("fotmob_match_uae_5898782.json"))
    L = {str(d["id"]): season.ledger_entry(d)}
    ht = season.ht_table(L)
    assert ht["rows"][0]["team"] == 209190 and ht["rows"][0]["pts"] == 3     # Kalba led 0-2 at half-time
    gb = season.goal_bands(L)
    assert sum(gb["teams"]["209190"]["for"].values()) == 2 and sum(gb["teams"]["102123"]["for"].values()) == 2
    assert season.xg_table(L)["available"] is False
    pl = FotMob().match_from_raw(fx("fotmob_match_pl_xg.json"))
    L2 = {str(pl["id"]): season.ledger_entry(pl)}
    xt = season.xg_table(L2)
    assert xt["available"] and len(xt["rows"]) == 2
    assert abs(sum(r["xpts"] for r in xt["rows"]) - 3) < 0.35       # a match hands out 2 or 3 points
    refs = season.referees(L2)["referees"]
    assert refs[0]["matches"] == 1 and refs[0]["name"] == pl["referee"]["name"]
    assert season.shots(L2)["available"]


def test_xpts_symmetry():
    h, a = season.xpts(1.2, 1.2)
    assert h == pytest.approx(a) and 1.0 < h < 1.6


def test_last_season_same_round():
    prev = [{"id": i, "kickoff_utc": f"2025-08-{10 + i}T14:00:00Z", "status": "finished",
             "score": {"home": 1, "away": 0}, "home": {"id": 1}, "away": {"id": 2}} for i in range(4)]
    out = season.last_season_same_round(prev, {1: 2, 2: 3, 3: 1})
    assert out["1"] == {"played": 2, "pts": 6, "gf": 2, "ga": 0}
    assert out["2"]["pts"] == 0 and "3" not in out


def test_tracked_filter_includes_national_team_friendlies(tmp_path):
    p = P.Poller(Store(LocalBackend(tmp_path)))
    assert p.tracked({"comp": 538, "home": {"id": 1}, "away": {"id": 2}})
    assert p.tracked({"comp": 114, "home": {"id": 5789}, "away": {"id": 8}})       # friendly, UAE plays
    assert p.tracked({"comp": 114, "home": {"id": 7}, "away": {"id": 8}})           # owner 2026-09-30: every international friendly
    assert not p.tracked({"comp": 999999, "home": {"id": 7}, "away": {"id": 8}})    # an untracked competition without an Arab side
    assert p.tracked({"comp": 999999, "home": {"id": 5789}, "away": {"id": 8}})     # ... unless an Arab national team plays
