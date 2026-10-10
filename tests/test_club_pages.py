"""Owner 2026-10-10 item 1: a static page for every club of the encyclopedia (/db/club/<id>/, site/lib/club_pages.cjs): before
it, 3,662 clubs lived only on the browser-drawn /db/club/?id= and ~26,000 links a build to them were unlinked."""
import json, os, shutil, subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")

CARD = {"id": 101918, "name": "Al Nassr FC", "name_ar": "النصر", "cc": "KSA", "country_ar": "السعودية", "league": 536, "league_ar": "دوري روشن السعودي",
        "position": 3, "venue": {"name": "Al-Awwal Park", "city": "Riyadh", "capacity": 26100},
        "trophies": [{"lid": "536", "name": "دوري روشن السعودي", "won": 4, "runnerup": 3, "seasons": ["2025/2026", "2018/2019"], "lost": []}],
        "squad": [[292198, "أنج بوستيكوغلو", None, "coach", "AUS"], [1125083, "نواف العقيدي", 1, "keepers", "KSA"], [1, "Cristiano Ronaldo", 7, "attackers", "POR"]]}
MOVES = [["2026-08-09", 1130583, "سامو", 8661, "مايوركا", 101918, "النصر", 24000000, "fee", None, "ESP", None]]


def page(card, moves=MOVES):
    js = f"""const C = require(process.argv[1] + '/site/lib/club_pages.cjs'), T = require(process.argv[1] + '/site/lib/transfers.cjs');
console.log(JSON.stringify(C.clubPage({json.dumps(card)}, {{ TRT:T, moves:{json.dumps(moves)}, rumours:[], season:"موسم 2026/27", site:"https://tifo.elyoxe.com",
  leaguePath:id => id === 536 ? "/transfers/saudi-pro-league/" : null }})));"""
    r = subprocess.run(["node", "-e", js, ROOT], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_the_page_says_who_the_club_is_its_players_transfers_and_titles():
    p = page(CARD)
    assert p["title"] == "النصر: اللاعبين والانتقالات والبطولات | تيفو"
    h = p["html"]
    assert "<h1>النصر</h1>" in h and "دوري روشن السعودي" in h and "/transfers/saudi-pro-league/" in h
    assert '<a class="row" href="/p/1125083/">' in h and "نواف العقيدي" in h and '<span class="lat">Cristiano Ronaldo</span>' in h
    assert "حراس المرمى" in h and "المدرب" in h and h.index("حراس المرمى") < h.index("الهجوم") < h.index("المدرب")
    assert "سامو" in h and "€24" in h                                       # this season's window from the ledger
    assert "4" in h and "2025/2026" in h                                    # the titles
    assert "Al-Awwal Park" in h
    assert p["ld"]["@type"] == "SportsTeam" and p["ld"]["url"] == "https://tifo.elyoxe.com/db/club/101918/"


def test_a_club_with_nothing_to_show_gets_no_page_and_no_arabic_name_none_either():
    assert page(dict(CARD, squad=[], trophies=[]), moves=[]) is None
    assert page(dict(CARD, name_ar=None)) is None                            # Arabic search needs the Arabic name
