"""news/media.py: which official video goes with which match and which goal. Every title here is a real upload of the
channel named (2026-09-20 .. 09-30); the wrong ones are the traps the checks exist for."""
import json, os
from datetime import datetime, timezone
from news import media as M

HERE = os.path.dirname(os.path.abspath(__file__))
NATIONS = json.load(open(os.path.join(HERE, "..", "news", "nations.json"), encoding="utf-8"))
TEAMS = {
    "7795": {"name": "Saudi Arabia", "name_ar": "السعودية", "country": {"iso2": "SA", "national": True}},
    "5819": {"name": "Iraq", "name_ar": "العراق", "country": {"iso2": "IQ", "national": True}},
    "5824": {"name": "Oman", "name_ar": "عُمان", "country": {"iso2": "OM", "national": True}},
    "5821": {"name": "Kuwait", "name_ar": "الكويت", "country": {"iso2": "KW", "national": True}},
    "5901": {"name": "Bahrain", "name_ar": "البحرين", "country": {"iso2": "BH", "national": True}},
    "5789": {"name": "UAE", "name_ar": "الإمارات", "country": {"iso2": "AE", "national": True}},
    "8636": {"name": "Inter", "name_ar": "إنتر ميلان"},
    "9875": {"name": "Napoli", "name_ar": "نابولي"},
    "8633": {"name": "Real Madrid", "name_ar": "ريال مدريد"},
    "9906": {"name": "Atlético Madrid", "name_ar": "أتلتيكو مدريد"},
    "101918": {"name": "Al Nassr FC", "name_ar": "النصر"},
    "102123": {"name": "Al-Nasr SC", "name_ar": "النصر"},
    "8456": {"name": "Manchester City", "name_ar": "مانشستر سيتي"},
    "8472": {"name": "Sunderland", "name_ar": "سندرلاند"},
}
PLAYERS = {"101": {"ar": "عبدالله السالم"}, "102": {"ar": "عبد الله الحمدان"}, "201": {"ar": "ناصر الرواحي"}, "202": {"ar": "مصعب الشقصي"},
           "301": {"ar": "علي صالح"}, "401": {"ar": "إيرلينغ هالاند"}}
ALIASES = {"teams": {"Man City": "Manchester City", "Atleti": "Atlético Madrid"}}
N = M.Names(TEAMS, PLAYERS, {}, {}, ALIASES, NATIONS, national_comps={329, 114})
CH = {c["key"]: c for c in [
    {"key": "ksa", "name": "القنوات الرياضية السعودية", "lang": "ar", "kind": "broadcaster", "team": None, "comps": None},
    {"key": "saudint", "name": "المنتخب السعودي", "lang": "ar", "kind": "federation", "team": 7795, "comps": None},
    {"key": "seriea", "name": "الدوري الإيطالي", "lang": "it", "kind": "league", "team": None, "comps": {55}},
    {"key": "inter", "name": "إنتر", "lang": "it", "kind": "club", "team": 8636, "comps": None},
    {"key": "realmadrid", "name": "ريال مدريد", "lang": "es", "kind": "club", "team": 8633, "comps": None},
    {"key": "mancity", "name": "مانشستر سيتي", "lang": "en", "kind": "club", "team": 8456, "comps": None},
    {"key": "uaepl", "name": "دوري أدنوك", "lang": "ar", "kind": "league", "team": None, "comps": {538}},
    {"key": "bein", "name": "بي إن سبورتس", "lang": "ar", "kind": "broadcaster", "team": None, "comps": None},
]}


def team(i):
    t = TEAMS[str(i)]
    return {"id": i, "name": t["name"], "name_ar": t["name_ar"]}


def goal(minute, side, pid, name, score, typ="goal", added=None):
    return {"type": typ, "minute": minute, "added": added, "team": side, "player": {"id": pid, "name": name}, "score": {"home": score[0], "away": score[1]}}


KSA_IRQ = {"id": 6052048, "comp": 329, "kickoff_utc": "2026-09-29T17:30:00Z", "status": "finished", "score": {"home": 2, "away": 0},
           "home": team(7795), "away": team(5819),
           "periods": {"firstHalfStarted": "2026-09-29T17:32:32Z", "secondHalfStarted": "2026-09-29T18:37:26Z", "gameEnded": "2026-09-29T19:27:00Z"},
           "events": [goal(55, "home", 101, "Abdullah Al Salem", (1, 0)), goal(69, "home", 102, "Abdullah Al-Hamdan", (2, 0))]}
