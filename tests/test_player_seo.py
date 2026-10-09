"""The player pages Google sends visitors to (owner item 11, 2026-10-09): site/lib/player_seo.cjs builds the honest title, the
one-paragraph intro, the Person JSON-LD and this season's row, and keeps the /p/ players' career profiles in a cache that is
re-read once per data generation, a budget per run."""
import json, os, re, shutil, subprocess, tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="node is not installed")

SCRIPT = r"""
const root = process.argv[1], dir = process.argv[2];
const S = require(root + '/site/lib/player_seo.cjs');
const prof = {bio: {born: '2003-04-09', h: 188, cc: 'BOL'}, career: {senior: {seasons: [
    ['2026', 1001, 'Bolivar', 14, 3, 2, '7.1', 'x'], ['2025', 1001, 'Bolivar', 30, 5, 1, '6.9'], ['2024', 1002, 'Old FC', 0, 0, 0]]},
  'national team': {seasons: [['2025', 8, 'Bolivia', 4, 0, 0]]}}, trophies: [[1001, 'Bolivar', 0, 'League', ['2024/2025']], [1, 'x', 0, 'Cup', []]]};
const stale = {career: {senior: {seasons: [['2024/2025', 1, 'A', 20, 2, 0]]}}};
(async () => {
  const fetched = [];
  const get = async p => { fetched.push(p); return p.includes('/9/') ? null : prof; };
  const pool = async (xs, n, fn) => Promise.all(xs.map(fn));
  const r1 = await S.refreshCareers({ids: ['1', '2', '3', '9'], gen: 'g1', get, pool, dir, budget: 2});
  const after1 = S.loadCareers(dir);
  const r2 = await S.refreshCareers({ids: ['1', '2', '3', '9'], gen: 'g1', get, pool, dir, budget: 10});
  const r3 = await S.refreshCareers({ids: ['1', '2', '3', '9'], gen: 'g1', get, pool, dir, budget: 10});
  const r4 = await S.refreshCareers({ids: ['1', '3'], gen: 'g2', get, pool, dir, budget: 10});
  const after4 = S.loadCareers(dir);
  console.log(JSON.stringify({
    trim: S.trimProfile(prof), trimNull: S.trimProfile(null),
    row: S.seasonRow(S.trimProfile(prof)), rowStale: S.seasonRow(S.trimProfile(stale)), rowNone: S.seasonRow(null),
    tot: S.careerTotals(S.trimProfile(prof)),
    titleNums: S.title({name: 'علي', team: 'العين', nums: true}), titleBare: S.title({name: 'علي', team: '', nums: false}),
    intro: S.intro({name: 'إدواردو ألفاريز', pos: 'قلب دفاع', country: 'بوليفيا', team: 'بوليفار', age: 23, comp: 'الدوري البوليفي',
                    season: {apps: 14, g: 3, a: 2}}),
    introOne: S.intro({name: 'سالم', team: 'العين', season: {apps: 1, g: 1, a: 0}}),
    introTwo: S.intro({name: 'سالم', team: 'العين', season: {apps: 2, g: 2, a: 2}}),
    introCareer: S.intro({name: 'سالم', pos: 'مهاجم', team: 'العين', career: {apps: 44, g: 8, seasons: 3}}),
    introZero: S.intro({name: 'سالم', team: 'العين', season: {apps: 0, g: 0, a: 0}}),
    introLeague: S.intro({name: 'دجيكو', team: 'شالكه', league: {comp: 'الدوري الألماني الثاني', min: 86, g: 0, a: 0}, season: {apps: 4, g: 2, a: 1}}),
    introLeagueG: S.intro({name: 'دجيكو', team: 'شالكه', league: {comp: '', min: 300, g: 3, a: 1}}),
    introLeague0: S.intro({name: 'دجيكو', team: 'شالكه', league: {comp: 'x', min: 0, g: 0, a: 0}, season: {apps: 4, g: 2, a: 1}}),
    introNothing: S.intro({name: 'سالم'}),
    person: S.person({site: 'https://tifo.elyoxe.com', id: 2777, name: 'إدواردو', latin: 'Eduardo Álvarez', born: '2003-04-09', h: 188,
                      country: 'بوليفيا', team: 'بوليفار', image: '/v1/ph/2777.webp'}),
    personBare: S.person({site: 'https://tifo.elyoxe.com', id: 5, name: '', latin: 'X Y', born: '1899-01-01'}),
    r1, r2, r3, r4, n1: Object.keys(after1.careers).length, n4: Object.keys(after4.careers).sort(), fetched,
  }));
})().catch(e => { console.error(e); process.exit(1); });
"""


