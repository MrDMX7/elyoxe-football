"""compute/goal_how.py on real FotMob goals (tests/fixtures/goal_how_samples.json: events trimmed to the fields the module
reads, English ticker excerpts, matches of 2026-09-11..29) plus hand-made edge cases."""
import json, os

import pytest

from compute import goal_how as GH

HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, "fixtures", "goal_how_samples.json"), encoding="utf-8"))
M = {m["match"]: m for m in S["matches"]}


@pytest.mark.parametrize("case", S["singles"], ids=lambda c: f"{c['match']}-{(c['expect'] or {}).get('key')}")
def test_real_single_events(case):
    assert GH.describe(case["event"]) == case["expect"]


@pytest.mark.parametrize("mid", sorted(M))
def test_real_matches_with_ticker(mid):
    m = M[mid]
    assert GH.describe_all(m["raw"], m["ticker"]) == m["expect"]


def how(mid, key):
    m = M[mid]
    return GH.describe_all(m["raw"], m["ticker"]).get(key)


def test_uae_league_goals_come_from_the_auto_ticker():
    # UAE Pro League: "ratings" coverage, no shot map; Opta's auto commentary (en_gen) is the only evidence
    assert how(1000020521, "25-644002") == {"key": "header+close", "ar": "رأسية من قريب"}               # six yard box
    assert how(1000020521, "45+2-851198")["key"] == "header+set_piece"                                 # added time
    assert how(1000020521, "67-981858")["key"] == "right_foot"             # FotMob 67', Opta 68': matched by name
    assert how(1000020521, "81-1291309") == {"key": "left_foot+outside", "ar": "تسديدة باليسار من برا المنطقة"}
    assert how(1000020519, "24-1837011")["key"] == "own_goal"
    assert GH.describe_all(M[1000020521]["raw"]) == {}                      # without the ticker nothing is known


def test_human_commentary_rare_techniques_only_for_the_scorer():
    assert how(5749683, "23-942549") == {"key": "volley+right_foot+corner", "ar": "طايرة باليمين من ركنية"}   # Gilmour
    # Haaland prods in after «Odegaard steps up to take the 25-yard free-kick» and «Berg cushions back a header»:
    # neither the free kick nor the header is his
    assert how(5181864, "51-737066")["key"] == "left_foot+close+set_piece"
    assert how(5795461, "9-1137705")["key"] == "free_kick"                 # «a cheeky free-kick by Enzo Fernandez»
    assert how(5071380, "24-30981") == {"key": "free_kick+long", "ar": "ضربة حرة مباشرة من بعيد"}      # Messi


def test_event_keys_and_flags():
    assert GH.describe({"type": "Goal", "time": 10, "goalDescriptionKey": "penalty"}) == {"key": "penalty", "ar": "ضربة جزاء"}
    assert GH.describe({"type": "Goal", "time": 10, "ownGoal": True})["key"] == "own_goal"
    assert GH.describe({"type": "Goal", "time": 10, "goalDescriptionKey": "header"})["ar"] == "رأسية"
    assert GH.describe({"type": "Goal", "time": 10, "goalDescriptionKey": "direct_free_kick"})["ar"] == "ضربة حرة مباشرة"
    assert GH.describe({"type": "Goal", "time": 10}) is None
    assert GH.describe({"type": "Goal", "time": 120, "isPenaltyShootoutEvent": True, "goalDescriptionKey": "penalty"}) is None