OMA_KUW = {"id": 6052049, "comp": 329, "kickoff_utc": "2026-09-29T17:30:00Z", "status": "finished", "score": {"home": 3, "away": 1},
           "home": team(5824), "away": team(5821),
           "periods": {"firstHalfStarted": "2026-09-29T17:32:32Z", "secondHalfStarted": "2026-09-29T18:39:05Z", "gameEnded": "2026-09-29T19:30:00Z"},
           "events": [goal(6, "away", 301, "Shabaib Al Khaldi", (0, 1)), goal(65, "home", 201, "Nasser Al-Rawahi", (1, 1)),
                      goal(81, "home", 201, "Nasser Al-Rawahi", (2, 1)), goal(84, "home", 202, "Musab Al-Shaqsy", (3, 1))]}
INTER_NAP = {"id": 700, "comp": 55, "kickoff_utc": "2026-09-28T18:45:00Z", "status": "finished", "score": {"home": 3, "away": 2},
             "home": team(8636), "away": team(9875), "periods": {"gameEnded": "2026-09-28T20:40:00Z"},
             "events": [goal(10, "away", 501, "Scott McTominay", (0, 1)), goal(30, "away", 502, "Rasmus Hojlund", (0, 2)),
                        goal(50, "home", 503, "Lautaro Martinez", (1, 2)), goal(70, "home", 503, "Lautaro Martinez", (2, 2)),
                        goal(88, "home", 504, "Marcus Thuram", (3, 2))]}
CITY_SUN = {"id": 800, "comp": 47, "kickoff_utc": "2026-09-20T14:00:00Z", "status": "finished", "score": {"home": 5, "away": 3},
            "home": team(8456), "away": team(8472), "periods": {"gameEnded": "2026-09-20T15:55:00Z"},
            "events": [goal(12, "home", 401, "Erling Haaland", (1, 0))]}
MATCHES = [KSA_IRQ, OMA_KUW, INTER_NAP, CITY_SUN]


def run(ch, title, at, matches=MATCHES, desc=""):
    v = {"id": "v" + str(abs(hash(title)) % 10 ** 8), "title": title, "desc": desc, "at": at, "ch": ch, "source": "youtube", "url": "https://www.youtube.com/watch?v=abcdefghijk"}
    trace = []
    out = M.attach([v], matches, N, CH, trace)
    res = {}
    for mid, r in out.items():
        if r["highlights"]:
            res[mid] = "highlights"
        for k in r["goals"]:
            res.setdefault(mid, []).append(k) if isinstance(res.get(mid), list) else res.__setitem__(mid, [k])
    return res, trace


def test_highlights_of_a_gulf_cup_match_in_arabic():
    r, _ = run("ksa", "ملخص مباراة السعودية 2 - 0 العراق | الجولة الثالثة ضمن بطولة كأس الخليج 2027", "2026-09-29T21:03:16Z")
    assert r == {6052048: "highlights"}
    r, _ = run("saudint", "ملخص و أهداف المباراة || السعودية 2 × 0 العراق - كأس الخليج 2027 - الجولة الثالثة", "2026-09-29T19:43:10Z")
    assert r == {6052048: "highlights"}


def test_clitics_and_the_other_spelling_of_a_country():
    r, _ = run("ksa", "أهداف مباراة عمان 3 - 1 الكويت | الجولة الثالثة ضمن بطولة كأس الخليج 2027", "2026-09-29T22:17:00Z")
    assert r == {6052049: "highlights"}
    r, _ = run("bein", "ملخص مباراة السعودية والعراق | كأس الخليج", "2026-09-29T20:00:00Z")
    assert r == {6052048: "highlights"}


def test_never_before_the_match_nor_live_nor_a_full_replay():
    assert run("ksa", "ملخص مباراة السعودية 2 - 0 العراق", "2026-09-29T17:00:00Z")[0] == {}          # published before kickoff
    assert run("ksa", "مباشر | مباراة السعودية والعراق - خليجي 27", "2026-09-29T17:20:00Z")[0] == {}
    assert run("ksa", "السعودية 2 - 0 العراق | دور المجموعات - خليجي 27 | المباراة كاملة", "2026-09-29T21:21:00Z")[0] == {}


def test_a_score_the_match_never_had_is_another_match():
    assert run("ksa", "ملخص مباراة السعودية 3 - 0 العراق", "2026-09-29T21:00:00Z")[0] == {}
    # the reverse order of a real score is fine: club and national channels put their own side first
    assert run("ksa", "ملخص مباراة العراق 0 - 2 السعودية", "2026-09-29T21:00:00Z")[0] == {6052048: "highlights"}


