"""news/xhistory.js, the month of official X video posts for the goal-clip backfill. The 23:00 run of 2026-11-19 read six
European clubs, about 50 search pages in 6 minutes, before X's rate limit stopped it: the UAE and Arab accounts were never
reached (owner 2026-11-20, «Start with 1»). Now the UAE goes first, then the Gulf, the other Arab countries, the Arabic
accounts and the rest, and no more than BUDGET search pages go out in any 15 minutes."""
import json, os, shutil, subprocess
import pytest

JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "news", "xhistory.js").replace("\\", "/")
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node is not installed here")


def node(expr):
    out = subprocess.run(["node", "-e", f"const H=require({json.dumps(JS)});console.log(JSON.stringify({expr}))"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_uae_goes_first_then_the_gulf_the_other_arab_countries_and_the_rest():
    accs = [{"handle": "FCBarcelona"}, {"handle": "Al_Ahly", "country": "eg"}, {"handle": "beINSPORTS", "lang": "ar"},
            {"handle": "ADSportsTV", "country": "ae"}, {"handle": "Alhilal_FC", "country": "sa"}, {"handle": "alainfcae", "country": "ae"},
            {"handle": "MCA_Officiel", "country": "dz"}, {"handle": "LFC"}]
    got = node(f"H.order({json.dumps(accs)}).map(a => a.handle)")
    assert got == ["ADSportsTV", "alainfcae", "Alhilal_FC", "Al_Ahly", "MCA_Officiel", "beINSPORTS", "FCBarcelona", "LFC"]


def test_no_more_than_the_budget_of_search_pages_in_any_quarter_hour():
    q = 15 * 60_000
    assert node("H.wait([], 1e6, 3, %d)" % q) == 0
    assert node("H.wait([1e6 - 5000, 1e6 - 3000], 1e6, 3, %d)" % q) == 0
    # three in the window: the next waits until the first is a quarter-hour old (and a second more)
    assert node("H.wait([1e6 - 5000, 1e6 - 3000, 1e6 - 1000], 1e6, 3, %d)" % q) == q - 5000 + 1000
    # pages older than the window no longer count
    assert node("H.wait([1e6 - %d, 1e6 - 3000, 1e6 - 1000], 1e6, 3, %d)" % (q + 1, q)) == 0


def test_the_pages_an_earlier_run_sent_count_against_the_budget(tmp_path):
    # 2026-11-20: a second run started a minute after the first one ended counted from zero, and X stopped it at its 31st page
    f = tmp_path / "pages.json"
    f.write_text(json.dumps([1e9 - 1000, 1e9 - 20 * 60_000]), encoding="utf-8")
    assert node(f"H.loadStamps({json.dumps(str(f).replace(chr(92), '/'))}, 1e9)") == [1e9 - 1000]
    assert node(f"H.loadStamps({json.dumps(str(tmp_path / 'none.json').replace(chr(92), '/'))}, 1e9)") == []