def test_shot_geometry():
    ev = lambda **s: {"type": "Goal", "time": 5, "shotmapEvent": dict({"situation": "RegularPlay"}, **s)}
    assert GH.describe(ev(shotType="RightFoot", x=101, y=33, isFromInsideBox=True))["key"] == "right_foot+close"
    assert GH.describe(ev(shotType="RightFoot", x=92, y=34, isFromInsideBox=True))["key"] == "right_foot"
    assert GH.describe(ev(shotType="LeftFoot", x=86, y=30, isFromInsideBox=False))["key"] == "left_foot+outside"
    assert GH.describe(ev(shotType="LeftFoot", x=78, y=30, isFromInsideBox=False))["key"] == "left_foot+long"     # 27 m
    assert GH.describe(ev(shotType="Header", x=101, y=34, isFromInsideBox=True))["key"] == "header"      # no «close» header
    assert GH.describe(ev(shotType="Header", x=100, y=34, isFromInsideBox=True, situation="FromCorner"))["ar"] == "رأسية من ركنية"
    assert GH.describe(ev(shotType="RightFoot", x=94, y=34, isFromInsideBox=True, situation="Penalty"))["key"] == "penalty"
    assert GH.describe(ev(shotType="LeftFoot", x=80, y=40, isFromInsideBox=False, situation="FreeKick"))["key"] == "free_kick+long"
    # a header key the shot contradicts: the shot's body part
    assert GH.describe({"type": "Goal", "time": 5, "goalDescriptionKey": "header",
                        "shotmapEvent": {"shotType": "LeftFoot", "situation": "RegularPlay", "x": 95, "y": 30, "isFromInsideBox": True}})["key"] == "left_foot"


def test_phrasing():
    assert GH._compose("left_foot", "outside", "fast_break")["ar"] == "تسديدة باليسار من برا المنطقة بعد هجمة مرتدة"
    assert GH._compose("header", None, "corner")["ar"] == "رأسية من ركنية"
    assert GH._compose("right_foot", "close", "solo")["ar"] == "تسديدة باليمين من قريب، مجهود فردي"
    assert GH._compose("volley", None, None, "left_foot") == {"key": "volley+left_foot", "ar": "طايرة باليسار"}
    assert GH._compose("bicycle", "close") == {"key": "bicycle", "ar": "دبل كيك"}
    assert GH._compose("chip", "outside")["ar"] == "لوب من برا المنطقة"
    for k in list(GH.TECH_AR) + list(GH.PLACE_AR) + list(GH.SIT_AR):
        assert not any(c in "٠١٢٣٤٥٦٧٨٩" for c in (GH.TECH_AR.get(k, "") + GH.PLACE_AR.get(k, "") + GH.SIT_AR.get(k, "")))


def test_auto_template_parts():
    P = GH.parse_auto
    assert P("Goal! A 1, B 0. X Y (A) converts the penalty with a left footed shot to the bottom left corner.")["tech"] == "penalty"
    assert P("Own Goal by X Y, B. A 1, B 0.")["tech"] == "own_goal"
    assert P("Goal! A 1, B 0. X Y (A) right footed shot from a difficult angle on the left to the centre of the goal following a corner.") == \
        {"tech": "right_foot", "place": "angle", "sit": "corner"}
    assert P("Goal! A 2, B 0. X Y (A) left footed shot from long range on the right to the top left corner.")["place"] == "long"
    assert P("Goal! A 1, B 1. X Y (B) scores from a free kick with a right footed shot to the top right corner.")["tech"] == "free_kick"
    assert P("Goal! A 0, B 1. X Y (B) header from the centre of the box to the bottom left corner. Assisted by Z with a cross following a set piece situation.") == \
        {"tech": "header", "sit": "set_piece"}


def test_human_reader_is_conservative():
    ev = {"type": "Goal", "time": 50, "nameStr": "Pio Esposito", "lastName": "Pio Esposito"}
    t = "GOAL! An eventual Tonali volley pings off the post. Pio Esposito dives at the rebound to head into the net!"
    assert GH.parse_human(t, ev) == {}                                      # the volley was Tonali's
    assert GH.parse_human("What a finish! Esposito chips the keeper from 30 yards!", ev) == {"tech": "chip", "place": "long"}
    assert GH.parse_human("An overhead kick from Esposito! Unbelievable.", ev) == {"tech": "bicycle"}
    ev2 = {"type": "Goal", "time": 50, "nameStr": "Ramos", "shotmapEvent": {"shotType": "Header", "situation": "RegularPlay", "x": 100, "y": 34, "isFromInsideBox": True}}
    assert GH.describe(ev2, None, "Ramos volleys it home!", auto=False)["key"] == "header"   # a header is never a volley