def test_last_seasons_full_match_between_the_same_clubs_is_left_out():
    # Serie A posted last season's Napoli-Inter replay two days after this season's Inter 3-2 Napoli
    assert run("seriea", "NAPOLI-INTER 3-1 | FULL MATCH | SERIE A 2025/26", "2026-09-30T15:00:19Z")[0] == {}
    assert run("seriea", "Extended Highlights 2008/09 | Milan 1-0 Inter | Il primo gol di Ronaldinho", "2026-09-28T23:00:00Z")[0] == {}
    assert run("seriea", "INTER-NAPOLI 3-2 | HIGHLIGHTS | SERIE A 2026/27", "2026-09-28T22:00:00Z")[0] == {700: "highlights"}


def test_a_summary_out_while_the_ball_is_in_play_is_not_this_matchs():
    # Napoli led 0-2 from minute 30: an old «0-2» summary posted at minute 35 carries a score this match had at that moment
    assert run("seriea", "INTER-NAPOLI 0-2 | HIGHLIGHTS", "2026-09-28T19:20:00Z")[0] == {}
    # at half-time (no half starts known: kickoff + 47 .. + 85 min) the first half's summary is fine
    assert run("seriea", "INTER-NAPOLI 0-2 | HIGHLIGHTS PRIMO TEMPO", "2026-09-28T19:40:00Z")[0] == {700: "highlights"}


def test_a_club_channel_may_name_only_the_opponent_and_classic_means_thriller_only_with_the_final_score():
    r, _ = run("mancity", "EXTENDED HIGHLIGHTS | Man City 5-3 Sunderland | A Premier League Classic at the Etihad!", "2026-09-20T23:00:07Z")
    assert r == {800: "highlights"}
    assert run("mancity", "HIGHLIGHTS | A Premier League Classic vs Sunderland", "2026-09-20T23:00:07Z")[0] == {}


def test_women_and_youth_matches_never_reach_the_mens_match():
    assert run("mancity", "Highlights: Man City Women 5-3 Sunderland", "2026-09-20T23:00:00Z")[0] == {}
    assert run("ksa", "ملخص مباراة السعودية 2 - 0 العراق تحت 23 سنة", "2026-09-29T21:00:00Z")[0] == {}
    # CAF TV's uploads are the women's AFCON between the same countries as the men's qualifiers
    mar_alg = {"id": 903, "comp": 114, "kickoff_utc": "2026-09-29T19:00:00Z", "status": "finished", "score": {"home": 1, "away": 0},
               "home": {"id": 6262, "name": "Morocco", "name_ar": "المغرب"}, "away": {"id": 6317, "name": "Algeria", "name_ar": "الجزائر"},
               "periods": {"gameEnded": "2026-09-29T20:55:00Z"}, "events": [goal(30, "home", 801, "Ayoub El Kaabi", (1, 0))]}
    caf = dict(CH["bein"], key="caf", lang="en", kind="confed", comps={114})
    CH["caf"] = caf
    assert run("caf", "Morocco 1-0 Algeria | Match Highlights | TotalEnergies WAFCON 2026 | 3rd Place", "2026-09-29T21:30:00Z", [mar_alg])[0] == {}
    assert run("caf", "Morocco 1-0 Algeria | Match Highlights | TotalEnergies AFCON 2027 Qualifiers", "2026-09-29T21:30:00Z", [mar_alg])[0] == {903: "highlights"}


def test_goal_clip_by_the_arabic_name_with_a_split_abd():
    r, _ = run("ksa", "الهدف الثاني لمنتخبنا الوطني سجله اللاعب عبدالله الحمدان- السعودية 2- العراق 0 #السعودية_العراق", "2026-09-29T19:11:00Z")
    assert r == {6052048: ["69-102"]}


def test_goal_clip_cannot_come_out_before_the_goal():
    assert run("ksa", "هدف عبدالله الحمدان في مرمى العراق", "2026-09-29T18:30:00Z")[0] == {}