@pytest.fixture(scope="module")
def out():
    d = tempfile.mkdtemp()
    r = subprocess.run([NODE, "-e", SCRIPT, ROOT, d], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_trim_keeps_the_seasons_and_the_won_trophies(out):
    t = out["trim"]
    assert t["s"][0] == ["2026", 1001, "Bolivar", 14, 3, 2, "7.1"]          # 7 columns, the rest dropped
    assert t["n"] == [["2025", 8, "Bolivia", 4, 0, 0]]
    assert t["t"] == [[1001, "Bolivar", "League", ["2024/2025"]]]           # a trophy with no season won is dropped
    assert out["trimNull"] is None


def test_this_seasons_row_only_for_the_current_season(out):
    assert out["row"] == {"season": "2026", "apps": 14, "g": 3, "a": 2, "team": 1001}
    assert out["rowStale"] is None and out["rowNone"] is None
    assert out["tot"] == {"apps": 44, "g": 8, "seasons": 2}              # seasons with no match are not counted


def test_the_title_promises_numbers_only_when_there_are_some(out):
    assert out["titleNums"] == "علي: إحصائياته وأهدافه هذا الموسم مع العين | تيفو"
    assert out["titleBare"] == "علي: مسيرته وبطاقته | تيفو"


def test_the_intro_is_one_true_sentence_pair_in_light_emirati(out):
    assert out["intro"] == ("إدواردو ألفاريز قلب دفاع من بوليفيا، يلعب مع بوليفار، عمره 23 سنة. "
                            "هالموسم لعب 14 مباراة في الدوري البوليفي، وسجّل 3 أهداف وصنع هدفين.")
    assert out["introOne"] == "سالم يلعب مع العين. هالموسم لعب مباراة وحدة، وسجّل هدف واحد."
    assert out["introTwo"] == "سالم يلعب مع العين. هالموسم لعب مباراتين، وسجّل هدفين وصنع هدفين."
    assert out["introCareer"] == "سالم مهاجم، يلعب مع العين. لعب 44 مباراة مع الأندية في 3 مواسم، وسجّل 8 أهداف."
    assert out["introZero"] == "سالم يلعب مع العين."
    assert out["introNothing"] == ""
    # the league file's numbers win (the page's tiles show them): one set of numbers per page
    assert out["introLeague"] == "دجيكو يلعب مع شالكه. هالموسم لعب 86 دقيقة في الدوري الألماني الثاني."
    assert out["introLeagueG"] == "دجيكو يلعب مع شالكه. هالموسم لعب 300 دقيقة، وسجّل 3 أهداف وصنع هدف واحد."
    assert out["introLeague0"] == "دجيكو يلعب مع شالكه. هالموسم لعب 4 مباريات، وسجّل هدفين وصنع هدف واحد."
    for k in ("intro", "introOne", "introTwo", "introCareer"):
        assert not any(w in out[k] for w in ("وش", "مين", "زي", "تبي", "ً", "ٌ", "ٍ")), k


def test_person_ld(out):
    p = out["person"]
    assert p["@type"] == "Person" and p["name"] == "إدواردو" and p["alternateName"] == "Eduardo Álvarez"
    assert p["url"] == "https://tifo.elyoxe.com/p/2777/" and p["birthDate"] == "2003-04-09"
    assert p["height"] == {"@type": "QuantitativeValue", "value": 188, "unitCode": "CMT"}
    assert p["nationality"] == {"@type": "Country", "name": "بوليفيا"}
    assert p["affiliation"] == {"@type": "SportsTeam", "name": "بوليفار"}
    assert p["image"] == "https://tifo.elyoxe.com/v1/ph/2777.webp"
    b = out["personBare"]
    assert b["name"] == "X Y" and "birthDate" not in b and "alternateName" not in b and "affiliation" not in b


def test_the_career_cache_reads_each_player_once_per_generation_within_the_budget(out):
    assert out["r1"] == {"fetched": 2, "failed": 0, "waiting": 2, "cached": 2}
    assert out["n1"] == 2
    assert out["r2"] == {"fetched": 1, "failed": 1, "waiting": 0, "cached": 3}     # player 9 has no profile
    assert out["r3"] == {"fetched": 0, "failed": 0, "waiting": 0, "cached": 3}     # nothing left under g1
    assert out["r4"] == {"fetched": 2, "failed": 0, "waiting": 0, "cached": 2}     # a new generation; 2 left the list
    assert out["n4"] == ["1", "3"]
    assert out["fetched"].count("player/1/profile.json") == 2


PAGE = r"""
const root = process.argv[1];
const S = require(root + '/site/lib/player_seo.cjs'), P = require(root + '/site/src/v5/pages.js');
const car = S.trimProfile({career: {senior: {seasons: [['2026', 1001, 'Bolivar', 14, 3, 2, '7.1']]}}});
const base = {name: 'إدواردو', latin: 'Eduardo', team: {id: 1001, name_ar: 'بوليفار'}, pos: 'Center Back', cc: 'BOL', card: null, transfers: null};
const full = P.player(2777, Object.assign({}, base, {prof: Object.assign({bio: {born: '2003-04-09'}}, S.asProfile(car)), seasonRow: S.seasonRow(car),
  x: {mount: true, intro: 'إدواردو يلعب مع <بوليفار>.', follow: true, profile: ''}}));
const bare = P.player(5, Object.assign({}, base, {prof: null, x: {mount: true, profile: ''}}));
console.log(JSON.stringify({full: full.body, bare: bare.body}));
"""


@pytest.fixture(scope="module")
def page():
    r = subprocess.run([NODE, "-e", PAGE, ROOT], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_the_page_carries_the_career_the_tiles_and_the_intro(page):
    h = page["full"]
    assert '<div id="pcar1" data-pre="1">' in h and "مع الأندية" in h and "<td>14</td>" in h     # the career, in the page itself
    assert '<h2>هالموسم</h2><span class="num">2026</span>' in h and "<b>14</b><span>مباراة</span>" in h
    assert "إدواردو يلعب مع &lt;بوليفار&gt;." in h                                             # the intro, escaped
    assert 'data-fav="t:1001"' in h and "<span>تابع</span> <bdi>بوليفار</bdi>" in h     # paintFav() rewrites the <span> only
    assert re.search(r'href="[^"]*1001[^"]*#notify"', h) and "نبّهني لمبارياته" in h       # L(): /t/1001/ in the build
    assert 'data-sheet="sh-pnotify"' in h and "تابع اللاعب" in h                           # «تابع اللاعب» (player follow)
    assert h.index("إدواردو يلعب مع") < h.index("<h2>هالموسم</h2>") < h.index('id="pcar1"')


def test_a_player_without_a_cached_career_still_loads_it_in_the_browser(page):
    h = page["bare"]
    assert '<div id="pcar1"><div class="card pend">' in h and "data-pre" not in h
    assert "<h2>هالموسم</h2>" not in h and 'data-fav="t:' not in h                             # no numbers, no follow without x.follow
