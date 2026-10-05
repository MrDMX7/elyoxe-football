"""news/tvindex.py: one index of who called which match across days (v1/tv/commentators.json, item 3)."""
from datetime import date, datetime, timezone

from news import tvindex as X

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def day(matches, fixtures):
    return {"generated": "x", "date": "x", "sources": [], "matches": matches, "fixtures": fixtures, "unmatched": [], "dropped": [], "disputed": []}


def ours(mid, h, a, comp, ko, src="day"):
    return {"id": mid, "ko": datetime.fromisoformat(ko.replace("Z", "+00:00")), "home": {"id": h, "names": ["x"]},
            "away": {"id": a, "names": ["y"]}, "comp": comp, "comp_name_ar": "دوري", "status": "scheduled", "src": src}


D1 = day({"101": [{"channel": "beIN SPORTS 1", "commentator": "حفيظ الدراجي"}],           # a variant spelling of a famous voice
          "102": [{"channel": "شاهد", "commentator": "فارس عوض"}, {"channel": "MBC Action", "commentator": "فارس عوض"}],
          "103": [{"channel": "الكأس 1", "commentator": "سالم الهاشمي"}, {"channel": "SSC 1", "commentator": None, "from": "schedules"}]},
         {"101": {"home": "فرنسا", "away": "بلجيكا", "ko": "2026-10-01T18:45:00Z", "comp": "دوري الأمم الأوروبية"},
          "102": {"home": "الهلال", "away": "النصر", "ko": "2026-10-01T17:00:00Z", "comp": "دوري روشن"},
          "103": {"home": "السد", "away": "الغرافة", "ko": "2026-10-01T16:00:00Z", "comp": "دوري نجوم قطر"}})
D3 = day({"301": [{"channel": "beIN SPORTS 2", "commentators": ["حفيظ دراجي", "عصام الشوالي"]}],
          "302": [{"channel": "أبوظبي الرياضية 1", "commentator": "فارس عوض"}]},
         {"301": {"home": "إنتر", "away": "ميلان", "ko": "2026-10-03T18:45:00Z", "comp": "الدوري الإيطالي"},
          "302": {"home": "العين", "away": "الوحدة", "ko": "2026-10-03T10:30:00Z", "comp": "دوري أدنوك"}})
FX = {date(2026, 10, 1): [ours(101, 1, 2, 9806, "2026-10-01T18:45:00Z", "all"), ours(102, 3, 4, 536, "2026-10-01T17:00:00Z")],
      date(2026, 10, 3): [ours(301, 5, 6, 55, "2026-10-03T18:45:00Z"), ours(302, 7, 8, 538, "2026-10-03T10:30:00Z")]}


def test_one_spelling_per_voice_one_entry_per_match_and_facts_only():
    c = X.compact(D1, FX[date(2026, 10, 1)])
    assert c["101"]["calls"] == [["حفيظ دراجي", "beIN SPORTS 1"]]                   # FAMOUS / VARIANTS spelling
    assert c["102"]["calls"] == [["فارس عوض", "شاهد"], ["فارس عوض", "MBC Action"]]
    assert c["101"]["page"] is False and c["102"]["page"] is True                    # all/ only: no page of its own
    assert c["102"]["h"] == [3, "الهلال"] and c["102"]["c"] == [536, "دوري روشن"]
    assert c["103"]["calls"] == [["سالم الهاشمي", "الكأس 1"]] and c["103"]["h"] == [None, "السد"]   # no fixture of ours: no ids
    assert X.key_of("حفيظ الدراجي") == X.key_of("حفيظ دراجي") and X.slug_of("فارس عوض") == "فارس-عوض"


def test_build_next_recent_counts_and_only_famous_voices_get_an_entry():
    days = {"2026-10-01": X.compact(D1, FX[date(2026, 10, 1)]), "2026-10-03": X.compact(D3, FX[date(2026, 10, 3)])}
    pub = X.build(days, NOW)
    fares = pub["commentators"][X.key_of("فارس عوض")]
    # 302 kicked off 90 minutes ago: still «today's» (live), not history yet
    assert fares["n"] == 2 and fares["next"] == [[302, "أبوظبي الرياضية 1"]] and fares["recent"] == [[102, "شاهد، MBC Action"]]
    assert sorted(c for c, n in fares["channels"]) == sorted(["MBC Action", "شاهد", "أبوظبي الرياضية 1"])
    assert sorted(fares["comps"]) == [[536, "دوري روشن", 1], [538, "دوري أدنوك", 1]]
    hafid = pub["commentators"][X.key_of("حفيظ دراجي")]
    assert hafid["next"] == [[301, "beIN SPORTS 2"]] and hafid["recent"] == [[101, "beIN SPORTS 1"]]   # 18:45 today is still to come
    assert hafid["first"] == "2026-10-01" and hafid["last"] == "2026-10-03" and hafid["slug"] == "حفيظ-دراجي"
    assert pub["others"] == [["سالم الهاشمي", 1]] and X.key_of("سالم الهاشمي") not in pub["commentators"]
    assert set(pub["matches"]) == {"101", "102", "301", "302"} and pub["matches"]["301"]["c"] == [55, "الدوري الإيطالي"]
    assert pub["since"] == "2026-10-01" and pub["days"] == 2 and "كووورة" in pub["source"]
    assert list(pub["commentators"]) == [X.key_of(n) for n in ("عصام الشوالي", "حفيظ دراجي", "فارس عوض")]   # FAMOUS order


def test_update_backfills_once_keeps_state_and_writes_only_on_change(tmp_path):
    from store import Store, LocalBackend
    store = Store(LocalBackend(tmp_path))
    store.put_json("tv/20261001.json", D1)
    reads = []
    real = store.get_json
    store.get_json = lambda p, public=True: reads.append(p) or real(p, public)
    fx = lambda d: FX.get(d, [])                                                     # noqa: E731
    pub = X.update(store, {date(2026, 10, 3): D3, date(2026, 10, 4): day({}, {})}, fx, NOW, log=lambda s: None)
    assert [r for r in reads if r.startswith("tv/")] == ["tv/20260930.json", "tv/20261001.json", "tv/20261002.json"]
    assert X.key_of("فارس عوض") in pub["commentators"] and store.get_json("tv/commentators.json")["days"] == 5
    reads.clear()
    store.written.clear()
    X.update(store, {date(2026, 10, 3): D3, date(2026, 10, 4): day({}, {})}, fx, NOW, log=lambda s: None)
    assert [r for r in reads if r.startswith("tv/")] == []                           # the old days come from the state now
    assert "tv/commentators.json" not in store.written                              # same content: not uploaded again
