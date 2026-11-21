"""Measure graph/load/teams.py on a built tifo.db, read-only: the pairs it folds and the honour conflicts that go.

    python tools/measure_team_merge.py C:/Users/requi/tifo-local/tifo.db
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph.load import teams as T  # noqa: E402


def main(path):
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    p = T.candidates(c)
    N = {t: (n, s, co) for t, n, s, co in c.execute("SELECT tid, name, src, country FROM team")}
    print("pairs", len(p))
    for d, k in p:
        print(d, N[d], "->", k, N[k])
    m = {str(d): str(k) for d, k in p}
    rows = c.execute("SELECT kept, other FROM conflict WHERE type='honour' AND field IN ('champion', 'runner_up')").fetchall()
    print("team honour conflicts", len(rows), "removed", sum(1 for a, b in rows if a != b and m.get(a, a) == m.get(b, b)))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "C:/Users/requi/tifo-local/tifo.db")
