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
