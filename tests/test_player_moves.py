"""Phase 2 of the transfers (spec docs/superpowers/specs/2026-10-09-transfers-design.md): every player's full transfer history
from his FotMob career (profile.json career.senior.teams), with the fee where Transfermarkt or the phase 1 ledger has it."""
import json, os, shutil, subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")

# FotMob's shape (newest first): [team id, name, start, end, apps, goals, assists, transferType]
MESSI = [[960720, "إنتر ميامي", "2023-07-15", None, "117", "102", "56", {"text": "free transfer", "localizationKey": "free_transfer"}],
         [207967, "MLS All-Stars", "2024-07-02", "2024-07-22", None, None, None, None],
         [9847, "باريس سان جيرمان", "2021-08-10", "2023-06-30", "75", "32", "34", {"text": "free transfer", "localizationKey": "free_transfer"}],
         [8634, "برشلونة", "2004-07-01", "2021-06-30", "765", "666", "230", None]]
LOANEE = [[1, "Parent", "2026-07-01", None, "3", None, None, None],
          [2, "Loan club", "2025-08-01", "2026-06-30", "30", None, None, {"localizationKey": "on_loan"}],
          [1, "Parent", "2023-07-01", "2025-07-31", "40", None, None, {"localizationKey": "contract"}],
          [3, "Academy", "2018-07-01", "2023-06-30", "10", None, None, None]]


def run(js):
    r = subprocess.run(["node", "-e", "const U = require(process.argv[1] + '/site/src/v5/ui.js');\n" + js, ROOT], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_messis_moves_newest_first_without_the_all_star_game():
    mv = run(f"console.log(JSON.stringify(U.careerMoves({json.dumps(MESSI)}, [])))")
    assert mv == [["2023-07-15", 9847, "باريس سان جيرمان", 960720, "إنتر ميامي", "free", None],
                  ["2021-08-10", 8634, "برشلونة", 9847, "باريس سان جيرمان", "free", None]]


def test_a_loan_and_the_way_back_and_a_fee_from_another_source():
    fees = [["2023-06-20", 1, 4000000]]        # [date, to club id, fee]: Transfermarkt's or the ledger's, matched within 60 days
    mv = run(f"console.log(JSON.stringify(U.careerMoves({json.dumps(LOANEE)}, {json.dumps(fees)})))")
    assert mv == [["2026-07-01", 2, "Loan club", 1, "Parent", "back", None],
                  ["2025-08-01", 1, "Parent", 2, "Loan club", "loan", None],
                  ["2023-07-01", 3, "Academy", 1, "Parent", "fee", 4000000]]


def test_trimmed_rows_and_nothing():
    trimmed = [[960720, "إنتر ميامي", "2023-07-15", None, "117", "free_transfer"], [9847, "باريس سان جيرمان", "2021-08-10", "2023-06-30", "75", "free_transfer"]]   # player_seo trimProfile: [id, name, start, end, apps, type key]
    assert run(f"console.log(JSON.stringify(U.careerMoves({json.dumps(trimmed)})))") == [["2023-07-15", 9847, "باريس سان جيرمان", 960720, "إنتر ميامي", "free", None]]
    assert run("console.log(JSON.stringify([U.careerMoves(null), U.careerMoves([[1, 'A', '2020-01-01', null, '5', null, null, null]])]))") == [[], []]


def test_the_pane_lists_every_move():
    out = run(f"""const P = require(process.argv[1] + '/site/src/v5/pages.js');
console.log(JSON.stringify(P.playerCareer({{ prof:{{ career:{{ senior:{{ seasons:[], teams:{json.dumps(LOANEE)} }} }} }}, transfers:[["2023-06-20", "2023/24", "Academy", 3, "Parent", 1, 4000000, null]] }})));""")
    assert "انتقالاته" in out and "رجع من الإعارة" in out and "إعارة" in out and "€4" in out


def test_the_trimmed_profile_keeps_the_moves():
    out = subprocess.run(["node", "-e", f"""const S = require(process.argv[1] + '/site/lib/player_seo.cjs');
const t = S.trimProfile({{ career:{{ senior:{{ seasons:[], teams:{json.dumps(MESSI)} }} }} }});
console.log(JSON.stringify([t.m, S.asProfile(t).career.senior.teams]));""", ROOT], capture_output=True, text=True, encoding="utf-8")
    m, back = json.loads(out.stdout)
    assert m[0] == [960720, "إنتر ميامي", "2023-07-15", None, "117", "free_transfer"] and back == m
