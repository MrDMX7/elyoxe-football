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
