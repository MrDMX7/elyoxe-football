"""tools/archive_job.py: the archive pages go up only where their bytes changed, and their sitemaps hold 45,000 URLs each."""
import os
from tools import archive_job as J


class S3:
    def __init__(self, fail=()):
        self.put, self.fail = [], set(fail)

    def put_object(self, Bucket, Key, Body, ContentType, CacheControl):
        if Key in self.fail:
            raise RuntimeError("slow down")
        self.put.append((Key, ContentType))


def pages(tmp_path, d):
    for k, body in d.items():
        p = tmp_path / k
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")


def test_only_new_and_changed_pages_go_up_and_a_failed_one_is_sent_again_next_run(tmp_path):
    pages(tmp_path, {"m/k1/index.html": "a", "m/k2/index.html": "b", "m/k3/index.html": "c", "_archive_urls.json": "[]", "sitemap-archive.xml": "<x/>"})
    old = {"m/k1/index.html": J.md5(tmp_path / "m/k1/index.html"), "m/k2/index.html": "stale"}
    s3 = S3(fail={"m/k3/index.html"})
    new, sent = J.upload(s3, "b", str(tmp_path), old)
    assert sorted(k for k, _ in s3.put) == ["m/k2/index.html", "sitemap-archive.xml"]
    assert ("sitemap-archive.xml", "application/xml; charset=utf-8") in s3.put
    assert "m/k3/index.html" not in new and "_archive_urls.json" not in new and sent == 2


def test_sitemaps_of_45000_urls_and_their_index(tmp_path):
    urls = [f"/m/k{i}/" for i in range(90001)]
    names = J.sitemaps(str(tmp_path), urls)
    assert names == ["sitemap-archive-1.xml", "sitemap-archive-2.xml", "sitemap-archive-3.xml"]
    idx = (tmp_path / "sitemap-archive.xml").read_text(encoding="utf-8")
    assert idx.count("<loc>") == 3 and "https://tifo.elyoxe.com/sitemap-archive-3.xml" in idx
    assert (tmp_path / "sitemap-archive-3.xml").read_text(encoding="utf-8").count("<loc>") == 1


def test_a_page_whose_only_change_is_the_sites_asset_names_is_not_sent_again(tmp_path):
    # every site deploy renames its hashed assets (app.fccd68cafc.css): 353,513 pages re-sent a run
    pages(tmp_path, {"m/k1/index.html": '<link href="/assets/app.aaaaaaaaaa.css"><main>2-1</main>',
                     "m/k2/index.html": '<link href="/assets/app.aaaaaaaaaa.css"><main>3-0</main>'})
    old_shell, new_shell = '<link href="/assets/app.bbbbbbbbbb.css">', '<link href="/assets/app.aaaaaaaaaa.css">'
    old = {"m/k1/index.html": J.content_md5('<link href="/assets/app.bbbbbbbbbb.css"><main>2-1</main>', J.tokens(old_shell)),
           "m/k2/index.html": J.content_md5('<link href="/assets/app.bbbbbbbbbb.css"><main>1-0</main>', J.tokens(old_shell))}
    s3 = S3()
    new, sent = J.upload(s3, "b", str(tmp_path), old, strip=J.tokens(new_shell))
    assert [k for k, _ in s3.put] == ["m/k2/index.html"]                 # its score changed; k1 only the asset name
    s3 = S3()
    J.upload(s3, "b", str(tmp_path), old, strip=J.tokens(new_shell), full=True)
    assert len(s3.put) == 2                                              # the weekly full refresh sends them all


def test_a_page_the_manifest_holds_but_the_bucket_lost_is_sent_again(tmp_path):
    # 23 Nov 2026: an old site publish deleted 35,296 profiles the manifest said were up; the run never sent them again
    pages(tmp_path, {"p/k1/index.html": "a", "p/k2/index.html": "b", "m/k3/index.html": "c"})
    old = {k: J.md5(tmp_path / k) for k in ("p/k1/index.html", "p/k2/index.html", "m/k3/index.html")}

    class Listed(S3):
        def get_paginator(self, _):
            class P:
                def paginate(self, Bucket, Prefix=""):
                    yield {"Contents": [{"Key": k} for k in ("p/k1/index.html", "m/k3/index.html", "c/x/index.html") if k.startswith(Prefix)]}
            return P()
    s3 = Listed()
    kept = J.still_up(s3, "b", old)
    assert sorted(kept) == ["m/k3/index.html", "p/k1/index.html"]
    J.upload(s3, "b", str(tmp_path), kept)
    assert [k for k, _ in s3.put] == ["p/k2/index.html"]


