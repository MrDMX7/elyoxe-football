"""Team pages of clubs outside the focus set (Al Nassr, 2026-10-09: «ما عندنا قائمة اللاعبين») take their squad from the
world club file (db/world.py: v1/world/club/<id>.json, members [id, name, shirt, group, ccode])."""
import json, os, shutil, subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_squad_from_world_members():
    js = r"""
const W = require(process.argv[1] + '/site/lib/world_squad.cjs');
console.log(JSON.stringify([W.squadFromWorld([[292198, 'أونج بوستيكوغلو', null, 'coach', 'AUS'], [1125083, 'نواف العقيدي', 1, 'keepers', 'KSA'],
  [1, 'B', 4, 'defenders', 'BRA'], [2, 'C', null, 'attackers', 'POR'], [3, 'D', 10, 'midfielders', 'KSA'], [0, 'x', 1, 'keepers', 'KSA']]), W.squadFromWorld(null)]));"""
    sq, none = json.loads(subprocess.run(["node", "-e", js, ROOT], capture_output=True, text=True, encoding="utf-8").stdout)
    assert [g["group"] for g in sq] == ["keepers", "defenders", "midfielders", "attackers", "coach"]        # the squad page's order
    assert sq[0]["players"] == [{"id": 1125083, "name": "نواف العقيدي", "number": 1, "country": "KSA"}]  # id 0 dropped
    assert sq[4]["players"][0]["name"] == "أونج بوستيكوغلو" and none == []


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_dead_links_go_to_the_encyclopedia():
    """The hourly build unlinked ~125,000 links a run to pages it does not write (2026-10-09: /t/ 59,822, /p/ 40,614,
    /m/ 24,795): a player with an encyclopedia page goes there, a club the encyclopedia knows goes to its card."""
    js = r"""
const { relink } = require(process.argv[1] + '/site/lib/world_squad.cjs');
const has = { written:new Set(['/db/player/77']), clubs:new Set([101918]) };
console.log(JSON.stringify(['/p/77/', '/p/78/', '/t/101918/', '/t/5/', '/c/x/', '/p/77/compare/', '/m/5121498/', '/m/1/g/2'].map(h => relink(h, has))));"""
    out = json.loads(subprocess.run(["node", "-e", js, ROOT], capture_output=True, text=True, encoding="utf-8").stdout)
    # a match: its encyclopedia card (39 of 40 sampled 2026-10-09 have matchx/<id>.json; the card says so when not)
    assert out == ["/db/player/77/", None, "/db/club/?id=101918", None, None, None, "/db/match/?id=5121498", None]


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_squad_from_fotmob_players():
    """A club the encyclopedia has no squad for (the Iraqi league's, 2026-10-09) takes the FotMob players of history/fm/players.json
    that name it as their team, grouped by position (English or Arabic), Arabic names first."""
    js = r"""
const W = require(process.argv[1] + '/site/lib/world_squad.cjs');
const P = { 1:{ name:'A', team:9, pos:'Keeper', shirt:1, cc:'IRQ' }, 2:{ name:'B', team:9, pos:'مهاجم', shirt:9, cc:'IRQ' }, 3:{ name:'C', team:9, pos:'Right Back', shirt:2 },
  4:{ name:'D', team:9, pos:'وسط', shirt:8 }, 5:{ name:'E', team:9, pos:'unknown' }, 6:{ name:'F', team:7, pos:'Keeper' }, 7:{ name:'G', team:9, pos:'Left Winger', shirt:11 } };
const s = W.squadFromFm(P, 9, id => ({ 2:'بي' })[id]);
console.log(JSON.stringify(s));"""
    sq = json.loads(subprocess.run(["node", "-e", js, ROOT], capture_output=True, text=True, encoding="utf-8").stdout)
    assert [g["group"] for g in sq] == ["keepers", "defenders", "midfielders", "attackers"]
    assert sq[0]["players"] == [{"id": 1, "name": "A", "number": 1, "country": "IRQ"}]
    assert [p["name"] for p in sq[3]["players"]] == ["بي", "G"]           # Arabic name when known; the unknown position left out


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_header_from_world_club():
    """The team page header («المدرب … · الملعب …») of a club with no team file: the coach from the squad's coach row, the stadium
    from the venue; nothing when the file has neither."""
    js = r"""
const W = require(process.argv[1] + '/site/lib/world_squad.cjs');
console.log(JSON.stringify([W.headFromWorld({ squad:[[292198, 'أونج بوستيكوغلو', null, 'coach', 'AUS'], [1, 'x', 1, 'keepers', 'KSA']],
  venue:{ name:'Al-Awwal Park', city:'Riyadh', capacity:26100 } }), W.headFromWorld({ squad:[], venue:null }), W.headFromWorld(null)]));"""
    a, b, c = json.loads(subprocess.run(["node", "-e", js, ROOT], capture_output=True, text=True, encoding="utf-8").stdout)
    assert a == {"coach": {"id": 292198, "name": "أونج بوستيكوغلو"}, "venue": {"name": "Al-Awwal Park", "city": "Riyadh", "capacity": 26100}}
    assert b == {} and c == {}
