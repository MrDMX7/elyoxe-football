"""The last pass: what no loader owns and every build should be rid of (graph/integrity.py counts what is left).
A move from a club to itself is no move (Transfermarkt's rows, and two records of a club made one after the moves were
read); a move dated a millennium ahead takes the year of its season («3026-06-30» of 2025/2026)."""
import datetime
import re

SEASON_END = re.compile(r"(\d{4})\s*$")


def load(G, reg, S, today=None):
    ahead = str((today or datetime.date.today()).year + 2)
    n = {"moves_to_itself": G.c.execute("DELETE FROM transfer WHERE from_tid = to_tid").rowcount, "dates_set_right": 0, "dates_dropped": 0}
    for pid, date, to, season in G.c.execute("SELECT pid, date, to_tid, season FROM transfer WHERE substr(date, 1, 4) > ?", (ahead,)).fetchall():
        m = SEASON_END.search(season or "")
        right = m and m.group(1) + date[4:]
        where = "pid=? AND date=? AND to_tid IS ?"
        if right and right[:4] <= ahead and not G.c.execute(f"SELECT 1 FROM transfer WHERE {where}", (pid, right, to)).fetchone():
            G.c.execute(f"UPDATE transfer SET date=? WHERE {where}", (right, pid, date, to))
            n["dates_set_right"] += 1
        else:
            G.c.execute(f"DELETE FROM transfer WHERE {where}", (pid, date, to))
            n["dates_dropped"] += 1
    G.c.commit()
    return n
