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


def test_a_broadcasters_x_account_is_held_to_its_competitions():
    # 2026-10-07: AD Sports on X (`kind: broadcaster`, comps [538, 329]) for the Gulf Cup; a clip of another competition is not its
    acc = [{"handle": "ADSportsTV", "name": "أبوظبي الرياضية", "lang": "ar", "tier": "official", "kind": "broadcaster", "comps": [538, 329]},
           {"handle": "uaefa_ae", "name": "اتحاد الإمارات", "lang": "ar", "tier": "official", "team": 5789},
           {"handle": "kooora", "name": "كووورة", "lang": "ar", "tier": "paper"}]
    chs = {c["key"]: c for c in M.x_channels(acc)}
    assert set(chs) == {"x_adsportstv", "x_uaefa_ae"}                                  # press is never a video source
    assert chs["x_adsportstv"]["comps"] == {538, 329} and chs["x_adsportstv"]["kind"] == "broadcaster" and chs["x_adsportstv"]["team"] is None
    assert chs["x_uaefa_ae"]["team"] == 5789 and chs["x_uaefa_ae"]["comps"] is None
    box = {"items": [{"id": "1", "handle": "ADSportsTV", "text": "ملخص مباراة السعودية 2 - 0 العراق | كأس الخليج", "at": "2026-09-29T21:00:00Z",
                      "video": True, "url": "https://x.com/ADSportsTV/status/1", "image": None}]}
    v = M.x_videos(box, acc)
    out = M.attach(v, MATCHES, N, dict(CH, **chs))
    assert list(out) == [KSA_IRQ["id"]] and out[KSA_IRQ["id"]]["highlights"]
    inter = dict(box["items"][0], id="2", text="ملخص مباراة إنتر ميلان 3 - 2 نابولي", url="https://x.com/ADSportsTV/status/2")
    assert M.attach(M.x_videos({"items": [inter]}, acc), MATCHES, N, dict(CH, **chs)) == {}     # Serie A is not AD Sports'


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


def _ksa_store(tmp_path):
    from store import Store, LocalBackend
    store = Store(LocalBackend(str(tmp_path)))
    day = {"matches": [{k: KSA_IRQ[k] for k in ("id", "comp", "kickoff_utc", "status", "score", "home", "away")}]}
    store.put_json("day/20260929.json", day); store.put_json("day/20260930.json", {"matches": []})
    store.put_json(f"match/{KSA_IRQ['id']}.json", KSA_IRQ)
    store.put_json("teams.json", {"teams": TEAMS})
    return store


CFG_KSA = {"youtube": [], "media": {"youtube": [{"key": "yt_ksasports", "channel": "UCLo2xigvxv9ksxp78AyCBTw", "name": "القنوات الرياضية السعودية",
                                                   "lang": "ar", "kind": "broadcaster"}], "block": ["blockedvid1"]}, "x": {"accounts": []}}


def test_step_keeps_what_the_backfill_found_and_never_a_blocked_one(tmp_path, monkeypatch):
    store = _ksa_store(tmp_path)
    old = {"id": "oldclip0001", "url": "https://www.youtube.com/watch?v=oldclip0001", "title": "هدف عبدالله السالم", "source": "youtube",
           "channel": "x", "published": "2026-09-29T18:40:00Z", "embed": True, "conf": 80, "found_by": "tifo"}
    store.put_state(M.EXTRA, {"matches": {str(KSA_IRQ["id"]): {"highlights": [], "goals": {"55-101": [old, dict(old, id="blockedvid1")]}}}})
    monkeypatch.setattr(M, "fetch_feeds", lambda chs, prefetched=None, workers=6: ({"yt_ksasports": []}, {}))
    monkeypatch.setattr(M, "oembed", lambda vid: {"s": 200})
    monkeypatch.setattr(M, "load_names", lambda store, nat, cache_dir=None: M.Names(TEAMS, PLAYERS, {}, {}, ALIASES, NATIONS, {329}))
    res = M.step(store, CFG_KSA, t=datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc))
    assert res["written"] == 1
    doc = store.get_json(f"media/{KSA_IRQ['id']}.json")
    assert [c["id"] for c in doc["goals"]["55-101"]] == ["oldclip0001"]          # its feed no longer holds it: still there


