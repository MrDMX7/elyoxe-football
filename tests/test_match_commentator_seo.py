"""«معلق مباراة X و Y» (owner 2026-10-09): the commentator Tifo knows (news/commentators.py -> v1/tv/<ymd>.json) is in the
match page's title, description and HTML, not only painted by src/tv.js after load."""
import json, os, shutil, subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")

JS = r"""
const M = require(process.argv[1] + '/site/lib/match_seo.cjs'), P = require(process.argv[1] + '/site/src/v5/pages.js');
const tv = [{channel: 'ثمانية', commentator: 'مشعل الشمري'}, {channel: 'SSC <1>', commentator: null}];
const base = {H0: 'الخلود', A0: 'القادسية', cN: 'دوري روشن السعودي', played: false, ww: false};
const md = {id: 5970150, status: 'scheduled', kickoff_utc: '2026-10-09T15:00:00Z', comp: 536, home: {id: 1, name_ar: 'الخلود'}, away: {id: 2, name_ar: 'القادسية'}, score: null, events: []};
console.log(JSON.stringify({
  t: M.title(Object.assign({}, base, {tv})), t0: M.title(base), tww: M.title(Object.assign({}, base, {ww: true})),
  tp: M.title(Object.assign({}, base, {played: true, score: {home: 2, away: 1}, tv})),
  d: M.lead(tv), d0: M.lead([]),
  page: P.match(md, {ch: '', tv: tv}).body, page0: P.match(md, {ch: ''}).body,
}));"""


@pytest.fixture(scope="module")
def out():
    r = subprocess.run(["node", "-e", JS, ROOT], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_title_names_the_commentator_only_when_known(out):
    assert out["t"] == "موعد مباراة الخلود والقادسية في دوري روشن السعودي والقناة الناقلة والمعلق | تيفو"
    assert out["t0"] == "موعد مباراة الخلود والقادسية في دوري روشن السعودي | تيفو"
    assert out["tww"] == "موعد مباراة الخلود والقادسية في دوري روشن السعودي والقناة الناقلة | تيفو"
    assert out["tp"] == "نتيجة مباراة الخلود والقادسية 2-1 في دوري روشن السعودي | تيفو"     # after kickoff: the result


def test_description_lead_and_page_carry_it(out):
    assert out["d"] == "المعلق: مشعل الشمري على ثمانية. "
    assert out["d0"] == ""
    h = out["page"]
    assert 'id="tvc"' in h and "مشعل الشمري" in h and "SSC &lt;1&gt;" in h
    assert 'id="tvc"' not in out["page0"]