def test_two_goals_by_one_player_told_apart_by_equaliser_words():
    r, _ = run("ksa", "ناصر الرواحي يحرز هدف التعادل لمنتخب عمان", "2026-09-29T19:25:00Z")
    assert r == {6052049: ["65-201"]}
    # nothing tells which of the two: left out
    assert run("ksa", "هدف ناصر الرواحي في مرمى الكويت", "2026-09-29T19:25:00Z")[0] == {}
    # published between his two goals: it can only be the first
    assert run("ksa", "هدف ناصر الرواحي في مرمى الكويت", "2026-09-29T19:05:00Z")[0] == {6052049: ["65-201"]}
    # a brace clip goes with both
    assert run("ksa", "ثنائية ناصر الرواحي في مرمى الكويت", "2026-09-29T19:40:00Z")[0] == {6052049: ["65-201", "81-201"]}


def test_goal_clip_score_and_minute_must_be_this_goals():
    assert run("inter", "LAUTARO MARTINEZ | GOAL 2-2 vs NAPOLI", "2026-09-28T20:30:00Z")[0] == {700: ["70-503"]}
    assert run("inter", "LAUTARO MARTINEZ GOAL 50' vs NAPOLI", "2026-09-28T20:30:00Z")[0] == {700: ["50-503"]}
    assert run("inter", "LAUTARO MARTINEZ GOAL 3-2 vs NAPOLI", "2026-09-28T20:30:00Z")[0] == {}


def test_compilations_reactions_and_saves_are_not_goal_clips():
    assert run("mancity", "Every Goal of 2026/27 So Far | Haaland & Cherki", "2026-09-20T18:00:00Z")[0] == {}
    assert run("inter", "THURAM'S REACTION TO LAUTARO'S GOAL VS NAPOLI!", "2026-09-28T21:00:00Z")[0] == {}
    assert run("mancity", "Haaland goal of the season contender!", "2026-09-20T18:00:00Z")[0] == {}


def test_a_goal_clip_on_another_clubs_channel_needs_the_match_named():
    assert run("realmadrid", "Haaland goal!", "2026-09-20T15:00:00Z")[0] == {}


def test_mls_full_match_highlights_is_a_summary_but_full_match_alone_is_a_replay():
    assert M.Text("Columbus Crew vs. Inter Miami CF | Full Match Highlights | STUNNING Messi FREE KICK").neg is None
    assert M.Text("NAPOLI-INTER 3-1 | FULL MATCH | SERIE A 2025/26").neg == "full match"


def test_titles_read_through_unicode_tricks():
    tx = M.Text("𝗠𝗔𝗧𝗖𝗛 𝗥𝗘𝗖𝗔𝗣 🇯🇴 🆚 🇸🇾")
    assert tx.hl
    tx = M.Text("⁨ لمسة ورا لمسة وهـدف رائع ⁩ #السعودية_عمان")
    assert tx.goal and not tx.scores
    assert M.Text("ملخص مباراة الامارات ٣ - ٠ البحرين").scores == [(3, 0)]
    assert M.Text("ملخص مباراة الوداد 1-3 اليوم 27-9-2026").scores == [(1, 3)]


USA_CHI = {"id": 900, "comp": 114, "kickoff_utc": "2026-09-30T00:00:00Z", "status": "finished", "score": {"home": 4, "away": 2},
           "home": {"id": 6713, "name": "USA", "name_ar": "أمريكا"}, "away": {"id": 6711, "name": "Chile", "name_ar": "تشيلي"},
           "periods": {"firstHalfStarted": "2026-09-30T00:08:06Z", "secondHalfStarted": "2026-09-30T01:10:53Z", "gameEnded": "2026-09-30T02:02:00Z"},
           "events": [goal(37, "home", 601, "Sebastian Berhalter", (1, 0)), goal(51, "home", 602, "Julian Hall", (2, 2)),
                      goal(72, "home", 603, "Chris Richards", (3, 2))]}
MEX_PER = {"id": 901, "comp": 114, "kickoff_utc": "2026-09-30T01:00:00Z", "status": "finished", "score": {"home": 1, "away": 1},
           "home": {"id": 6710, "name": "Mexico", "name_ar": "المكسيك"}, "away": {"id": 5798, "name": "Peru", "name_ar": "بيرو"},
           "periods": {"firstHalfStarted": "2026-09-30T01:01:32Z", "secondHalfStarted": "2026-09-30T02:06:14Z", "gameEnded": "2026-09-30T02:58:00Z"},
           "events": [goal(27, "away", 701, "Jairo Vélez", (0, 1)), goal(49, "home", 702, "Víctor Guzmán", (1, 1))]}
JOR_SYR = {"id": 902, "comp": 114, "kickoff_utc": "2026-09-27T17:00:00Z", "status": "finished", "score": {"home": 1, "away": 1},
           "home": {"id": 5816, "name": "Jordan", "name_ar": "الأردن"}, "away": {"id": 6320, "name": "Syria", "name_ar": "سوريا"},
           "periods": {"gameEnded": "2026-09-27T18:55:00Z"}, "events": []}
