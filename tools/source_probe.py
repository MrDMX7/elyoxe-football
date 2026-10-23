"""Can this machine read the database job's sources? One small request per source, made the way db/refresh.py's stages make
it (the same client, headers and endpoints), and a line per source: HTTP status, bytes, and whether the body is the data
or a block page. Written 2026-10-23 to decide whether «Tifo database» can leave the laptop for GitHub's runners
(datacenter IPs); run it on both and compare.

    python -m tools.source_probe
"""
import gzip, json, sys, time, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
BLOCK = ("captcha", "cf-chl", "access denied", "attention required", "just a moment", "are you a robot", "request blocked", "px-captcha")


def plain(url, headers=None, want=None):
    req = urllib.request.Request(url, headers=dict({"User-Agent": UA, "Accept-Encoding": "gzip"}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            st = r.status
    except urllib.error.HTTPError as e:
        raw, st = e.read() or b"", e.code
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    txt = raw[:4000].decode("utf-8", "replace").lower()
    ok = st == 200 and not any(b in txt for b in BLOCK) and (want is None or want in raw.decode("utf-8", "replace"))
    return st, len(raw), ok


def fotmob(url, want):
    from sources.fotmob import FotMob
    d = FotMob().http.get_json(url, min_ttl=0)
    s = json.dumps(d)
    return 200, len(s), want in s


SRC = [
    ("fotmob matchDetails (db.matches)", lambda: fotmob("https://www.fotmob.com/api/data/matchDetails?matchId=4813584", "header")),
    ("fotmob teams (db.fotmob_profiles, db.world)", lambda: fotmob("https://www.fotmob.com/api/data/teams?id=8456", "squad")),
    ("fotmob playerData (db.fotmob_profiles)", lambda: fotmob("https://www.fotmob.com/api/data/playerData?id=30981", "name")),
    ("fotmob leagues (db.fm_scorers)", lambda: fotmob("https://www.fotmob.com/api/data/leagues?id=47", "table")),
    ("365scores (db.scores365, db.scorers365)", lambda: plain("https://webws.365scores.com/web/competitions/?appTypeId=5&langId=27&timezoneName=Asia/Dubai&userCountryId=-1",
                                                           {"Accept": "application/json", "Origin": "https://www.365scores.com", "Referer": "https://www.365scores.com/"}, "competitions")),
    ("transfermarkt datasets r2.dev (history.transfermarkt, db.tmdata)", lambda: plain("https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/clubs.csv.gz", {"User-Agent": "elyoxe-tifo/0.1"})),
    ("understat (db.understat)", lambda: plain("https://understat.com/getLeagueData/EPL/2025", {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}, "teams")),
    ("eloratings (db.elo_nations)", lambda: plain("https://www.eloratings.net/World.tsv")),
    ("wikidata sparql (db.champions, photos)", lambda: plain("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote("SELECT ?x WHERE { wd:Q615 rdfs:label ?x } LIMIT 1"),
                                                     {"User-Agent": "elyoxe-tifo/0.1 (https://tifo.elyoxe.com; hello@elyoxe.com)"}, "bindings")),
    ("wikidata api (db.champions_wiki)", lambda: plain("https://www.wikidata.org/w/api.php?action=wbgetentities&ids=Q615&props=labels&languages=ar&format=json",
                                                      {"User-Agent": "elyoxe-tifo/0.1 (https://tifo.elyoxe.com; hello@elyoxe.com)"}, "entities")),
    ("ar.wikipedia (db.wiki_ar)", lambda: plain("https://ar.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote("ليونيل_ميسي"),
                                               {"User-Agent": "elyoxe-tifo/0.1 (https://tifo.elyoxe.com; hello@elyoxe.com)"}, "extract")),
    ("en.wikipedia (db.champions_wiki)", lambda: plain("https://en.wikipedia.org/w/api.php?action=parse&page=UAE_Pro_League&prop=sections&format=json",
                                                      {"User-Agent": "elyoxe-tifo/0.1 (https://tifo.elyoxe.com; hello@elyoxe.com)"}, "sections")),
    ("EA FC ratings (db.eafc)", lambda: plain("https://drop-api.ea.com/rating/ea-sports-fc?locale=en&limit=1&offset=0", {"Accept": "application/json"}, "items")),
    ("kassiesa (db.uefa)", lambda: plain("https://kassiesa.net/uefa/data/method5/crank2025.html")),
    ("rsssf (db.rsssf)", lambda: plain("https://www.rsssf.org/")),
    ("statsbomb github (history.statsbomb_messi)", lambda: plain("https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json", None, "competition_id")),
    ("youtube channel page (news.readers, the journal)", lambda: plain("https://www.youtube.com/@FIFA/videos", None, "videoId")),
]


def main():
    bad = 0
    for name, f in SRC:
        t0 = time.time()
        try:
            st, n, ok = f()
        except Exception as e:
            st, n, ok = type(e).__name__ + ": " + str(e)[:120], 0, False
        bad += not ok
        print(f"{'OK     ' if ok else 'BLOCKED'}  {name:62} {st}  {n} bytes  {time.time() - t0:.1f}s", flush=True)
    print(f"{len(SRC) - bad} of {len(SRC)} readable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
