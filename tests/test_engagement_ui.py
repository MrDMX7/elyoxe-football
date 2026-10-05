"""The engagement UI modules (site/src/notify.js, predict.js, voices.js) render in Node exactly as in the browser: v5 markup,
everything escaped, scores as one dir="rtl" run, Western digits, the v5 copy rules (site/redesign/v5/DESIGN.md §7)."""
import json, os, re, shutil, subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="node is not installed")

SCRIPT = r"""
const root = process.argv[1];
const N = require(root + '/site/src/notify.js'), P = require(root + '/site/src/predict.js'), V = require(root + '/site/src/voices.js');
const ix = {since: '2026-09-30', source: 'جدول القنوات الناقلة والمعلقين في كووورة، مربوط بمباريات تيفو',
  commentators: {a8130496: {name: 'عصام الشوالي', slug: 'عصام-الشوالي', n: 3, channels: [['beIN SPORTS 1', 2], ['beIN SPORTS 2', 1]],
    comps: [[42, 'دوري أبطال أوروبا', 2], [null, '', 1]], first: '2026-10-01', last: '2026-10-07',
    next: [[5181793, 'beIN SPORTS 1']], recent: [[5181794, 'beIN SPORTS 2'], [999, 'x<script>']]},
    'zz': {name: 'حفيظ دراجي', slug: 'حفيظ-دراجي', n: 1, channels: [], comps: [], first: '2026-10-02', last: '2026-10-02', next: [], recent: [[5181794, 'beIN SPORTS 2']]}},
  matches: {'5181793': {ko: '2026-10-07T19:00:00Z', h: [8634, 'برشلونة'], a: [8633, 'ريال مدريد'], c: [87, 'الدوري الإسباني'], page: true},
            '5181794': {ko: '2026-10-02T19:00:00Z', h: [1, 'فرنسا'], a: [2, 'بلجيكا<img src=x>'], c: [9806, 'دوري الأمم'], page: false}}};
console.log(JSON.stringify({
  nf: N.body({id: 5789, name: 'الإمارات <b>'}), nfSheet: N.sheet({id: 1, name: 'x'}),
  events: [N.eventsOf('goals', true), N.eventsOf('all', false), N.eventsOf('off', true), N.eventsOf('off', false)],
  modes: [N.modeOf(['goal']), N.modeOf(['start', 'goal', 'end', 'video']), N.modeOf(['video']), N.modeOf([])],
  hours: [N.hourAr(0), N.hourAr(60), N.hourAr(420), N.hourAr(720), N.hourAr(900), N.hourAr(1380)],
  block: P.block({id: 101, kickoff_utc: '2026-10-10T16:00:00Z', status: 'scheduled', home: {name_ar: 'العين'}, away: {name_ar: 'الوحدة"><script>'}}),
  board: P.board({members: [{rank: 1, nick: 'سالم<img>', tag: null, pts: 10, ex: 1, df: 1, oc: 1, me: true}, {rank: 2, nick: 'علي', tag: 'K7Q', pts: 0, ex: 0, df: 0, oc: 0}]}),
  pick: P.pickRow({match: 101, h: 2, a: 1, ko: '2026-10-10T16:00:00Z', home: {name: 'العين'}, away: {name: 'الوحدة'}, pts: 5, k: 'x', res: [2, 1]}),
  names: P.NAMES, comps: P.COMPS,
  vpage: V.page(ix, 'a8130496'), vslug: V.page(ix, 'عصام-الشوالي'), vlist: V.list(ix), vpick: V.picker(ix), vmissing: V.page(ix, 'nope'),
}));
"""


@pytest.fixture(scope="module")
def out():
    r = subprocess.run([NODE, "-e", SCRIPT, ROOT], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def all_html(out):
    return " ".join(v for v in out.values() if isinstance(v, str))


def test_v5_markup_and_hooks(out):
    nf = out["nf"]
    assert 'data-nf-team="5789"' in nf and 'class="seg"' in nf and 'data-seg="nf"' in nf and nf.count('role="switch"') == 2
    assert '<span class="sw" aria-hidden="true"></span>' in nf and 'data-nf="qs"' in nf and nf.count("<option") == 48
    assert out["nfSheet"].startswith('<dialog class="sheet" id="sh-notify"') and 'data-close aria-label="سكّر"' in out["nfSheet"]
    b = out["block"]
    assert 'class="grp tp" data-predict data-mid="101" data-kick="2026-10-10T16:00:00Z" data-status="scheduled"' in b
    assert b.count('dir="ltr"') == 2 and 'data-tp="save"' in b and 'href="/predict/"' in b
    assert '<span class="sc num" dir="rtl">2 - 1</span>' in out["pick"] and 'href="/m/101/"' in out["pick"]
    assert 'class="row tp-lb me"' in out["board"] and "#K7Q" in out["board"]
    assert '<h1>عصام الشوالي</h1>' in out["vpage"] and out["vslug"] == out["vpage"] and 'data-voice="a8130496"' in out["vpage"]
    assert 'href="/m/5181793/"' in out["vpage"] and 'href="/live/?id=5181794"' in out["vpage"]      # a match without a page of its own
    assert "علّق على 3 مباريات من 30 سبتمبر 2026، أكثرها على beIN SPORTS 1." in out["vpage"]
    assert "كووورة" in out["vpage"] and 'href="/commentators/%D8%B9' in out["vlist"]
    assert out["vpick"].count('role="switch"') == 2 and "ما عندنا" in out["vmissing"]


def test_choices_map_to_the_servers_events(out):
    assert out["events"] == [["goal", "video"], ["start", "goal", "end"], ["video"], []]
    assert out["modes"] == ["goals", "all", "off", "off"]
    assert out["hours"] == ["12 بالليل", "1 بالليل", "7 الصبح", "12 الظهر", "3 العصر", "11 بالليل"]
    assert out["names"][0] == "دوري الربع" and len(out["names"]) == 10                     # the server's LEAGUE_NAMES order
    assert all(len(ids) <= 5 for ids, _ in out["comps"])                                    # the server's COMPS_MAX


def test_everything_from_data_is_escaped(out):
    h = all_html(out)
    assert "<script>" not in h and "<img" not in h and "<b>" not in out["nf"].replace("<b>الإمارات &lt;b&gt;</b>", "")
    assert "&lt;script&gt;" in out["block"] and "&lt;img&gt;" in out["board"] and "&lt;img src=x&gt;" in out["vpage"]


def test_western_digits_and_the_copy_rules(out):
    h = all_html(out)
    assert not re.search("[٠-٩]", h)
    for banned in ("وش", "زي", "تبي", "الجاي", "جديد", "مين"):          # site/redesign/v5/DESIGN.md §7
        assert not re.search(r"(?<![؀-ۿ])" + banned + r"(?![؀-ۿ])", h), banned