CH.update({c["key"]: c for c in [
    {"key": "ussoccer", "name": "منتخب أمريكا", "lang": "en", "kind": "federation", "team": 6713, "comps": None},
    {"key": "tudn", "name": "TUDN", "lang": "es", "kind": "broadcaster", "team": None, "comps": {114}},
    {"key": "jfa", "name": "الاتحاد الأردني", "lang": "ar", "kind": "federation", "team": 5816, "comps": None},
    {"key": "x_saudint", "name": "المنتخب السعودي", "lang": "ar", "kind": "club", "team": 7795, "comps": None, "platform": "x"}]})


def test_a_clip_of_the_same_scorer_from_the_previous_match_is_left_out():
    # US Soccer posted Hall's and Berhalter's goals against Peru (27-28 Sep); both scored again against Chile on the 30th
    assert run("ussoccer", "A Brilliant Buildup for Julian Hall's First #USMNT Goal!", "2026-09-27T22:45:00Z", [USA_CHI])[0] == {}
    assert run("ussoccer", "Chris Richards Heads In The Match-Winner Against Chile!", "2026-09-30T18:20:27Z", [USA_CHI])[0] == {900: ["72-603"]}


def test_goal_for_a_side_that_had_scored_once_is_that_goal():
    assert run("tudn", "GOAL FOR PERU! Mexico vs Peru | Friendly - Friendly | TUDN", "2026-09-30T01:33:54Z", [MEX_PER])[0] == {901: ["27-701"]}
    assert run("tudn", "¡GOOL DE MÉXICO! México vs Perú | Amistoso - Amistoso | TUDN", "2026-09-30T02:14:42Z", [MEX_PER])[0] == {901: ["49-702"]}
    # a penalty shout, a save, no side named: not a goal clip
    assert run("tudn", "THAT WAS A PENALTY FOR EL TRI! Mexico vs Peru | Friendly", "2026-09-30T01:32:00Z", [MEX_PER])[0] == {}
    assert run("tudn", "¡GOLAZO! Mexico vs Peru | Friendly", "2026-09-30T01:33:00Z", [MEX_PER])[0] == {}
    assert run("tudn", "ALMOST A GOAL FOR MEXICO! Mexico vs Peru", "2026-09-30T01:40:00Z", [MEX_PER])[0] == {}


def test_two_flags_either_side_of_vs_name_two_national_teams():
    assert run("jfa", "🎥 | 𝗠𝗔𝗧𝗖𝗛 𝗥𝗘𝗖𝗔𝗣 🇯🇴 🆚 🇸🇾", "2026-09-28T10:26:50Z", [JOR_SYR])[0] == {902: "highlights"}
    assert run("jfa", "🎥 | 𝗠𝗔𝗧𝗖𝗛 𝗥𝗘𝗖𝗔𝗣 🇯🇴 🇸🇾", "2026-09-28T10:26:50Z", [JOR_SYR])[0] == {}      # flags alone, no «vs»


def test_the_same_two_countries_in_another_sport_on_a_broadcasters_channel():
    assert run("ksa", "ملخص مباراة السعودية والعراق | كرة اليد | دورة الألعاب الآسيوية", "2026-09-29T21:00:00Z")[0] == {}
    assert run("bein", "ملخص مباراة السعودية والعراق | كرة الصالات", "2026-09-29T21:00:00Z")[0] == {}


def test_a_live_match_file_read_before_the_clip_cannot_place_it():
    live = dict(KSA_IRQ, status="live", _fetched="2026-09-29T19:05:00Z", _fstatus="live")
    title = "الهدف الثاني لمنتخبنا الوطني سجله اللاعب عبدالله الحمدان- السعودية 2- العراق 0"
    r, tr = run("ksa", title, "2026-09-29T19:11:00Z", [live])
    assert r == {} and any(t["result"] == "the match file may not have that goal yet" for t in tr)
    later = dict(live, _fetched="2026-09-29T19:30:00Z")
    assert run("ksa", title, "2026-09-29T19:11:00Z", [later])[0] == {6052048: ["69-102"]}