def test_assign_two_goals_one_minute():
    goals = [{"time": 30, "playerId": 1, "nameStr": "Ali Mabkhout"}, {"time": 30, "playerId": 2, "nameStr": "Caio Canedo"}]
    lines = [(31, None, "G", "Goal! A 0, B 1. Caio Canedo (B) header from the centre of the box to the bottom left corner."),
             (30, None, "G", "Goal! A 1, B 0. Ali Mabkhout (A) left footed shot from outside the box to the top left corner.")]
    got = GH.assign(goals, lines)
    assert "Mabkhout" in got[0] and "Canedo" in got[1]
    # a single line at the exact minute, a name spelt differently (Mohamed / Mohammed): still his
    assert GH.assign([{"time": 12, "playerId": 3, "nameStr": "Mohammed Abbas"}], [(12, None, "G", "Goal! A 1, B 0. Mohamed Abas (A) header from very close range to the centre of the goal.")]) == \
        {0: "Goal! A 1, B 0. Mohamed Abas (A) header from very close range to the centre of the goal."}


def test_goal_key_raw_and_normalized_agree():
    raw = {"time": 45, "overloadTime": 2, "playerId": 851198}
    norm = {"minute": 45, "added": 2, "player": {"id": 851198, "name": "Waleed Azaro"}}
    assert GH.goal_key(raw) == GH.goal_key(norm) == "45+2-851198"
    assert GH.goal_key({"time": 7, "overloadTime": None, "playerId": 5}) == GH.goal_key({"minute": 7, "added": None, "player": {"id": 5}}) == "7-5"


def test_needs_ticker():
    base = lambda langs, shot: {"content": {"liveticker": {"langs": langs}, "matchFacts": {"events": {"events": [
        {"type": "Goal", "time": 3, "playerId": 1, "shotmapEvent": {"shotType": "Header"} if shot else None}]}}}}
    assert GH.needs_ticker(base("de_gen,en_gen,es_gen", False)) == "en_gen"     # no shot map: read the template
    assert GH.needs_ticker(base("de_gen,en_gen,es_gen", True)) is None          # the shot map says it all
    assert GH.needs_ticker(base("ar_gen,de,en,es_gen", True)) == "en"           # human commentary: rare techniques
    assert GH.needs_ticker(base(None, False)) is None
    assert GH.ticker_url(5181791, "en") == "https://data.fotmob.com/webcl/ltc/gsm/5181791_en.json.gz"


