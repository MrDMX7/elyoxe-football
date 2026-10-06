"""news/streams.py: which official live stream goes with which match («شوفها مباشر ببلاش»). The first titles are the Gulf Cup
final's real streams of 2026-10-06; the others are the traps a live tab holds besides the match."""
from datetime import datetime, timedelta, timezone
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