def test_x_posts_only_with_a_video_from_an_official_account():
    box = {"items": [{"id": "1", "handle": "SaudiNT", "text": "هدف عبدالله الحمدان في مرمى العراق ⚽️", "at": "2026-09-29T19:10:00.000Z",
                      "url": "https://x.com/SaudiNT/status/1", "video": True, "tier": "official"},
                     {"id": "2", "handle": "SaudiNT", "text": "هدف عبدالله الحمدان في مرمى العراق ⚽️", "at": "2026-09-29T19:10:00.000Z",
                      "url": "https://x.com/SaudiNT/status/2", "video": False, "tier": "official"},
                     {"id": "3", "handle": "kooora", "text": "هدف عبدالله الحمدان في مرمى العراق", "at": "2026-09-29T19:10:00.000Z",
                      "url": "https://x.com/kooora/status/3", "video": True, "tier": "paper"}]}
    acc = [{"handle": "SaudiNT", "tier": "official", "team": 7795, "name": "المنتخب السعودي", "lang": "ar"}, {"handle": "kooora", "tier": "paper"}]
    vids = M.x_videos(box, acc)
    assert [v["id"] for v in vids] == ["x1"]
    out = M.attach(vids, [KSA_IRQ], N, CH)
    assert list(out[6052048]["goals"]) == ["69-102"]


def test_step_writes_a_file_per_match_with_media_and_nothing_when_unchanged(tmp_path, monkeypatch):
    from store import Store, LocalBackend
    store = Store(LocalBackend(str(tmp_path)))
    md = dict(KSA_IRQ, highlights={"url": "https://www.youtube.com/watch?v=FOTMOBVID01", "image": None, "source": "www.youtube.com"})
    day = {"matches": [{k: md[k] for k in ("id", "comp", "kickoff_utc", "status", "score", "home", "away")}]}
    store.put_json("day/20260929.json", day); store.put_json("day/20260930.json", {"matches": []})
    store.put_json(f"match/{md['id']}.json", md)
    store.put_json("teams.json", {"teams": TEAMS})
    items = [{"url": "https://www.youtube.com/watch?v=aaaaaaaaaaa", "title": "ملخص مباراة السعودية 2 - 0 العراق | كأس الخليج", "desc": "", "at": "2026-09-29T21:03:16Z"},
             {"url": "https://www.youtube.com/shorts/bbbbbbbbbbb", "title": "الهدف الثاني لمنتخبنا الوطني سجله اللاعب عبدالله الحمدان- السعودية 2- العراق 0", "desc": "", "at": "2026-09-29T19:11:10Z"},
             {"url": "https://www.youtube.com/watch?v=ccccccccccc", "title": "مباشر | السعودية والعراق", "desc": "", "at": "2026-09-29T17:10:00Z"}]
    monkeypatch.setattr(M, "fetch_feeds", lambda chs, prefetched=None, workers=6: ({"yt_ksasports": items}, {}))
    monkeypatch.setattr(M, "oembed", lambda vid: {"s": 200, "title": "t", "author": "a"})
    monkeypatch.setattr(M, "load_names", lambda store, nat, cache_dir=None: M.Names(TEAMS, PLAYERS, {}, {}, ALIASES, NATIONS, {329}))
    cfg = {"youtube": [], "media": {"youtube": [{"key": "yt_ksasports", "channel": "UCLo2xigvxv9ksxp78AyCBTw", "name": "القنوات الرياضية السعودية", "lang": "ar", "kind": "broadcaster"}]}, "x": {"accounts": []}}
    t = datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc)
    res = M.step(store, cfg, t=t)
    assert res["written"] == 1 and res["with_media"] == 1
    doc = store.get_json(f"media/{md['id']}.json")
    assert [h["id"] for h in doc["highlights"]] == ["aaaaaaaaaaa", "FOTMOBVID01"]       # ours first, FotMob's link kept too
    assert doc["highlights"][0]["kind"] == "summary" and doc["highlights"][1]["found_by"] == "fotmob"
    assert list(doc["goals"]) == ["69-102"] and doc["goals"]["69-102"][0]["vertical"] is True
    assert store.get_json("media/recent.json")["matches"][0]["id"] == md["id"]
    assert M.step(store, cfg, t=t)["written"] == 0                                        # same content: nothing uploaded


def test_goal_time_uses_the_real_half_starts():
    t = M.goal_time(KSA_IRQ, 69, None)
    assert t == datetime(2026, 9, 29, 19, 0, 26, tzinfo=timezone.utc)      # 18:37:26 + 23 min
    assert M.goal_time(KSA_IRQ, 45, 3) == datetime(2026, 9, 29, 18, 19, 32, tzinfo=timezone.utc)
