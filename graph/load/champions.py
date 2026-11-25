"""Champions read by hand (graph/champions.yaml) for leagues whose games name none: the honour «champion» on the edition of
that season, when the club played in it and no source named a champion before (the first source keeps the title). No
edition, club or game is minted. Runs once the clubs two sources hold are one, and before seasons."""
import os
from collections import Counter

import yaml

FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "champions.yaml")
SRC = "rsssf"


def load(G, reg, S, path=FILE):
    data = yaml.safe_load(open(path, encoding="utf-8")) or {}
    n = Counter()

    def one(t, src, key):                 # the record that holds the source's key now (a club joined to another since)
        r = G.c.execute("SELECT tifo_id FROM xref WHERE type=? AND source=? AND source_id=?", (t, src, key)).fetchone()
        return r[0] if r else reg.get(t, src, key)

    for comp, seasons in data.items():
        src, key = comp.split("|", 1)
        cid = one("competition", src, key)
        if cid is None:
            n["no_competition"] += len(seasons)
            continue
        for season, club in seasons.items():
            tid = one("team", src, club)
            eds = [e for e, in G.c.execute("SELECT eid FROM edition WHERE cid=? AND season=?", (cid, season))]
            if tid is None or len(eds) != 1:
                n["no_club" if tid is None else "no_edition"] += 1
                continue
            if not G.c.execute("SELECT 1 FROM match WHERE eid=? AND ? IN (home, away) LIMIT 1", (eds[0], tid)).fetchone():
                n["not_in_its_games"] += 1
                continue
            if G.c.execute("SELECT 1 FROM honour WHERE eid=? AND kind='champion' AND rank=1", (eds[0],)).fetchone():
                n["already"] += 1
                continue
            G.c.execute("INSERT OR IGNORE INTO honour(eid, kind, rank, tid, src) VALUES(?,?,?,?,?)", (eds[0], "champion", 1, tid, SRC))
            n["champions"] += 1
    return dict(n)
