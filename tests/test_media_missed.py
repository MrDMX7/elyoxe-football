"""news/media_missed.py: the goals that ended without a clip of their own, the official posts that looked like each, and why
the matcher turned each down (owner 2026-11-19: Al Ain's 43' and 54' were missed and only he noticed)."""
from datetime import datetime, timezone
from news import media as M
from news import media_missed as MM
from test_media import AIN_DHA, N_AE, CH_AE

T = datetime(2026, 11, 19, 18, 30, tzinfo=timezone.utc)
CARD_66 = {"id": "x2123460043517415732", "url": "https://x.com/ADSportsTV/status/2123460043517415732", "source": "x"}


def vid(i, ch, title, at, image=None):
    return {"id": "x" + i, "source": "x", "url": f"https://x.com/{ch}/status/{i}", "title": title, "desc": "", "at": at,
            "ch": "x_" + ch.lower(), "image": image, "made": M.video_made(image)}


def run(vids, docs=None):
    trace = []
    M.attach(vids, [AIN_DHA], N_AE, CH_AE, trace)
    docs = {AIN_DHA["id"]: {"highlights": [], "goals": {"66-794049": [CARD_66]}}} if docs is None else docs
    return MM.build([AIN_DHA], docs, vids, N_AE, CH_AE, trace, T)


def test_each_missed_goal_lists_the_posts_that_looked_like_it_and_why():
    vids = [
        # (a name we don't know and nothing else to say which goal: «يفتتح التسجيل» would place it, 2026-11-20)
        vid("1", "ADSportsTV", "ماركينيو يسجل ويضع العين في المقدمة ⚽️ #العين_الظفرة", "2026-11-19T16:12:36Z"),
        vid("2", "alainfcae", "د54: حسين رحيمي يسجل ثاني أهداف الزعيم 🔥 #العين_الظفرة", "2026-11-19T16:40:27Z",
            "https://pbs.twimg.com/amplify_video_thumb/2091176345514479616/img/a.jpg"),
        vid("3", "ADSportsTV", "عبدالله الكربي يطلق تسديدة قوية لا تُرد معلناً تقليص الفارق بالهدف الأول للظفرة ⚽️ #العين_الظفرة",
            "2026-11-19T16:55:01Z"),
        vid("4", "ADSportsTV", "روستاند لاعب الظفرة يتلقى البطاقة الحمراء 🟥 #العين_الظفرة", "2026-11-19T17:04:00Z"),
    ]
    vids[2]["id"] = CARD_66["id"]
    day = run(vids)["2026-11-19"]
    e = day[str(AIN_DHA["id"])]
    assert (e["goals"], e["with_clip"], e["home"], e["away"], e["score"]) == (3, 1, "العين", "الظفرة", "2-1")
    by = {m["key"]: m for m in e["missed"]}
    assert sorted(by) == ["43-1572471", "54-1295519"]
    c43 = by["43-1572471"]["cands"]
    assert [c["url"] for c in c43] == ["https://x.com/ADSportsTV/status/1"] and c43[0]["why"] == "unrecognised"
    assert by["43-1572471"]["scorer"] == "ماركوس أندريه" and by["43-1572471"]["minute"] == "43"
    c54 = by["54-1295519"]["cands"]
    assert [c["url"] for c in c54] == ["https://x.com/alainfcae/status/2"]
    assert c54[0]["why"].startswith("video made before the goal") and c54[0]["why_ar"]
    # the clip already in use and a card post are nobody's candidates
    assert all("ADSportsTV/status/4" not in c["url"] for m in e["missed"] for c in m["cands"])


def test_a_goal_no_official_account_posted_counts_without_candidates():
    e = run([])["2026-11-19"][str(AIN_DHA["id"])]
    assert [(m["key"], m["cands"]) for m in e["missed"]] == [("43-1572471", []), ("54-1295519", [])]


def test_only_finished_matches_and_kept_days():
    live = dict(AIN_DHA, status="live")
    assert MM.build([live], {}, [], N_AE, CH_AE, [], T) == {}
    old = {"2026-11-01": {"1": {}}, "2026-11-18": {"2": {}}}
    assert sorted(MM.merge(old, {"2026-11-19": {"3": {}}}, T)) == ["2026-11-18", "2026-11-19"]
