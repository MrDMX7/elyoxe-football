"""news/streams.py: which official live stream goes with which match («شوفها مباشر ببلاش»). The first titles are the Gulf Cup
final's real streams of 2026-10-06; the others are the traps a live tab holds besides the match. Then the official accounts'
broadcasts on X (2026-10-07), and news/xreader.js reading their cards."""
import json, os, shutil, subprocess
from datetime import datetime, timedelta, timezone
import pytest
from news import media as M
from news import streams as SR
from test_media import TEAMS, PLAYERS, ALIASES, NATIONS, N, team

T = datetime(2026, 10, 6, 19, 40, tzinfo=timezone.utc)
FINAL = {"id": 6052096, "comp": 329, "kickoff_utc": "2026-10-06T18:00:00Z", "status": "live", "score": {"home": 2, "away": 0},
         "home": team(7795), "away": team(5789)}
OTHER = {"id": 6368653, "comp": 114, "kickoff_utc": "2026-10-06T18:00:00Z", "status": "live", "score": {"home": 1, "away": 0},
         "home": {"id": 5816, "name": "Jordan", "name_ar": "الأردن"}, "away": {"id": 7, "name": "Venezuela", "name_ar": "فنزويلا"}}
CH = {"adsports": {"key": "yt_adsports", "name": "أبوظبي الرياضية", "lang": "ar", "team": None, "comps": None},
      "ksa": {"key": "yt_ksasports", "name": "القنوات الرياضية السعودية", "lang": "ar", "team": None, "comps": None},
      "saudint": {"key": "yt_saudint", "name": "المنتخب السعودي", "lang": "ar", "team": 7795, "comps": None}}


def which(title, ch="adsports", matches=(FINAL, OTHER)):
    return SR.match_of(title, CH[ch], M.Ctx(list(matches), N))


def test_the_finals_real_streams_are_the_final():
    assert which("مباشر| نهائي خليجي 27 – الإمارات والسعودية - عامر عبدالله")[0] == 6052096
    assert which("مباشر |  القناة الرياضية السعودية الأولى | نهائي كأس الخليج ( السعودية 🆚 الامارات )", "ksa")[0] == 6052096
    assert which("بث مباشر | السعودية × الإمارات | نهائي كأس الخليج 27", "ksa")[0] == 6052096


def test_a_channels_own_stream_that_names_no_match_is_left_out():
    assert which("‫ 🔴 بث مباشر | beIN SPORTS") == (None, "no match named")
    assert which("beIN SPORTS الإخبارية")[0] is None


def test_studios_press_conferences_and_replays_are_not_the_match():
    for title in ("الاستوديو التحليلي | نهائي كأس الخليج السعودية والإمارات", "مباشر | المؤتمر الصحفي لمدرب الإمارات قبل مواجهة السعودية",
                  "تحليل مباراة السعودية والإمارات بعد التتويج", "إعادة | نهائي كأس الخليج السعودية والإمارات",
                  "ملخص مباراة السعودية والإمارات | نهائي كأس الخليج"):
        mid, why = which(title)
        assert mid is None and why.startswith("not the match"), title


def test_a_federation_channel_names_only_the_opponent_but_never_its_press_conference():
    assert which("مباشر | منتخبنا أمام الإمارات في نهائي كأس الخليج", "saudint")[0] == 6052096
    assert which("مباشر | المؤتمر الصحفي للمنتخب الوطني قبل مواجهة الإمارات", "saudint")[0] is None


def test_women_and_youth_matches_between_the_same_countries_are_not_the_mens():
    assert which("مباشر | السعودية والإمارات | كأس الخليج للسيدات")[0] is None
    assert which("مباشر | السعودية × الإمارات | كأس الخليج للناشئين تحت 17")[0] is None


