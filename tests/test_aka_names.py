"""«يُكتب أيضاً» (owner 2026-10-09, idea 3): other Arabic spellings of a player's name, from Arabic Wikipedia redirects to his
article (names/aka.py -> names/players_ar_aka.json), shown on /p/ pages and in Person.alternateName. Measured on 300 players:
220 have an Arabic article, 30 a real variant."""
import json, os, shutil, subprocess, sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "names"))
import aka as A  # noqa: E402


def test_variants_keep_real_arabic_spellings_only():
    main = "تايلر آدمز"
    redirects = ["تايلر ادامس", "تايلر آدمز", "تايلر ادمز", "Tyler Adams", "تایلر آدامز", "ادمز", "تايلر آدامس (لاعب كرة قدم)"]
    assert A.variants(main, redirects) == ["تايلر ادامس"]          # hamza/alif-only, Latin, Persian letters, one short word, a
    assert A.variants("إدين دجيكو", ["ادين دجيكو", "إدين دزيكو"]) == ["إدين دزيكو"]   # disambiguation copy all dropped
    assert A.variants("س", []) == []


def test_at_most_four_and_stable_order():
    vs = A.variants("محمد صلاح", [f"محمد صلاح{x}" for x in "بتثجحخد"])
    assert len(vs) == 4 and vs == sorted(vs)


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_person_and_page_carry_the_spellings():
    js = r"""
const S = require(process.argv[1] + '/site/lib/player_seo.cjs'), P = require(process.argv[1] + '/site/src/v5/pages.js');
const p = S.person({site: 'https://x', id: 1, name: 'تايلر آدمز', latin: 'Tyler Adams', aka: ['تايلر ادامس']});
const one = S.person({site: 'https://x', id: 1, name: 'تايلر آدمز', latin: 'Tyler Adams'});
const page = P.player(1, {name: 'تايلر آدمز', latin: 'Tyler Adams', team: null, x: {mount: true, profile: '', aka: ['تايلر <ادامس>']}}).body;
console.log(JSON.stringify({alt: p.alternateName, one: one.alternateName, page}));"""
    out = json.loads(subprocess.run(["node", "-e", js, ROOT], capture_output=True, text=True, encoding="utf-8").stdout)
    assert out["alt"] == ["Tyler Adams", "تايلر ادامس"] and out["one"] == "Tyler Adams"
    assert "يُكتب أيضاً: تايلر &lt;ادامس&gt;" in out["page"]


def test_another_person_or_a_typo_is_not_a_spelling():
    assert A.variants("محمد وعد", ["محمد جدوع", "محمد وعد عبد الوهاب"]) == ["محمد وعد عبد الوهاب"]   # a different man; a fuller name
    assert A.variants("حمزة الركراكي", ["حمزةة الركراكي"]) == []                                    # a typo redirect
    assert A.variants("غابرييل مارتينيلي", ["جبريل مارتينيلي"]) == ["جبريل مارتينيلي"]
    assert A.variants("مايكل أوليسه", ["مايكل أوليز"]) == ["مايكل أوليز"]
