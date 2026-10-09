"""The <title> Google matches against the search box is in the Arabic people type there, not the site's light Emirati
(owner 2026-10-09: «نتايج» on the home page and «هالموسم» on 17k player pages were words nobody searches). The pages
themselves keep the Emirati voice; only titles are checked."""
import os, re, shutil, subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIALECT = ("نتايج", "هالموسم", "الحين", "الياية", "الياي", "وايد", "يديد", "جذيه", "منو ", "شو ", "بكرة", "اللي")
FILES = ("site/build.cjs", "site/build_arabs.cjs", "site/src/v5/pages.js", "site/lib/world_stage.cjs", "site/lib/player_seo.cjs")


def titles(path):
    src = open(os.path.join(ROOT, path), encoding="utf-8").read()
    return re.findall(r'title\s*:\s*(`[^`]*`|"[^"]*")', src) + re.findall(r"=> `\$\{o\.name\}: (.*?)` ", src)


@pytest.mark.parametrize("path", FILES)
def test_titles_are_in_the_arabic_people_search_in(path):
    bad = [t for t in titles(path) for w in DIALECT if w in t]
    assert not bad, bad


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_player_title_reads_like_a_search():
    js = "const S=require(process.argv[1]+'/site/lib/player_seo.cjs');console.log(S.title({name:'علي',team:'العين',nums:true}))"
    out = subprocess.run(["node", "-e", js, ROOT], capture_output=True, text=True, encoding="utf-8").stdout.strip()
    assert out == "علي: إحصائياته وأهدافه هذا الموسم مع العين | تيفو"


def test_the_site_says_telephone_the_emirati_way():
    """Owner 2026-10-09: «تلفونك» not «جوالك», in every visible string of the site's sources."""
    import glob
    hits = []
    for f in glob.glob(os.path.join(ROOT, "site", "src", "**", "*.js"), recursive=True) + [os.path.join(ROOT, "site", "build.cjs")] + glob.glob(os.path.join(ROOT, "site", "lib", "*.cjs")):
        for i, line in enumerate(open(f, encoding="utf-8"), 1):
            if "جوال" in line:
                hits.append(f"{os.path.relpath(f, ROOT)}:{i}")
    assert not hits, hits