def test_window_live_soon_and_just_finished_but_not_far_or_called_off(tmp_path):
    from store import Store, LocalBackend
    store = Store(LocalBackend(str(tmp_path)))
    ko = lambda mins: (T + timedelta(minutes=mins)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ms = [dict(FINAL), dict(OTHER, id=1, status="scheduled", kickoff_utc=ko(60)), dict(OTHER, id=2, status="scheduled", kickoff_utc=ko(180)),
          dict(OTHER, id=3, status="finished", kickoff_utc=ko(-120)), dict(OTHER, id=4, status="finished", kickoff_utc=ko(-300)),
          dict(OTHER, id=5, status="postponed", kickoff_utc=ko(30))]
    store.put_json("day/20261006.json", {"matches": ms}); store.put_json("day/20261005.json", {"matches": []})
    assert sorted(m["id"] for m in SR.window(store, T)) == [1, 3, 6052096]


def test_step_publishes_the_streams_that_play_first_and_drops_gone_ones(tmp_path, monkeypatch):
    from store import Store, LocalBackend
    store = Store(LocalBackend(str(tmp_path)))
    store.put_json("day/20261006.json", {"matches": [FINAL]}); store.put_json("day/20261005.json", {"matches": []})
    lives = {"UCF8Fpc7bPHC8Jrflci-mUiQ": [("9StetIBgFZI", "مباشر| نهائي خليجي 27 – الإمارات والسعودية - عامر عبدالله", "94K")],
             "UCLo2xigvxv9ksxp78AyCBTw": [("TK1XWtPXj6w", "مباشر |  القناة الرياضية السعودية الأولى | نهائي كأس الخليج ( السعودية 🆚 الامارات )", "112K"),
                                          ("lxpmm36-1Ww", "مباشر | القناة الرياضية السعودية الثانية |  نهائي كأس الخليج ( السعودية 🆚 الامارات )", "10K"),
                                          ("goneGONE123", "مباشر | السعودية والإمارات | نهائي كأس الخليج", "1K")]}
    oe = {"9StetIBgFZI": 200, "TK1XWtPXj6w": 401, "lxpmm36-1Ww": 200, "goneGONE123": 404}
    monkeypatch.setattr(SR, "live_now", lambda cid: lives.get(cid, []))
    monkeypatch.setattr(M, "oembed", lambda vid: {"s": oe[vid]})
    monkeypatch.setattr(M, "load_names", lambda store, nat, cache_dir=None: M.Names(TEAMS, PLAYERS, {}, {}, ALIASES, NATIONS, {329}))
    cfg = {"youtube": [], "media": {"youtube": [
        {"key": "yt_adsports", "channel": "UCF8Fpc7bPHC8Jrflci-mUiQ", "name": "أبوظبي الرياضية", "lang": "ar", "kind": "broadcaster", "country": "ae"},
        {"key": "yt_ksasports", "channel": "UCLo2xigvxv9ksxp78AyCBTw", "name": "القنوات الرياضية السعودية", "lang": "ar", "kind": "broadcaster", "country": "sa"}]}}
    res = SR.step(store, cfg, t=T)
    assert res["streams"] == 3 and res["written"] is True
    got = store.get_json("streams.json")["matches"]["6052096"]
    # the two that play on the page first, the more watched of them first; the one that opens on YouTube last; the gone one out
    assert [(s["id"], s["embed"], s["cc"]) for s in got] == [("9StetIBgFZI", True, "ae"), ("lxpmm36-1Ww", True, "sa"), ("TK1XWtPXj6w", False, "sa")]
    assert SR.step(store, cfg, t=T + timedelta(minutes=4))["written"] is False          # nothing new: not uploaded again
    assert SR.step(store, cfg, t=T + timedelta(minutes=11))["written"] is True          # ... but kept fresh while a stream is on
    lives.clear()
    assert SR.step(store, cfg, t=T + timedelta(minutes=15))["written"] is True          # the streams ended: the match goes
    assert store.get_json("streams.json")["matches"] == {}


AD_X = {"handle": "ADSportsTV", "name": "أبوظبي الرياضية", "lang": "ar", "tier": "official", "kind": "broadcaster", "country": "ae", "comps": [538, 329]}
KSA_X = {"handle": "riyadiyatv", "name": "القنوات الرياضية السعودية", "lang": "ar", "tier": "official", "kind": "broadcaster", "country": "sa", "comps": [329]}
PRESS_X = {"handle": "kooora", "name": "كووورة", "lang": "ar", "tier": "paper"}


def bc_post(i, handle, text, at, state="RUNNING", seen=T - timedelta(minutes=10)):
    return {"id": str(i), "handle": handle, "text": text, "at": at, "url": f"https://x.com/{handle}/status/{i}",
            "bc": {"id": f"1kJzDPLnoNy{i:02d}", "state": state, "title": "خليجي 27", "seen": seen.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                   "thumb": "https://pbs.twimg.com/card_img/2107624129155469312/YvBkC3TF?format=jpg&name=800x419"}}


def test_x_broadcasts_count_while_the_match_is_on_and_their_post_names_it(tmp_path, monkeypatch):
    from store import Store, LocalBackend
    store = Store(LocalBackend(str(tmp_path)))
    store.put_json("day/20261006.json", {"matches": [FINAL]}); store.put_json("day/20261005.json", {"matches": []})
    items = [bc_post(1, "ADSportsTV", "مباشر | السعودية × الإمارات | نهائي خليجي 27", "2026-10-06T17:30:00.000Z"),
             bc_post(2, "ADSportsTV", "مباشر | برنامج الفريق التاسع | خليجي 27", "2026-10-06T19:30:00.000Z"),       # its feed in a studio (real, 21:08)
             bc_post(3, "ADSportsTV", "مباشر | السعودية × الإمارات | خليجي 27", "2026-10-03T17:30:00.000Z"),           # the group stage, days ago
             bc_post(4, "riyadiyatv", "مباشر | نهائي كأس الخليج السعودية والإمارات", "2026-10-06T17:40:00.000Z", state="ENDED"),
             bc_post(5, "kooora", "مباشر | السعودية × الإمارات", "2026-10-06T17:40:00.000Z"),                         # press, not official
             bc_post(6, "riyadiyatv", "مباشر | السعودية والإمارات | نهائي كأس الخليج", "2026-10-06T17:45:00.000Z", seen=T - timedelta(hours=2))]
    store.put_state("news/x-inbox.json", {"last_run": (T - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.000Z"), "items": items})
    monkeypatch.setattr(SR, "live_now", lambda cid: [])
    monkeypatch.setattr(M, "load_names", lambda store, nat, cache_dir=None: M.Names(TEAMS, PLAYERS, {}, {}, ALIASES, NATIONS, {329}))
    cfg = {"youtube": [], "media": {"youtube": []}, "x": {"accounts": [AD_X, KSA_X, PRESS_X]}}
    SR.step(store, cfg, t=T)
    got = store.get_json("streams.json")["matches"]["6052096"]
    assert [(s["id"], s["platform"], s["embed"], s["cc"]) for s in got] == [("x1kJzDPLnoNy01", "x", False, "ae")]
    assert got[0]["url"] == "https://x.com/i/broadcasts/1kJzDPLnoNy01" and got[0]["thumb"].startswith("https://pbs.twimg.com/")
    # after the whistle the same feed is a studio: the broadcast goes, while a YouTube stream of the match may stay
    store.put_json("day/20261006.json", {"matches": [dict(FINAL, status="finished")]})
    SR.step(store, cfg, t=T + timedelta(minutes=12))
    assert store.get_json("streams.json")["matches"] == {}


def test_a_quiet_x_reader_is_not_believed(tmp_path, monkeypatch):
    from store import Store, LocalBackend
    store = Store(LocalBackend(str(tmp_path)))
    store.put_json("day/20261006.json", {"matches": [FINAL]}); store.put_json("day/20261005.json", {"matches": []})
    store.put_state("news/x-inbox.json", {"last_run": (T - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                                          "items": [bc_post(1, "ADSportsTV", "مباشر | السعودية × الإمارات | نهائي خليجي 27", "2026-10-06T17:30:00.000Z")]})
    monkeypatch.setattr(SR, "live_now", lambda cid: [])
    monkeypatch.setattr(M, "load_names", lambda store, nat, cache_dir=None: M.Names(TEAMS, PLAYERS, {}, {}, ALIASES, NATIONS, {329}))
    res = SR.step(store, {"youtube": [], "media": {"youtube": []}, "x": {"accounts": [AD_X]}}, t=T)
    assert res["streams"] == 0


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed here")
def test_xreader_reads_wrapped_posts_and_their_broadcast_card(tmp_path):
    # X wraps some posts in TweetWithVisibilityResults (12 of AD Sports' 20 on 2026-10-07): they were missed before
    user = {"core": {"screen_name": "ADSportsTV", "name": "ADSportsTV"}}
    card = {"legacy": {"name": "745291183405076480:broadcast", "binding_values": [
        {"key": "broadcast_id", "value": {"string_value": "1kJzDPLnoNyKv"}}, {"key": "broadcast_state", "value": {"string_value": "RUNNING"}},
        {"key": "broadcast_title", "value": {"string_value": "خليجي 27"}},
        {"key": "broadcast_thumbnail_large", "value": {"image_value": {"url": "https://pbs.twimg.com/card_img/1/a?format=jpg&name=800x419"}}}]}}
    wrapped = {"__typename": "TweetWithVisibilityResults", "tweet": {"rest_id": "2107578742025662594", "core": {"user_results": {"result": user}}, "card": card,
               "legacy": {"id_str": "2107578742025662594", "created_at": "Tue Oct 06 21:08:23 +0000 2026", "full_text": "مباشر | السعودية × الإمارات https://t.co/x"}}}
    plain = {"__typename": "Tweet", "rest_id": "2", "core": {"user_results": {"result": user}},
             "legacy": {"id_str": "2", "created_at": "Tue Oct 06 20:00:00 +0000 2026", "full_text": "هدف! https://t.co/y",
                        "extended_entities": {"media": [{"type": "video", "media_url_https": "https://pbs.twimg.com/v.jpg"}]}}}
    f = tmp_path / "tl.json"
    f.write_text(json.dumps({"data": {"entries": [{"content": {"itemContent": {"tweet_results": {"result": wrapped}}}},
                                                   {"content": {"itemContent": {"tweet_results": {"result": plain}}}}]}}), encoding="utf-8")
    js = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "news", "xreader.js").replace("\\", "/")
    out = subprocess.run(["node", "-e", f"const X=require({json.dumps(js)});const fs=require('fs');"
                          f"process.stdout.write(JSON.stringify(X.posts(JSON.parse(fs.readFileSync({json.dumps(str(f))},'utf8')),'ADSportsTV')))"],
                         capture_output=True, text=True, encoding="utf-8", timeout=60)
    ps = json.loads(out.stdout)
    assert [p["id"] for p in ps] == ["2107578742025662594", "2"]
    assert ps[0]["bc"]["id"] == "1kJzDPLnoNyKv" and ps[0]["bc"]["state"] == "RUNNING" and ps[0]["bc"]["thumb"].startswith("https://pbs.twimg.com/")
    assert ps[0]["text"] == "مباشر | السعودية × الإمارات" and "bc" not in ps[1] and ps[1]["video"] is True