def test_poller_reads_the_ticker_once_and_keeps_it(tmp_path, fx, monkeypatch):
    """UAE league match (no shot map): the match file's goals get the ticker's reading; the ticker is asked once, not on
    every 20-second fetch, and again only while a goal still lacks its line (2 min apart)."""
    from datetime import datetime, timedelta, timezone
    import poller as P
    from store import Store, LocalBackend
    raw = fx("fotmob_match_uae_5898782.json")
    raw["content"]["liveticker"] = {"langs": "de_gen,en_gen", "teams": ["Al-Nasr SC", "Kalba FC"]}
    ticker = {"AutoCommentaries": True, "Events": [
        {"IncidentCode": "G", "Elapsed": 7, "ElapsedPlus": -1, "Description": "Goal! Al Nasr 0, Kalba 1. Nemanja Jovic (Kalba) header from the centre of the box to the bottom left corner. Assisted by X with a cross following a corner."},
        {"IncidentCode": "PSG", "Elapsed": 20, "ElapsedPlus": -1, "Description": "Goal! Al Nasr 0, Kalba 2. Saman Ghoddos (Kalba) converts the penalty with a left footed shot to the bottom right corner."},
        {"IncidentCode": "G", "Elapsed": 65, "ElapsedPlus": -1, "Description": "Goal! Al Nasr 1, Kalba 2. Abdoulaye Touré (Al Nasr) right footed shot from outside the box to the top left corner."}]}
    asked = []

    def get_json(url, headers=None, min_ttl=0):
        asked.append(url)
        return json.loads(json.dumps(ticker))
    monkeypatch.setattr(P.HTTP, "get_json", get_json)
    p = P.Poller(Store(LocalBackend(tmp_path)))
    p.load()
    t = [datetime(2026, 9, 27, 20, 0, tzinfo=timezone.utc)]
    p.now_fn = lambda: t[0]
    p.fm.match_raw = lambda mid: json.loads(json.dumps(raw))
    p.fetch_detail(5898782, "final")
    ev = {GH.goal_key(e): e for e in p.store.get_json("match/5898782.json")["events"] if "goal" in e["type"]}
    assert ev["7-1229101"]["how"] == {"key": "header+corner", "ar": "رأسية من ركنية"}
    assert ev["64-1441638"]["how"]["key"] == "right_foot+outside"       # FotMob 64', Opta 65'
    assert ev["20-532220"]["how"]["key"] == "penalty"
    assert "how" not in ev["77-581132"] or ev["77-581132"]["how"]["key"] == "penalty"
    assert asked == [GH.ticker_url(5898782, "en_gen")]
    p.fetch_detail(5898782, "repoll")                                    # 77' still has no line, but within 2 min
    assert len(asked) == 1
    t[0] += timedelta(minutes=3)
    p.fetch_detail(5898782, "repoll")
    assert len(asked) == 2                                              # asked again for the missing line
    ev = {GH.goal_key(e): e for e in p.store.get_json("match/5898782.json")["events"] if "goal" in e["type"]}
    assert ev["7-1229101"]["how"]["ar"] == "رأسية من ركنية"               # kept across fetches
    for _ in range(8):
        t[0] += timedelta(minutes=3)
        p.fetch_detail(5898782, "repoll")
    assert len(asked) == 6                                              # gives up after 6 tries


def test_matchx_goal_rows_append_the_label(fx):
    """db/matches.py: goal arrays keep their 7 fields and append [how_ar, how_key] when known (backward compatible);
    goals FotMob does not describe take the poller's ticker reading from v1/match/<id>.json."""
    from db import matches as MXS
    g = [e for e in MXS.compact(fx("fotmob_match_pl_xg.json"), 1)["events"] if e[1] == "g"]
    assert g[0][:7] == [63, "g", "h", 847983, "Lisandro Martínez", None, "own"] and g[0][7:] == ["هدف عكسي", "own_goal"]
    assert g[1][6] is None and g[1][8] == "right_foot+long"
    m = MXS.compact(fx("fotmob_match_uae_5898782.json"), 5898782)
    assert [len(e) for e in m["events"] if e[1] == "g"] == [7, 9, 7, 9]      # UAE league: only the penalties are known
    doc = {"events": [{"type": "goal", "minute": 7, "added": None, "player": {"id": 1229101}, "how": {"key": "header+corner", "ar": "رأسية من ركنية"}}]}
    g = [e for e in MXS.fill_how(m, doc)["events"] if e[1] == "g"]
    assert g[0][7:] == ["رأسية من ركنية", "header+corner"] and len(g[2]) == 7


def test_cards_copy_is_identical():
    """saas/cards vendors this module for /api/tifo/match; when the cards repo sits next to this one, the copy must match."""
    here = os.path.join(os.path.dirname(HERE), "compute", "goal_how.py")
    other = os.path.join(os.path.dirname(HERE), "..", "cards", "src", "goal_how.py")
    if not os.path.exists(other):
        pytest.skip("saas/cards not next to this checkout")
    assert open(here, encoding="utf-8").read() == open(other, encoding="utf-8").read()
