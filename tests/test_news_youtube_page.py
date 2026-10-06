"""news/readers.py youtube_page: a channel read from its own pages while YouTube's feeds answer 404 (2026-10-06)."""
import json
from datetime import datetime, timedelta, timezone

from news import readers as RD

NOW = datetime(2026, 10, 6, 4, 0, tzinfo=timezone.utc)
SRC = {"key": "yt_x", "kind": "youtube", "lang": "en", "tier": "official", "name": "X FC", "owner": ["team", 1],
       "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCabc"}


def page(data):
    return '<html><script>var ytInitialData = ' + json.dumps(data) + ';</script></html>'


def video(vid, title, label):
    return {"lockupViewModel": {"contentId": vid, "contentType": "LOCKUP_CONTENT_TYPE_VIDEO", "metadata": {"lockupMetadataViewModel": {
        "title": {"content": title}, "metadata": {"contentMetadataViewModel": {"metadataRows": [{"metadataParts": [
            {"text": {"content": "1K"}, "accessibilityLabel": "1 thousand views"}, {"text": {"content": "x"}, "accessibilityLabel": label}]}]}}}}}}


def short(vid, title):
    return {"shortsLockupViewModel": {"onTap": {"innertubeCommand": {"reelWatchEndpoint": {"videoId": vid}}},
                                      "overlayMetadata": {"primaryText": {"content": title}}}}


def setup(monkeypatch, tmp_path, tabs):
    monkeypatch.setattr(RD, "YT_SEEN", str(tmp_path / "yt-seen.json"))
    RD._SEEN.clear()
    monkeypatch.setattr(RD, "_yt_html", lambda cid, tab, timeout=20: page({"items": tabs[tab]}))


def test_videos_get_their_age_and_keep_the_first_estimate(monkeypatch, tmp_path):
    tabs = {"videos": [video("aaaaaaaaaaa", "Goal of the week", "2 hours ago"), video("bbbbbbbbbbb", "Live now", "1,234 watching"),
                       video("ccccccccccc", "Highlights", "Streamed 3 days ago")], "shorts": []}
    setup(monkeypatch, tmp_path, tabs)
    got = RD.youtube_page(SRC, now=NOW)
    by = {g["url"]: g for g in got}
    assert set(by) == {"https://www.youtube.com/watch?v=aaaaaaaaaaa", "https://www.youtube.com/watch?v=ccccccccccc"}   # the live one has no age
    a = by["https://www.youtube.com/watch?v=aaaaaaaaaaa"]
    assert a["at"] == "2026-10-06T02:00:00Z" and a["id"] == RD.item_id(a["url"]) and a["owner"] == ["team", 1]
    assert a["image"] == "https://i.ytimg.com/vi/aaaaaaaaaaa/hqdefault.jpg"
    assert by["https://www.youtube.com/watch?v=ccccccccccc"]["at"] == "2026-10-03T04:00:00Z"
    # an hour later the page still says «2 hours ago»: the first estimate stays, from memory and from the file
    RD._SEEN.clear()
    later = RD.youtube_page(SRC, now=NOW + timedelta(minutes=50))
    assert {g["url"]: g["at"] for g in later}["https://www.youtube.com/watch?v=aaaaaaaaaaa"] == "2026-10-06T02:00:00Z"


def test_shorts_up_before_the_first_read_are_never_listed(monkeypatch, tmp_path):
    tabs = {"videos": [], "shorts": [short("sssssssssss", "Old short")]}
    setup(monkeypatch, tmp_path, tabs)
    assert RD.youtube_page(SRC, now=NOW) == []
    tabs["shorts"] = [short("ttttttttttt", "Goal! 1-0"), short("sssssssssss", "Old short")]
    got = RD.youtube_page(SRC, now=NOW + timedelta(minutes=15))
    assert [(g["url"], g["at"]) for g in got] == [("https://www.youtube.com/shorts/ttttttttttt", "2026-10-06T04:15:00Z")]


def test_a_failing_feed_falls_back_to_the_page(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path, {"videos": [video("aaaaaaaaaaa", "Goal", "5 minutes ago")], "shorts": []})

    def no_feed(url, timeout=20):
        raise RD.urllib.error.HTTPError(url, 404, "Not Found", {}, None)
    monkeypatch.setattr(RD, "fetch", no_feed)
    got, err = RD.read_source(SRC)
    assert err is None and [g["url"] for g in got] == ["https://www.youtube.com/watch?v=aaaaaaaaaaa"]
    # a page with no data (a consent or check page) is an error, never an empty success
    monkeypatch.setattr(RD, "_yt_html", lambda cid, tab, timeout=20: "<html>consent</html>")
    got, err = RD.read_source(SRC)
    assert got == [] and "404" in err and "ytInitialData" in err
