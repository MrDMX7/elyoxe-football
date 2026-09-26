"""Keep-last-good: an empty or failed fetch never replaces a good snapshot; health.json says so."""
import gzip, json

import pytest

import poller as P
from sources import schema as S
from sources.http import FetchError
from store import Store, LocalBackend


def read(tmp, path):
    return json.loads(gzip.decompress((tmp / "v1" / path).read_bytes()))


GOOD = {"groups": [{"name": None, "rows": [
    {"rank": 1, "team": {"id": 1, "name": "A"}, "pts": 3}, {"rank": 2, "team": {"id": 2, "name": "B"}, "pts": 0}]}]}


def test_invalid_payload_keeps_previous(tmp_path):
    st = Store(LocalBackend(tmp_path))
    assert st.put_json("comp/1/standings.json", GOOD, validate=S.validate_standings)
    assert not st.put_json("comp/1/standings.json", {"groups": []}, validate=S.validate_standings)
    assert not st.put_json("comp/1/standings.json", {"groups": [{"rows": []}]}, validate=S.validate_standings)
    assert read(tmp_path, "comp/1/standings.json") == GOOD
    assert st.health["comp/1/standings.json"]["ok"] is False
    assert "kept last good" in st.health["comp/1/standings.json"]["error"]


def test_unchanged_content_not_reuploaded(tmp_path):
    st = Store(LocalBackend(tmp_path))
    st.put_json("a.json", {"x": 1})
    st.put_json("a.json", {"x": 1})
    assert st.written == ["a.json"] and st.skipped_same == 1
    meta = json.loads((tmp_path / "v1" / "a.json.meta").read_text())
    assert meta["ContentEncoding"] == "gzip" and "max-age=300" in meta["CacheControl"]


class FailingFotMob:
    name = "fotmob"
    names = {}

    def league_raw(self, *a, **k):
        raise FetchError("https://www.fotmob.com/api/data/leagues?id=538", "HTTP 503", 503)


def _poller(tmp_path):
    p = P.Poller(Store(LocalBackend(tmp_path)), budget=30)
    p.load()
    p.mode = "test"
    return p


def test_failed_source_does_not_overwrite_and_is_reported(tmp_path, fx):
    p = _poller(tmp_path)
    comp = {"id": 538, "key": "x", "name_ar": "د", "name_en": "PL", "kind": "league", "scope": "uae",
            "matches_per_team": 26}                                  # no uaepl id: no fallback
    raw = fx("fotmob_league_538.json")
    p.fm.league_raw = lambda *a, **k: raw
    p.fm.http.get_json = lambda *a, **k: (_ for _ in ()).throw(FetchError("x", "no network in tests"))
    p.refresh_comp(comp)
    good = read(tmp_path, "comp/538/standings.json")
    assert len(good["groups"][0]["rows"]) == 14 and good["magic"]["teams"]
    # now FotMob is down
    p.fm = FailingFotMob()
    p.refresh_comp(comp)
    assert read(tmp_path, "comp/538/standings.json") == good
    assert p.store.health["comp:538:fotmob"]["ok"] is False
    p.save()
    h = read(tmp_path, "health.json")
    assert "comp:538:fotmob" in h["failing"]


def test_fallback_to_uaepl_when_fotmob_fails(tmp_path, fx):
    p = _poller(tmp_path)
    p.fm = FailingFotMob()
    called = {}

    def fake_competition(comp):
        called["yes"] = True
        return {"competition": {"id": 538, "season": None, "has_table": True}, "matches": [],
                "standings": {"comp": 538, "groups": [{"id": 538, "name": None, "rows": GOOD["groups"][0]["rows"]}],
                              "legend": [], "source": "uaepl"}, "leaders": None, "teams": []}
    p.up.competition = fake_competition
    comp = {"id": 538, "key": "x", "name_ar": "د", "name_en": "PL", "kind": "league", "scope": "uae",
            "matches_per_team": 26, "uaepl": "b8785e20"}
    p.refresh_comp(comp)
    assert called
    assert read(tmp_path, "comp/538/standings.json")["source"] == "uaepl"
    assert p.store.health["comp:538:uaepl-fallback"]["ok"] is True


def test_health_keeps_last_ok_time(tmp_path):
    p = _poller(tmp_path)
    p.store.ok("day:today")
    p.save()
    first = read(tmp_path, "health.json")["items"]["day:today"]["at"]
    p2 = _poller(tmp_path)
    p2.store.fail("day:today", "HTTP 500")
    p2.save()
    item = read(tmp_path, "health.json")["items"]["day:today"]
    assert item["ok"] is False and item["last_ok"] == first
