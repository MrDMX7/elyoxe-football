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
    assert ("p15403:card:yellow", "card", "15403") in rows and ("p15403:pen:1", "pen", "15403") in rows


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


def test_map_from_profiles():
    import pushplayers as M
    prof = {"15403": {"bio": {"team": 10189}, "career": {"national team": {"seasons": [["2024", 8, "Bosnia", 3, 0, 0]]}}},
            "2777": {"bio": {"team": 49678}, "career": {}}, "5": None}
    m = {k: {kk: vv for kk, vv in v.items() if kk != "at"} for k, v in M.build_map(["15403", "2777", "5"], lambda pid: prof.get(pid)).items()}
    assert m == {"15403": {"club": 10189, "national": 8, "cc": None}, "2777": {"club": 49678, "national": None, "cc": None},
                 "5": {"club": None, "national": None, "cc": None}}
    old = {"seasons": [["2019", 8, "Bosnia", 3, 0, 0]]}
    assert M.national_of({"career": {"national team": old}}) is None          # more than 3 years without a cap
    assert M.national_of({"career": {"national team": {"seasons": [["2025/2026", "8", "B", 1, 0, 0]]}}}) == 8


def test_poller_plans_prematch_details():
    import inspect, poller
    src = inspect.getsource(poller.Poller.fetch_detail)
    assert 'why == "prematch"' in src and "PUSH.plan" in src


def test_push_knows_every_player_kind():
    import push
    assert set(PP.KINDS) <= set(push.EVENTS) and set(PP.KINDS) | set(push.TEAM_EVENTS) == set(push.EVENTS)


# ------------------------------------------------------------------ final review fixes (2026-10-09)
def test_deploy_bundles_every_local_module_push_and_poller_import():
    """deploy.sh copies an explicit list: a module push.py or poller.py imports and the list lacks kills the poller at
    cold start (review: pushplayer.py was missing)."""
    import os, re
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sh = open(os.path.join(root, "deploy.sh"), encoding="utf-8").read()
    listed = set(re.findall(r"\b([a-z_0-9]+)\.py\b", sh))
    for mod in ("poller.py", "push.py", "pushplayer.py"):
        src = open(os.path.join(root, mod), encoding="utf-8").read()
        for m in re.findall(r"^(?:import|from) ([a-z_0-9]+)", src, re.M):
            if os.path.exists(os.path.join(root, m + ".py")):
                assert m in listed, f"{mod} imports {m}.py but deploy.sh does not bundle it"


def test_squad_out_and_start11_only_for_players_in_this_match_however_many_are_followed():
    import time as _t
    d, full = det(status="finished", minute=None)
    many = {str(i): {"club": 99999, "national": None} for i in range(200000)}
    many.update({"15403": F["15403"]})
    t0 = _t.time()
    rows = PP.events_for(d, full, many, [], NOW)
    assert _t.time() - t0 < 1.0                                        # not one pass per followed player on earth
    assert {r[2] for r in rows} <= {"15403", "1", "555"}


def test_missed_penalty_key_survives_a_minute_correction():
    d, full = det(events=[ev_("missed_penalty", 66, 15403)])
    k1 = [r[0] for r in PP.events_for(d, full, {"15403": F["15403"]}, [], NOW) if r[1] == "pen"]
    d, full = det(events=[ev_("missed_penalty", 67, 15403)])
    assert [r for r in PP.events_for(d, full, {"15403": F["15403"]}, k1, NOW) if r[1] == "pen"] == []


def test_potm_is_sent_once_per_match_and_never_zero_minutes():
    d, full = det(status="finished", minute=None, events=[ev_("sub", 90, 555, out=1)])
    fol = {"1": {"club": 7, "national": None}, "15403": F["15403"], "555": {"club": 10189, "national": None}}
    rows = PP.events_for(d, full, fol, ["p1:potm"], NOW)
    assert not [r for r in rows if r[1] == "potm"]                     # a potm went out already (another player's key too)
    full["lineups"]["home"]["starters"][0]["rating"] = 9.9
    assert not [r for r in PP.events_for(d, full, fol, ["p1:potm"], NOW) if r[1] == "potm"]
    assert not [r for r in rows if r[1] == "end" and r[2] == "555"]    # came on at 90': no «لعب 0 دقيقة»


def test_the_map_reads_only_new_or_stale_players_within_a_budget_and_drops_unfollowed():
    import pushplayers as M
    got = []
    prof = lambda pid: got.append(pid) or {"bio": {"team": 1}}
    now = 200000                                                # a day = 86,400 s
    prev = {"a": {"club": 5, "national": None, "cc": None, "at": now - 100}, "b": {"club": 6, "national": None, "cc": None, "at": 0},
            "gone": {"club": 1, "at": now - 100}}
    m = M.build_map(["a", "b", "c", "d"], prof, prev=prev, budget=2, now=now)
    assert got == ["c", "d"]                                    # never mapped first (budget 2); "b" is stale but waits; "a" is fresh
    assert m["a"]["club"] == 5 and m["b"]["club"] == 6 and m["c"]["club"] == 1 and m["d"]["club"] == 1 and "gone" not in m
    got.clear()
    m2 = M.build_map(["a", "b", "c", "d"], prof, prev=m, budget=2, now=now + 60)
    assert got == ["b"] and m2["b"]["club"] == 1                # next run: the stale one


def test_followed_ids_drop_players_nobody_follows_any_more():
    import pushplayers as M

    class T:
        def query(self, **kw):
            pk = kw["KeyConditionExpression"].get_expression()["values"][1]
            if pk == "TIFOFOLLOW":
                return {"Items": [{"sk": "P1", "n": 1}, {"sk": "P2", "n": 3}, {"sk": "P3", "n": 0}]}
            return {"Items": [{"pk": pk}] if pk == "TIFOPUSH#P1" else []}
    assert M.followed_ids(T()) == ["1"]                         # 2's subscriptions expired (TTL), 3 unfollowed