def test_the_site_coach_pages_are_known_so_the_archive_links_them_and_writes_no_second():
    class Listed:
        def get_paginator(self, _):
            class P:
                def paginate(self, Bucket, Prefix=""):
                    keys = ["coach/500/index.html", "coach/k7/index.html", "coach/compare/index.html", "p/30981/index.html"]
                    yield {"Contents": [{"Key": k} for k in keys if k.startswith(Prefix)]}
            return P()
    k = J.known_pages(Listed(), "b")
    assert k["coach"] == ["500"] and k["p"] == ["30981"]


def test_the_lost_page_check_lists_the_coach_pages_too():
    assert "coach/k" in J.ARCHIVE_PREFIXES


def test_the_archives_own_pages_no_run_wrote_are_swept_and_the_sites_are_not():
    # 23 Nov 2026: 20,270 old-match pages the site build published on 22 Nov (copies the seasons pass has since merged into
    # their twin) sat in the bucket, linked from nowhere, duplicating real match pages
    up = {"m/k1/index.html", "m/k9/index.html", "c/x/index.html", "c/x/s/1990/index.html", "c/x/s/1880/index.html", "p/30981/index.html", "coach/500/index.html"}
    new = {"m/k1/index.html": "a", "c/x/s/1990/index.html": "b"}
    assert J.orphans(up, new) == ["c/x/s/1880/index.html", "m/k9/index.html"]


def test_the_photo_index_hands_the_renderer_the_men_and_the_coaches():
    assert J.archive_photos({"k1": 1, "c2": 2, "30981": 3}) == {"k1": 1, "c2": 2}


def test_the_fotmob_to_archive_map_goes_out_whole_for_the_site_and_in_100_shards_for_the_browser():
    files = J.fm2k_files({"4000001": 1, "4000101": 2, "4000002": 3})
    assert files["v1/archive/fm2k.json"] == {"4000001": 1, "4000101": 2, "4000002": 3}
    assert files["v1/archive/fm2k/1.json"] == {"4000001": 1, "4000101": 2}
    assert files["v1/archive/fm2k/2.json"] == {"4000002": 3}
    assert len([k for k in files if k.startswith("v1/archive/fm2k/")]) == 100      # every shard, empty ones too: no 404 in the browser


def test_the_fotmob_to_profile_map_goes_out_like_the_matches_one():
    files = J.map_files("fm2p", {"1526227": 5, "77": 6})
    assert files["v1/archive/fm2p.json"] == {"1526227": 5, "77": 6}
    assert files["v1/archive/fm2p/27.json"] == {"1526227": 5} and files["v1/archive/fm2p/77.json"] == {"77": 6}


def test_a_fotmob_profile_is_cut_to_what_the_archive_profile_shows():
    raw = {"bio": {"name": "Eugene Frimpong", "h": 174, "shirt": 16, "cc": "GHA", "mv": 139630, "contract": "2027-06-30", "pos": "وسط", "team": 1585, "n": 6},
           "career": {"senior": {"seasons": [["2025/2026", 8005, "Ponferradina", "32", "2", "0", "6.05", []], ["2024/2025", 4031, "Zamora", "10", "0", "0", None, []]]}}}
    assert J.fm_profile(raw) == {"bio": {"h": 174, "shirt": 16, "mv": 139630, "contract": "2027-06-30", "pos": "وسط", "team": 1585},
                                 "s0": ["2025/2026", 8005, 32, 2, 0, 6.05]}
    assert J.fm_profile({}) is None


def test_a_page_whose_man_or_match_was_folded_into_another_forwards_to_the_kept_one(tmp_path):
    """23 Nov 2026: Thierry Henry's three records became one; the two pages that go would be 404s for whoever kept the link"""
    pages(tmp_path, {"p/k124/index.html": "henry", "m/k9/index.html": "match"})
    old = {"p/k124/index.html": "a", "p/k107585/index.html": "b", "p/k5/index.html": "c", "m/k8/index.html": "d", "m/k7/index.html": "e"}
    merged = {"player": {107585: 124, 5: 6}, "match": {8: 9}}
    got = J.forwards(tmp_path, old, merged)
    assert got == {"p/k107585/index.html": "/p/k124/", "m/k8/index.html": "/m/k9/"}      # k5's kept man has no page; k7 not folded
    h = (tmp_path / "p/k107585/index.html").read_text(encoding="utf-8")
    assert 'rel="canonical" href="https://tifo.elyoxe.com/p/k124/"' in h and 'content="0;url=/p/k124/"' in h and "noindex" in h


def test_the_merges_are_read_from_the_graph(tmp_path):
    import json, sqlite3
    db = tmp_path / "t.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT)")
    c.execute("INSERT INTO meta VALUES('merged', ?)", (json.dumps({"player": {"107585": 124}}),))
    c.commit(); c.close()
    assert J.merged_of(str(db)) == {"player": {107585: 124}}
    assert J.merged_of(str(tmp_path / "none.db")) == {}