def test_backfill_adds_to_the_published_file_and_takes_nothing_away(tmp_path, monkeypatch):
    from news import media_backfill as B
    store = _ksa_store(tmp_path)
    kept = {"id": "kept0000001", "url": "https://www.youtube.com/watch?v=kept0000001", "title": "ملخص مباراة السعودية والعراق", "source": "youtube",
            "channel": "x", "published": "2026-09-29T21:00:00Z", "embed": True, "conf": 90, "found_by": "tifo", "kind": "summary"}
    store.put_json(f"media/{KSA_IRQ['id']}.json", {"generated": "2026-09-29T21:05:00Z", "match": KSA_IRQ["id"], "highlights": [kept], "goals": {}})
    clip = {"id": "bbbbbbbbbbb", "source": "youtube", "url": "https://www.youtube.com/watch?v=bbbbbbbbbbb", "vertical": True,
            "title": "الهدف الثاني لمنتخبنا الوطني سجله اللاعب عبدالله الحمدان- السعودية 2- العراق 0", "desc": "",
            "at": "2026-09-29T19:11:10Z", "ch": "yt_ksasports", "image": None}
    monkeypatch.setattr(B, "youtube_videos", lambda chs, ctx, t0, relist=False, log=print, store=None, remote=False: [clip])
    monkeypatch.setattr(B, "CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(M, "oembed", lambda vid: {"s": 200})
    monkeypatch.setattr(M, "load_names", lambda store, nat, cache_dir=None: M.Names(TEAMS, PLAYERS, {}, {}, ALIASES, NATIONS, {329}))
    monkeypatch.setattr(M, "national_comps", lambda: frozenset({329}))
    t = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    res = B.run(store, CFG_KSA, t=t, days=3, log=lambda *a: None)
    doc = store.get_json(f"media/{KSA_IRQ['id']}.json")
    assert [h["id"] for h in doc["highlights"]] == ["kept0000001"]
    assert [c["id"] for c in doc["goals"]["69-102"]] == ["bbbbbbbbbbb"]
    assert res["goal_keys_added"] == 1 and res["total"] == {"goals": 2, "before": 0, "after": 1}
    extra = store.get_state(M.EXTRA)["matches"][str(KSA_IRQ["id"])]
    assert list(extra["goals"]) == ["69-102"]
    assert B.run(store, CFG_KSA, t=t, days=3, log=lambda *a: None)["written"] == 0      # a second run adds nothing


def test_a_title_naming_the_matchs_other_scorers_is_its_goals_not_one_goal():
    # Real Madrid's «A GOAL FEST at the Bernabéu! MBAPPÉ, ARDA GÜLER and DIOMANDE shine | Real Madrid 4-1 Leipzig» (2026-11-19)
    assert run("inter", "A GOAL FEST at San Siro! Thuram, Hojlund and McTominay shine | Inter 3-2 Napoli", "2026-09-28T20:50:00Z")[0] == {}
    assert run("inter", "Thuram scores the winner! Inter 3-2 Napoli", "2026-09-28T20:50:00Z")[0] == {700: ["88-504"]}
    # one teammate named beside the scorer (the assist) is still his goal's clip
    assert run("inter", "Martinez sets up Thuram for the winner! Inter 3-2 Napoli", "2026-09-28T20:50:00Z")[0] == {700: ["88-504"]}


def test_a_celebration_clip_is_not_the_goal():
    assert run("inter", "Thuram celebrando su gol del triunfo, Inter 3-2 Napoli", "2026-09-28T20:50:00Z", desc="")[0] == {}


def test_fotmobs_summary_on_every_event_goes_with_the_highlights_not_under_a_goal():
    # FotMob copies one match's summary onto every event, cards too (Al Jazira - Al Wasl, 2026-11-19); a goal's own link stays
    summ = "https://www.youtube.com/watch?v=SUMMARY0001"
    full = dict(KSA_IRQ, events=[dict(KSA_IRQ["events"][0], clip=summ), {"type": "yellow", "minute": 60, "clip": summ},
                                 dict(KSA_IRQ["events"][1], clip="https://www.youtube.com/watch?v=OWNCLIP0001")])
    md = M.slim(full)
    found = M.fotmob_links({}, [md], {}, set())
    assert [v["id"] for v, _ in found[KSA_IRQ["id"]]["highlights"]] == ["SUMMARY0001"]
    assert {k: [v["id"] for v, _ in l] for k, l in found[KSA_IRQ["id"]]["goals"].items()} == {"69-102": ["OWNCLIP0001"]}
    assert M.own_clip_keys({"highlights": [], "goals": {"55-101": [{"url": "a"}], "69-102": [{"url": "a"}], "70-1": [{"url": "b"}]}}) == {"70-1"}


def test_goal_key_is_the_minute_the_page_shows():
    # the match page's rows: data-goal-key="45+4-301" (render.js / v3.js)
    assert M.goal_key(goal(45, "home", 301, "Ali Saleh", (1, 1), added=4)) == "45+4-301"
    assert M.goal_key(goal(69, "home", 102, "Abdullah Al-Hamdan", (2, 0))) == "69-102"
    uae_qat = {"id": 904, "comp": 329, "kickoff_utc": "2026-09-30T17:30:00Z", "status": "finished", "score": {"home": 1, "away": 1},
               "home": team(5789), "away": {"id": 5902, "name": "Qatar", "name_ar": "قطر"},
               "periods": {"firstHalfStarted": "2026-09-30T17:31:08Z", "secondHalfStarted": "2026-09-30T18:37:37Z", "gameEnded": "2026-09-30T19:30:00Z"},
               "events": [goal(33, "away", 401, "Almoez Ali", (0, 1)), goal(45, "home", 301, "Ali Saleh", (1, 1), added=4)]}
    assert run("ksa", "هدف علي صالح في مرمى قطر", "2026-09-30T18:25:00Z", [uae_qat])[0] == {904: ["45+4-301"]}


def test_goal_time_uses_the_real_half_starts():
    t = M.goal_time(KSA_IRQ, 69, None)
    assert t == datetime(2026, 9, 29, 19, 0, 26, tzinfo=timezone.utc)      # 18:37:26 + 23 min
    assert M.goal_time(KSA_IRQ, 45, 3) == datetime(2026, 9, 29, 18, 19, 32, tzinfo=timezone.utc)


# Al Ain 2-1 Al Dhafra, UAE Pro League, 2026-11-19: the club's and Abu Dhabi Sports' own X clips of the two Al Ain goals were
# all missed (only the 66' went up on TikTok). Real titles and times.
AIN_DHA = {"id": 1000022241, "comp": 538, "kickoff_utc": "2026-11-19T15:25:00Z", "status": "finished", "score": {"home": 2, "away": 1},
           "home": {"id": 102117, "name": "Al-Ain", "name_ar": "العين"}, "away": {"id": 102118, "name": "Al-Dhafra", "name_ar": "الظفرة"},
           "periods": {"firstHalfStarted": "2026-11-19T15:26:01Z", "firstHalfEnded": "2026-11-19T16:14:10Z",
                       "secondHalfStarted": "2026-11-19T16:30:46Z", "gameEnded": "2026-11-19T17:20:56Z"},
           "events": [goal(43, "home", 1572471, "Marcos André", (1, 0)), goal(54, "home", 1295519, "Houssine Rahimi", (2, 0)),
                      goal(66, "away", 794049, "Abdulla Al Karbi", (2, 1))]}
import yaml
N_AE = M.Names({"102117": {"name": "Al-Ain", "name_ar": "العين"}, "102118": {"name": "Al-Dhafra", "name_ar": "الظفرة"}},
               {"1572471": {"ar": "ماركوس أندريه"}, "1295519": {"ar": "حسين رحيمي"}, "794049": {"ar": "عبدالله الكربي"}}, {}, {},
               yaml.safe_load(open(os.path.join(HERE, "..", "news", "aliases.yaml"), encoding="utf-8")), NATIONS)
CH_AE = {c["key"]: c for c in M.x_channels([
    {"handle": "ADSportsTV", "name": "أبوظبي الرياضية", "lang": "ar", "tier": "official", "kind": "broadcaster", "comps": [538, 11027, 9943, 11026, 329]},
    {"handle": "alainfcae", "name": "العين", "lang": "ar", "tier": "official", "team": 102117}])}


def run_ae(handle, title, at):
    v = {"id": "x" + str(abs(hash(title)) % 10 ** 8), "title": title, "desc": "", "at": at, "ch": "x_" + handle.lower(), "source": "x",
         "url": "https://x.com/" + handle + "/status/1"}
    out = M.attach([v], [AIN_DHA], N_AE, CH_AE, [])
    return {mid: sorted(r["goals"]) for mid, r in out.items() if r["goals"]}


def test_the_clubs_drawn_out_name_and_its_nickname_for_a_player():
    # «ماركو ماياااا»: letters drawn out for the cheer, and the name the club and the broadcaster use for FotMob's «Marcos André»
    assert run_ae("alainfcae", "د43: ماركو ماياااا يفتتح أهداف الزعيم ⚽️\n\n#العين_الظفرة 1⃣ - 0⃣ | #دوري_أدنوك_للمحترفين",
                  "2026-11-19T16:10:10Z") == {1000022241: ["43-1572471"]}
    assert run_ae("ADSportsTV", "ماركوس مايا يفتتح التسجيل ويضع العين في المقدمة ⚽️\n\n#العين_الظفرة \n#دوري_أدنوك_للمحترفين | #أبوظبي_الرياضية 1⃣",
                  "2026-11-19T16:12:36Z") == {1000022241: ["43-1572471"]}


def test_the_second_of_the_teams_goals_is_one_goal():
    # «ثاني أهداف الزعيم» is the club's second goal, not its goals
    assert run_ae("alainfcae", "د54: حسييييين رحيمي يسجل ثااااااااني أهداف الزعيم 🔥\n\n#العين_الظفرة 2⃣ - 0⃣ | #دوري_أدنوك_للمحترفين",
                  "2026-11-19T16:40:27Z") == {1000022241: ["54-1295519"]}
    # the number is checked: his goal made it 2-0, not 3-0
    assert run_ae("alainfcae", "حسين رحيمي يسجل ثالث أهداف الزعيم", "2026-11-19T16:40:27Z") == {}


def test_a_rebound_off_the_post_that_the_title_says_went_in():
    assert run_ae("ADSportsTV", "القائم يرفض تسديدة كاكو.. والحسين رحيمي يكمل المهمة من متابعة سريعة تمنح العين الهدف الثاني ⚽️\n\n"
                  "#العين_الظفرة  #دوري_أدنوك_للمحترفين | #أبوظبي_الرياضية 1⃣", "2026-11-19T16:43:30Z") == {1000022241: ["54-1295519"]}
    # the post alone, a miss, or a goal number that is not his are still no goal
    assert run_ae("ADSportsTV", "تسديدة الحسين رحيمي ترتطم بالقائم #العين_الظفرة", "2026-11-19T16:43:30Z") == {}
    assert run_ae("ADSportsTV", "فرصة الهدف الثالث تضيع من الحسين رحيمي #العين_الظفرة", "2026-11-19T16:46:04Z") == {}
    assert run_ae("ADSportsTV", "القائم يحرم الحسين رحيمي من الهدف الثالث #العين_الظفرة", "2026-11-19T16:46:04Z") == {}


def test_a_video_uploaded_before_the_goal_is_not_that_goal():
    # Al Ain's «د43: ماركو ماياااا …» post carried a goal animation uploaded to X on 22 August and posted again for every goal
    # (owner 2026-11-19: «يرسل صورة متحركة مصورة مسبقاً»): the video's own id dates it
    acc = [{"handle": "alainfcae", "name": "العين", "lang": "ar", "tier": "official", "team": 102117}]
    def post(img):
        return {"items": [{"id": "2123448758813798726", "handle": "alainfcae", "video": True, "at": "2026-11-19T16:10:10.000Z",
                           "url": "https://x.com/alainfcae/status/2123448758813798726", "image": img,
                           "text": "د43: ماركو ماياااا يفتتح أهداف الزعيم ⚽️\n\n#العين_الظفرة 1⃣ - 0⃣ | #دوري_أدنوك_للمحترفين"}]}
    old = M.x_videos(post("https://pbs.twimg.com/amplify_video_thumb/2091176454193127424/img/NNNgbP5lZaxfNo98.jpg"), acc)
    assert old[0]["made"] == "2026-08-22T14:51:33Z"
    assert M.attach(old, [AIN_DHA], N_AE, CH_AE, []) == {}
    # uploaded after the goal: fine; a custom thumbnail tells nothing, so nothing is held against it
    new = M.x_videos(post("https://pbs.twimg.com/amplify_video_thumb/2123448700000000000/img/x.jpg"), acc)
    assert sorted(M.attach(new, [AIN_DHA], N_AE, CH_AE, [])[1000022241]["goals"]) == ["43-1572471"]
    assert M.x_videos(post("https://pbs.twimg.com/media/HXgB47CWkAA6cs1.jpg"), acc)[0].get("made") is None


def test_the_clubs_own_clip_with_the_minute_needs_no_name_we_know():
    # a club posts «د43: <the name it uses>»: its channel, the minute and its one goal at that minute say which goal it is
    assert run_ae("alainfcae", "د43: ماركينيو يفتتح التسجيل ⚽️ #العين_الظفرة", "2026-11-19T16:10:10Z") == {1000022241: ["43-1572471"]}
    assert run_ae("alainfcae", "43' ماركينيو يسجل للزعيم ⚽️", "2026-11-19T16:10:10Z") == {1000022241: ["43-1572471"]}
    # no goal of the club at that minute (66' was Al Dhafra's), or a minute it has not reached yet: nothing
    assert run_ae("alainfcae", "د50: ماركينيو يسجل ⚽️ #العين_الظفرة", "2026-11-19T16:40:27Z") == {}
    assert run_ae("alainfcae", "د66: الهدف الأول للظفرة ⚽️ #العين_الظفرة", "2026-11-19T16:55:00Z") == {}
    assert run_ae("alainfcae", "د54: ماركينيو يسجل ⚽️ #العين_الظفرة", "2026-11-19T16:12:00Z") == {}
    # a broadcaster's or another club's channel is not the club: the name still has to be known there
    assert run_ae("ADSportsTV", "د43: ماركينيو يفتتح التسجيل ⚽️ #العين_الظفرة", "2026-11-19T16:12:36Z") == {}
    # a miss at that minute is still not a goal, and the club's ready-made animation is still not the goal
    assert run_ae("alainfcae", "د43: فرصة ضائعة من ماركينيو #العين_الظفرة", "2026-11-19T16:10:10Z") == {}
    acc = [{"handle": "alainfcae", "name": "العين", "lang": "ar", "tier": "official", "team": 102117}]
    old = M.x_videos({"items": [{"id": "2123448758813798726", "handle": "alainfcae", "video": True, "at": "2026-11-19T16:10:10.000Z",
                                 "url": "u", "text": "د43: ماركينيو يفتتح التسجيل ⚽️",
                                 "image": "https://pbs.twimg.com/amplify_video_thumb/2091176454193127424/img/a.jpg"}]}, acc)
    assert M.attach(old, [AIN_DHA], N_AE, CH_AE, []) == {}


def test_a_scorers_name_spelt_another_way_still_names_him():
    # 2026-11-19 report: «منذر طمين»/«منذر تيمين», «عبد الله الزياني»/«عبد الله زياني», «هوجو»/«هوغو». A whole name spelt with
    # ط/ت, غ/ج/ق, «ال» or one long vowel more or less names the scorer
    assert run_ae("ADSportsTV", "ماركوس اندري يفتتح التسجيل ويضع العين في المقدمة ⚽️ #العين_الظفرة", "2026-11-19T16:12:36Z") \
        == {1000022241: ["43-1572471"]}
    assert run_ae("ADSportsTV", "حسين الرحيمي يسجل الهدف الثاني للعين ⚽️ #العين_الظفرة", "2026-11-19T16:43:30Z") == {1000022241: ["54-1295519"]}
    assert run_ae("ADSportsTV", "عبدالله الكربى يقلص الفارق بالهدف الأول للظفرة ⚽️ #العين_الظفرة", "2026-11-19T16:55:01Z") \
        == {1000022241: ["66-794049"]}
    # one word spelt loosely is not enough on its own (it could be anyone's)
    assert run_ae("ADSportsTV", "رحيم يسجل الهدف الثاني للعين ⚽️", "2026-11-19T16:43:30Z") == {}
    assert M.loose("طمين") & M.loose("تيمين") and M.loose("هوجو") & M.loose("هوغو") and M.loose("الزياني") & M.loose("زياني")
    assert not M.loose("حسين") & M.loose("محسن") and not M.loose("goal")


def test_the_graphs_other_arabic_names_of_a_player_name_him():
    # the Tifo graph publishes every Arabic form it holds per FotMob player id (state graph/player_aliases_ar.json.gz):
    # «سيرجيو بيريرا» for the «سيرجينيو» of the dictionary (Al Wasl 2-1 Hatta, 2026-11-19)
    n = M.Names({}, {"1572471": {"ar": "سيرجينيو"}}, {}, {}, {}, NATIONS, player_aliases={"1572471": ["سيرجيو بيريرا", ""]})
    assert n.player(1572471, "Serginho").get(("سيرجيو", "بيريرا")) == 3
    assert n.player(1572471, "Serginho").get(("سيرجينيو",)) == 2
    assert M.Names({}, {}, {}, {}, {}, NATIONS).player(1, "X") == M.player_forms("X", [])


# Abu Dhabi Sports' YouTube highlights, out the same evening and named by the result alone (2026-11-19, real titles and times):
# the pages waited 3-5 days for the league's own «ملخص وأهداف مباراة …» instead (owner: «ملخصات المباريات تنزل فصفحة المباراة
# لما تتوفر، نفس ما الاهداف تنزل؟»)
CH_YT_AE = {c["key"]: c for c in M.channels({"youtube": [], "media": {"youtube": [
    {"key": "yt_adsports", "channel": "UCF8Fpc7bPHC8Jrflci-mUiQ", "name": "أبوظبي الرياضية", "lang": "ar", "kind": "broadcaster",
     "home": [538, 11027, 9943, 11026, 329]},
    {"key": "yt_elsewhere", "channel": "UCxxxxxxxxxxxxxxxxxxxxxx", "name": "قناة", "lang": "ar", "kind": "broadcaster"}]}})}
CH_YT_AE.update(CH_AE)


def hl_of(ch, title, at, match=AIN_DHA):
    src = "x" if ch.startswith("x_") else "youtube"
    v = {"id": "v" + str(abs(hash(ch + title + at)) % 10 ** 9), "title": title, "desc": "", "at": at, "ch": ch, "source": src,
         "url": "https://www.youtube.com/watch?v=" + "a" * 11}
    trace = []
    out = M.attach([v], [match], N_AE, CH_YT_AE, trace)
    return [mid for mid, r in out.items() if r["highlights"]], trace


def test_a_broadcasters_upload_named_by_the_result_alone_is_the_matchs_highlights():
    assert hl_of("yt_adsports", "العين 2 - 1 الظفرة | الجولة 9 - دوري أدنوك للمحترفين 2026 - 2027", "2026-11-19T17:23:01Z")[0] == [1000022241]
    # the same channel's full match and live stream are not
    assert hl_of("yt_adsports", "العين 2 - 1 الظفرة | الجولة 9 - دوري أدنوك للمحترفين 2026 - 2027 | المباراة كاملة", "2026-11-19T18:01:00Z")[0] == []
    assert hl_of("yt_adsports", "مباشر | دوري أدنوك للمحترفين | الجولة 9", "2026-11-19T17:53:00Z")[0] == []


def test_a_result_title_is_two_names_and_a_score_and_nothing_else():
    # a coach after the match, the score in his words: not the highlights
    got, trace = hl_of("yt_adsports", "مدرب العين بعد الفوز 2-1 على الظفرة | دوري أدنوك للمحترفين", "2026-11-19T18:10:00Z")
    assert got == []
    # an X post shaped like a result carries one goal or a card, not the summary
    assert hl_of("x_adsportstv", "العين 2 - 1 الظفرة | الجولة 9 - دوري أدنوك للمحترفين", "2026-11-19T17:23:01Z")[0] == []


def test_two_short_names_are_enough_only_in_the_channels_home_competitions():
    title, at = "العين 2 - 1 الظفرة | الجولة 9", "2026-11-19T17:23:01Z"
    got, trace = hl_of("yt_elsewhere", title, at)
    assert got == [] and any(t["result"] == "weak names" for t in trace)
    abroad = dict(AIN_DHA, comp=536)                                     # the same names in another country's league
    assert hl_of("yt_adsports", title, at, abroad)[0] == []


def test_a_result_title_is_a_summary_not_only_the_goals():
    # Abu Dhabi Sports' 189 s «العين 2 - 1 الظفرة | الجولة 9»: chances, saves and the three goals; the page's sheet says
    # «ملخص المباراة» for a summary and «أهداف المباراة» for the goals alone
    v = {"id": "6ZkC43OjQwg", "source": "youtube", "url": "https://www.youtube.com/watch?v=6ZkC43OjQwg", "ch": "yt_adsports",
         "title": "العين 2 - 1 الظفرة | الجولة 9 - دوري أدنوك للمحترفين 2026 - 2027", "at": "2026-11-19T17:23:01Z"}
    kind = lambda title: M.pack([(dict(v, title=title), 95)], {}, CH_YT_AE, hl=True)[0]["kind"]
    assert kind(v["title"]) == "summary"
    assert kind("أهداف مباراة العين 2 - 1 الظفرة") == "goals"


def test_thmanyahs_celebration_disallowed_goal_and_talk_show_posts_are_not_a_goals_clip():
    # the Thmanyah X pass of the month backfill (2026-11-20): Mané's goal got only «فرحة ساديو ماني بهدف التقدّم» (the celebration),
    # Mensah's the post that says the referee ruled it out for offside, Ronaldo's three a talk show segment about his hat-trick
    assert M.Text("فرحة ساديو ماني بهدف التقدّم 🟡🔥\n\n#النصر_الخلود | #دوري_روشن_السعودي").neg_goal
    assert M.Text("بصناعة من تريزيقيه، مينساه يسجل الهدف الثاني للرياض، لكن حكم اللقاء يُلغيه بداعي التسلل ⚽️🚩 #الرياض_التعاون").neg_goal
    assert M.Text("هاتريك رونالدو يقود النصر للانتصار وترقب لقمة الشباب والأهلي | المنصة مع تركي العجمة").neg
    # the studio's analyst on Al Ghannam's goal (Thmanyah 2026-10-24)
    assert M.Text("عن هدف خالد الغنام؟ 🤔 مُحلّل «ثمانية» أحمد عفيفي @Ahmed1Afify يشرح🎙️ #الخلود_الاتفاق | #استديو_ثمانية").neg
    # the clips of the same goals that stay
    assert not M.Text("هدف ⚽️ مينساه يعزّز تقدم الرياض بالهدف الثاني، بتسديدة تستقر في شباك التعاون 🔴 #الرياض_التعاون | #دوري_روشن_السعودي").neg_goal
    assert not M.Text("ثلاثية كريستيانو رونالدو ضد الخلود").neg
    assert not M.Text("📹| شاهد.. عمر كيتا يسجل بالخطأ في مرماه، ليمنح الشارقة هدف التقدم في شباك شباب الأهلي 🥅، لتتعالى فرحة اللاعبين").neg_goal
    assert not M.Text("العين 2 - 1 الظفرة | الجولة 9 - دوري أدنوك للمحترفين").neg


def test_a_rerun_takes_off_the_clips_a_newer_veto_turns_down(tmp_path, monkeypatch):
    # the backfill only ever added: the celebration and talk-show clips it filed before those words were vetoes (2026-11-20)
    # stayed on the pages and in media-extra.json, which the step merges back. A rerun now takes them off both; FotMob's own
    # link for a goal is not judged by its title
    from news import media_backfill as B
    store = _ksa_store(tmp_path)
    card = lambda vid, title, **k: dict({"id": vid, "url": f"https://www.youtube.com/watch?v={vid}", "title": title, "source": "youtube",
                                          "channel": "x", "published": "2026-09-29T19:00:00Z", "embed": True, "conf": 80,
                                          "found_by": "tifo"}, **k)
    good = card("good0000001", "هدف عبدالله الحمدان الثاني في شباك العراق")
    joy = card("joy00000001", "فرحة عبدالله الحمدان بالهدف الثاني")
    show = card("show0000001", "ثنائية الحمدان ترسم الطريق | المنصة مع تركي العجمة")
    fm = card("fotmob00001", "فرحة", found_by="fotmob")
    store.put_json(f"media/{KSA_IRQ['id']}.json", {"generated": "2026-09-29T21:05:00Z", "match": KSA_IRQ["id"],
                                                   "highlights": [dict(show, kind="summary")], "goals": {"69-102": [good, joy, fm]}})
    store.put_state(M.EXTRA, {"matches": {str(KSA_IRQ["id"]): {"kickoff_utc": KSA_IRQ["kickoff_utc"], "highlights": [show],
                                                                "goals": {"69-102": [good, joy], "55-101": [show]}}}})
    monkeypatch.setattr(B, "youtube_videos", lambda chs, ctx, t0, relist=False, log=print, store=None, remote=False: [])
    monkeypatch.setattr(B, "CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(M, "oembed", lambda vid: {"s": 200})
    monkeypatch.setattr(M, "load_names", lambda store, nat, cache_dir=None: M.Names(TEAMS, PLAYERS, {}, {}, ALIASES, NATIONS, {329}))
    monkeypatch.setattr(M, "national_comps", lambda: frozenset({329}))
    res = B.run(store, CFG_KSA, t=datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc), days=3, log=lambda *a: None)
    doc = store.get_json(f"media/{KSA_IRQ['id']}.json")
    assert doc["highlights"] == []
    assert [c["id"] for c in doc["goals"]["69-102"]] == ["good0000001", "fotmob00001"]
    assert res["taken_off"] == 2                                                   # off the page: the show and the celebration
    extra = store.get_state(M.EXTRA)["matches"][str(KSA_IRQ["id"])]
    assert extra["highlights"] == [] and {k: [c["id"] for c in l] for k, l in extra["goals"].items()} == {"69-102": ["good0000001"]}


# Al Wasl 2-1 Hatta, UAE Pro League, 2026-11-19: Abu Dhabi Sports and Dubai Sports both posted Serginho's 62' as «سيرجيو بيريرا»
# and Dubai Sports Hugo's own goal as «هوجو نيتو»; our names are «سيرجينيو» and «هوغو», so all three were turned down (the
# morning report of 11-20). Real titles, times and ids.
WAS_HAT = {"id": 1000022240, "comp": 538, "kickoff_utc": "2026-11-19T12:45:00Z", "status": "finished", "score": {"home": 2, "away": 1},
           "home": {"id": 102111, "name": "Al-Wasl", "name_ar": "الوصل"}, "away": {"id": 102113, "name": "Hatta", "name_ar": "حتا"},
           "periods": {"firstHalfStarted": "2026-11-19T12:45:35Z", "firstHalfEnded": "2026-11-19T13:32:45Z",
                       "secondHalfStarted": "2026-11-19T13:49:24Z", "gameEnded": "2026-11-19T14:41:15Z"},
           "events": [goal(16, "home", 619506, "Mehdi Taremi", (1, 0)), goal(62, "home", 1393478, "Serginho", (2, 0)),
                      goal(90, "away", 1182091, "Hugo", (2, 1), "own_goal", added=7)]}
# other players of the dictionary: the words names are made of, and a full name that is someone else's
WH_PLAYERS = {"619506": {"ar": "مهدي طارمي"}, "1393478": {"ar": "سيرجينيو"}, "1182091": {"ar": "هوغو"},
              "9001": {"ar": "سيرجيو راموس"}, "9002": {"ar": "بيبي بيريرا"}, "9003": {"ar": "هوجو ألميدا"}, "9004": {"ar": "بيدرو نيتو"},
              "1282441": {"ar": "ريناتو جونيور"}, "9005": {"ar": "جواو فيليكس"}, "9006": {"ar": "برناردو سيلفا"}}
WH_TEAMS = {"102111": {"name": "Al-Wasl", "name_ar": "الوصل"}, "102113": {"name": "Hatta", "name_ar": "حتا"}}
CH_WH = {c["key"]: c for c in M.x_channels([
    {"handle": "ADSportsTV", "name": "أبوظبي الرياضية", "lang": "ar", "tier": "official", "kind": "broadcaster", "comps": [538, 11027, 9943]},
    {"handle": "dubaisportstv", "name": "دبي الرياضية", "lang": "ar", "tier": "official", "kind": "broadcaster", "comps": [538, 11027, 9943]}])}
AD_62 = ("برأسية متقنة.. سيرجيو بيريرا يرتقي لعرضية رائعة ويضاعف النتيجة بهدف ثان للوصل ⚽️\n\n#الوصل_حتا \n"
         "#دوري_أدنوك_للمحترفين | #أبوظبي_الرياضية 1⃣", "2026-11-19T14:09:39Z")
DS_62 = ("سيرجيو بيريرا يحرز هدف الوصل الثاني في مرمى حتا \n\n#الوصل 2\n#حتا 0\n\n#دبي_الرياضية\n#دوري_أدنوك_للمحترفين",
         "2026-11-19T14:12:18Z")
DS_OG = ("هوجو نيتو يحرز هدف حتا الأول بالخطأ في مرمى فريقه الوصل \n\n#الوصل 2\n#حتا 1\n\n#دبي_الرياضية\n#دوري_أدنوك_للمحترفين",
         "2026-11-19T14:44:19Z")


def wh_names(learned=None):
    n = M.Names(WH_TEAMS, WH_PLAYERS, {}, {}, {}, NATIONS)
    if learned:
        n.add_aliases(learned)
    return n


def wh_post(handle, title_at, n=1):
    title, at = title_at
    return {"id": f"x{handle}{n}", "title": title, "desc": "", "at": at, "ch": "x_" + handle.lower(), "source": "x",
            "url": f"https://x.com/{handle}/status/{n}"}


def wh_goals(posts, names):
    out = M.attach(posts, [WAS_HAT], names, CH_WH, [])
    return {v["id"]: k for r in out.values() for k, l in r["goals"].items() for v, _ in l}


def test_dubai_sports_writes_the_score_after_the_goal_in_its_hashtags():
    assert M.Text(DS_62[0]).scores == [(2, 0)] and M.Text(DS_OG[0]).scores == [(2, 1)]
    assert M.Text(AD_62[0]).scores == []                          # «#أبوظبي_الرياضية 1⃣» alone is no score


def test_the_goal_number_with_the_team_between():
    assert M.Text(DS_62[0]).ordinal == 2                           # «هدف الوصل الثاني»
    assert M.Text(AD_62[0]).ordinal == 2                           # «بهدف ثان»
    assert M.Text(DS_OG[0]).ordinal == 1                           # «هدف حتا الأول»
    assert M.Text("هدف عالمي في الشوط الثاني").ordinal is None      # the half, not the goal
    assert M.Text("هدف التعادل في الدقيقة الأولى من الوقت بدل الضائع").ordinal is None
    # his second, his team's third (Thmanyah, Al-Bulaihi 2026-10-22): no number rather than the wrong one
    assert M.Text("هدف! ⚽️ البليهي مجددًا، لا يكتفي بهدف واحد ويسجل الثاني له والثالث لفريقه 🔥").ordinal is None


def test_two_broadcasters_teach_the_name_they_both_wrote():
    posts = [wh_post("ADSportsTV", AD_62), wh_post("dubaisportstv", DS_62)]
    assert wh_goals(posts, wh_names()) == {}                       # «سيرجيو بيريرا» is not a name we have for Serginho
    got = M.learn(posts, [WAS_HAT], wh_names(), CH_WH)
    assert {p: sorted(f) for p, f in got.items()} == {"1393478": ["سيرجيو بيريرا"]}
    assert sorted(got["1393478"]["سيرجيو بيريرا"]["chs"]) == ["x_adsportstv", "x_dubaisportstv"]
    learned = {p: list(f) for p, f in got.items()}
    assert wh_goals(posts, wh_names(learned)) == {"xADSportsTV1": "62-1393478", "xdubaisportstv1": "62-1393478"}


def test_one_post_teaches_a_name_only_when_it_writes_the_scorers_own_name_another_way():
    # one channel alone: «سيرجيو بيريرا» shares nothing with «سيرجينيو»
    assert M.learn([wh_post("ADSportsTV", AD_62)], [WAS_HAT], wh_names(), CH_WH) == {}
    # «هوجو» is our «هوغو», too short to name him alone; the score and the goal number in the post are his own goal's
    og = [wh_post("dubaisportstv", DS_OG)]
    assert wh_goals(og, wh_names()) == {}
    got = M.learn(og, [WAS_HAT], wh_names(), CH_WH)
    assert {p: sorted(f) for p, f in got.items()} == {"1182091": ["هوجو نيتو"]}
    assert wh_goals(og, wh_names({p: list(f) for p, f in got.items()})) == {"xdubaisportstv1": "90+7-1182091"}


def test_another_players_name_or_the_one_after_the_pass_is_never_learned():
    # both channels name the player who made the goal: a full name the dictionary holds for someone else, and an unknown one
    # after «بعرضية من»
    for title in ("ريناتو جونيور يصنع والوصل يضاعف النتيجة 2-0 أمام حتا", "بعرضية من جواو سيلفا.. الوصل يضاعف النتيجة 2-0 أمام حتا"):
        posts = [wh_post("ADSportsTV", (title, "2026-11-19T14:09:39Z")), wh_post("dubaisportstv", (title + " ⚽️", "2026-11-19T14:12:18Z"))]
        assert M.learn(posts, [WAS_HAT], wh_names(), CH_WH) == {}, title
    # a post that already names the scorer teaches nothing
    named = wh_post("dubaisportstv", ("مهدي طارمي يفتتح التسجيل للوصل 1-0 أمام حتا", "2026-11-19T13:02:00Z"))
    assert M.learn([named], [WAS_HAT], wh_names(), CH_WH) == {}


def test_load_names_reads_the_learned_names(tmp_path):
    from store import Store, LocalBackend
    store = Store(LocalBackend(str(tmp_path)))
    store.put_json("teams.json", {"teams": WH_TEAMS})
    store.put_state(M.LEARNED, {"1393478": {"سيرجيو بيريرا": {"n": 2, "chs": ["x_adsportstv", "x_dubaisportstv"]}}})
    names = M.load_names(store, frozenset(), cache_dir=str(tmp_path / "cache"))
    assert ("سيرجيو", "بيريرا") in names.player(1393478, "Serginho")


def test_step_learns_a_name_and_files_its_clips_in_the_same_run(tmp_path, monkeypatch):
    from store import Store, LocalBackend
    store = Store(LocalBackend(str(tmp_path)))
    day = {"matches": [{k: WAS_HAT[k] for k in ("id", "comp", "kickoff_utc", "status", "score", "home", "away")}]}
    store.put_json("day/20261119.json", day); store.put_json("day/20261120.json", {"matches": []})
    store.put_json(f"match/{WAS_HAT['id']}.json", WAS_HAT)
    store.put_json("teams.json", {"teams": WH_TEAMS})
    acc = [{"handle": "ADSportsTV", "name": "أبوظبي الرياضية", "lang": "ar", "tier": "official", "kind": "broadcaster", "comps": [538]},
           {"handle": "dubaisportstv", "name": "دبي الرياضية", "lang": "ar", "tier": "official", "kind": "broadcaster", "comps": [538]}]
    box = {"items": [{"id": str(i), "handle": h, "text": ta[0], "at": ta[1], "url": f"https://x.com/{h}/status/{i}", "video": True}
                     for i, (h, ta) in enumerate([("ADSportsTV", AD_62), ("dubaisportstv", DS_62), ("dubaisportstv", DS_OG)])]}
    monkeypatch.setattr(M, "fetch_feeds", lambda chs, prefetched=None, workers=6: ({}, {}))
    monkeypatch.setattr(M, "oembed", lambda vid: {"s": 200})
    monkeypatch.setattr(M, "load_names", lambda store, nat, cache_dir=None: wh_names(M.learned_aliases(store.get_state(M.LEARNED))))
    cfg = {"youtube": [], "media": {"youtube": []}, "x": {"accounts": acc}}
    t = datetime(2026, 11, 19, 15, 0, tzinfo=timezone.utc)
    M.step(store, cfg, t=t, xbox=box, push=None)
    doc = store.get_json(f"media/{WAS_HAT['id']}.json")
    assert {k: sorted(c["id"] for c in l) for k, l in doc["goals"].items()} == {"62-1393478": ["x0", "x1"], "90+7-1182091": ["x2"]}
    learned = store.get_state(M.LEARNED)
    assert sorted(learned) == ["1182091", "1393478"] and learned["1393478"]["سيرجيو بيريرا"]["n"] == 2
    assert M.step(store, cfg, t=t, xbox=box, push=None)["written"] == 0           # learnt once: nothing new the second time


# Shabab Al Ahli 3-2 Al Ain, President's Cup, 2026-10-22: Ezatolahi scored from the spot at 20' and again at 34', a penalty too
# though FotMob has it as a plain goal. Abu Dhabi Sports' post of the second, «بنفس سيناريو الهدف الأول.. … ويضاعف النتيجة …»,
# names the first goal to say it was the same again; with his name learnt it went on the 20' (dry run 2026-11-20)
SHA_AIN = {"id": 6428995, "comp": 9943, "kickoff_utc": "2026-10-22T16:00:00Z", "status": "finished", "score": {"home": 3, "away": 2},
           "home": {"id": 102119, "name": "Shabab Al-Ahli Dubai FC", "name_ar": "شباب الأهلي"}, "away": {"id": 102117, "name": "Al-Ain", "name_ar": "العين"},
           "periods": {"firstHalfStarted": "2026-10-22T16:01:05Z", "secondHalfStarted": "2026-10-22T17:12:22Z", "gameEnded": "2026-10-22T18:47:56Z"},
           "events": [goal(20, "home", 505281, "Saeid Ezatolahi", (1, 0), "penalty_goal"), goal(34, "home", 505281, "Saeid Ezatolahi", (2, 0))]}


def test_a_title_with_two_goal_numbers_places_no_goal():
    tx = M.Text("بنفس سيناريو الهدف الأول..  سعيد عزت يضع بصمته ويضاعف النتيجة لشباب الأهلي من علامة الجزاء⚽️")
    assert tx.ordinal is None and tx.ord_clash
    assert M.Text("برأسية متقنة.. سيرجيو بيريرا يرتقي لعرضية رائعة ويضاعف النتيجة بهدف ثان للوصل").ordinal == 2    # the same number twice
    names = M.Names({"102119": {"name": "Shabab Al-Ahli Dubai FC", "name_ar": "شباب الأهلي"}, "102117": {"name": "Al-Ain", "name_ar": "العين"}},
                    {"505281": {"ar": "سعيد عزت اللهي"}}, {}, {}, {}, NATIONS, player_aliases={"505281": ["سعيد عزت"]})
    post = lambda title, at, n: {"id": f"x{n}", "title": title, "desc": "", "at": at, "ch": "x_adsportstv", "source": "x", "url": "u"}
    out = M.attach([post("سعيد عزت يسجل هدف التقدم الأول لشباب الأهلي من علامة الجزاء ⚽️ #شباب_الأهلي_العين", "2026-10-22T16:22:12Z", 1),
                    post("بنفس سيناريو الهدف الأول..  سعيد عزت يضع بصمته ويضاعف النتيجة لشباب الأهلي من علامة الجزاء⚽️ #شباب_الأهلي_العين",
                         "2026-10-22T16:37:13Z", 2)], [SHA_AIN], names, CH_WH, [])
    assert {v["id"]: k for r in out.values() for k, l in r["goals"].items() for v, _ in l} == {"x1": "20-505281"}


def test_a_rerun_takes_off_a_clip_todays_matcher_no_longer_files_there(tmp_path, monkeypatch):
    # Dubai Sports' round-up «… #الوصل يتغلب على #حتا بثنائية طارمي وبيريرا» went on Taremi's goal while «بيريرا» named nobody;
    # with Serginho's learnt name it names two scorers and is no goal's clip (2026-11-20). A post this run holds is judged again
    # against its own match; one it does not hold, and FotMob's own link, are left as they are
    from news import media_backfill as B
    store = _ksa_store(tmp_path)
    vid = lambda i, title, at: {"id": i, "source": "youtube", "url": f"https://www.youtube.com/watch?v={i}", "vertical": False,
                                "title": title, "desc": "", "at": at, "ch": "yt_ksasports", "image": None}
    good = vid("good0000001", "الهدف الثاني لمنتخبنا الوطني سجله اللاعب عبدالله الحمدان- السعودية 2- العراق 0", "2026-09-29T19:11:10Z")
    both = vid("both0000001", "السعودية تتغلب على العراق بهدفي عبدالله السالم وعبدالله الحمدان", "2026-09-29T19:40:00Z")
    card = lambda v, **k: dict({"id": v["id"], "url": v["url"], "title": v["title"], "source": "youtube", "channel": "x",
                                "published": v["at"], "embed": True, "conf": 70, "found_by": "tifo"}, **k)
    gone = dict(card(both), id="notheld0001")
    fm = dict(card(both), id="fotmob00001", found_by="fotmob")
    store.put_json(f"media/{KSA_IRQ['id']}.json", {"generated": "2026-09-29T21:05:00Z", "match": KSA_IRQ["id"], "highlights": [],
                                                   "goals": {"69-102": [card(good), card(both), gone, fm]}})
    store.put_state(M.EXTRA, {"matches": {str(KSA_IRQ["id"]): {"kickoff_utc": KSA_IRQ["kickoff_utc"], "highlights": [],
                                                                "goals": {"69-102": [card(good), card(both)]}}}})
    monkeypatch.setattr(B, "youtube_videos", lambda chs, ctx, t0, relist=False, log=print, store=None, remote=False: [good, both])
    monkeypatch.setattr(B, "CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(M, "oembed", lambda vid: {"s": 200})
    monkeypatch.setattr(M, "load_names", lambda store, nat, cache_dir=None: M.Names(TEAMS, PLAYERS, {}, {}, ALIASES, NATIONS, {329}))
    monkeypatch.setattr(M, "national_comps", lambda: frozenset({329}))
    res = B.run(store, CFG_KSA, t=datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc), days=3, log=lambda *a: None)
    doc = store.get_json(f"media/{KSA_IRQ['id']}.json")
    assert sorted(c["id"] for c in doc["goals"]["69-102"]) == ["fotmob00001", "good0000001", "notheld0001"]
    assert res["taken_off"] == 1
    extra = store.get_state(M.EXTRA)["matches"][str(KSA_IRQ["id"])]
    assert [c["id"] for c in extra["goals"]["69-102"]] == ["good0000001"]
    off = json.load(open(tmp_path / "cache" / "taken_off.json", encoding="utf-8"))
    assert [(x["goal"], x["id"]) for x in off] == [("69-102", "both0000001")] and off[0]["why"]


# Al Nasr 2-2 Al Shabab, Kuwait Premier League, 2026-11-02, as Kuwait's sports channel posted its goals on X (2026-11-20, the
# Arab leagues with no clip): Kuku has no Arabic name of ours, «للشباب» read as a youth word, and a graph «name» of Al Tararwa,
# «منتخب الكويت تحت 21 سنة لكرة القدم», named him in every post that says «لكرة القدم». Real titles, times and ids.
NAS_SHA = {"id": 6018582, "comp": 529, "kickoff_utc": "2026-11-02T15:45:00Z", "status": "finished", "score": {"home": 2, "away": 2},
           "home": {"id": 101710, "name": "Al Nasr", "name_ar": "النصر"}, "away": {"id": 150412, "name": "Al-Shabab SC", "name_ar": "الشباب"},
           "periods": {"firstHalfStarted": "2026-11-02T15:46:51Z", "secondHalfStarted": "2026-11-02T16:51:03Z", "gameEnded": "2026-11-02T17:40:10Z"},
           "events": [goal(34, "home", 2435620, "Abdelrahman Kuku", (1, 0)), goal(60, "away", 915137, "Yaqoub Al Tararwa", (1, 1)),
                      goal(74, "home", 725164, "Hazem Haj Hassen", (2, 1)), goal(90, "away", 1602390, "Geovane", (2, 2), added=3)]}
KW_TAIL = " ضمن منافسات بطولة دوري زين الممتاز لكرة القدم للموسم الرياضي 2026-2027 #الكويت #الرياضية #وزارة_الإعلام_الكويت"
CH_KW = {c["key"]: c for c in M.x_channels([{"handle": "kuwaitsporttv", "name": "القناة الرياضية الكويتية", "lang": "ar", "tier": "official",
                                              "country": "kw", "kind": "broadcaster", "comps": [529]}])}


def kw_names(learned=None):
    n = M.Names({"101710": {"name": "Al Nasr", "name_ar": "النصر"}, "150412": {"name": "Al-Shabab SC", "name_ar": "الشباب"}},
                {"915137": {"ar": "يعقوب الطراروة"}, "725164": {"ar": "حازم الحاج حسن"}, "1602390": {"ar": "جيوفاني"}}, {}, {}, {}, NATIONS,
                player_aliases={"915137": ["منتخب الكويت تحت 21 سنة لكرة القدم", "يعقوب الطراروة"]})
    if learned:
        n.add_aliases(learned)
    return n


def kw_post(title, at, n):
    return {"id": f"x{n}", "title": title + KW_TAIL, "desc": "", "at": at, "ch": "x_kuwaitsporttv", "source": "x", "url": "u"}


def kw_goals(posts, names):
    out = M.attach(posts, [NAS_SHA], names, CH_KW, [])
    return {v["id"]: k for r in out.values() for k, l in r["goals"].items() for v, _ in l}


def test_a_name_that_is_not_a_persons_is_no_form_of_him():
    assert ("القدم",) not in kw_names().player(915137, "Yaqoub Al Tararwa")
    assert kw_goals([kw_post("حازم الحاج حسن يسجل الهدف الثاني للنصر", "2026-11-02T17:27:00Z", 3)], kw_names()) == {"x3": "74-725164"}


def test_the_club_al_shabab_is_not_a_youth_word():
    assert kw_goals([kw_post("يعقوب الطراروة يسجل الهدف الأول للشباب", "2026-11-02T17:14:00Z", 2)], kw_names()) == {"x2": "60-915137"}
    assert M.Text("هدف منتخب الشباب في كأس الخليج للشباب").youth                  # still a youth word without that club


def test_letters_match_the_latin_name():
    assert M.skeleton_ar("عبدالرحمن كوكو") == M.skeleton_lat("Abdelrahman Kuku")
    assert M.skeleton_ar("هوجو") == M.skeleton_ar("هوغو") == M.skeleton_lat("Hugo")
    assert M.skeleton_ar("مايكل كابريرا") == M.skeleton_lat("Michael Cabrera")
    assert M.skeleton_ar("الطراروة") == M.skeleton_lat("Al Tararwa") == M.skeleton_lat("Tararwa")
    assert M.skeleton_ar("كارلوس") != M.skeleton_lat("Breno Calixto")


def test_a_scorer_with_no_arabic_name_learns_the_one_the_post_writes_in_its_letters():
    post = [kw_post("عبدالرحمن كوكو يسجل الهدف الأول للنصر", "2026-11-02T16:32:00Z", 1)]
    assert kw_goals(post, kw_names()) == {}
    got = M.learn(post, [NAS_SHA], kw_names(), CH_KW)
    assert {p: sorted(f) for p, f in got.items()} == {"2435620": ["عبدالرحمن كوكو"]}
    assert kw_goals(post, kw_names({p: list(f) for p, f in got.items()})) == {"x1": "34-2435620"}
    # the same post with another name in it teaches nothing: its letters are not Kuku's
    assert M.learn([kw_post("كارلوس سيلفا يسجل الهدف الأول للنصر", "2026-11-02T16:32:00Z", 9)], [NAS_SHA], kw_names(), CH_KW) == {}
