"""What a person decided from official sources (graph/corrections.yaml) beats every source, in every build. Runs after
graph/load/settle.py: an honour's winners are replaced, a match's score or a player's birth date set, and the disagreements
these decide are closed, including those where the value shown was right («keep»)."""
import os
import yaml

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read():
    return yaml.safe_load(open(os.path.join(HERE, "corrections.yaml"), encoding="utf-8")) or {}


def _edition(G, reg, comp, season):
    cid = reg.get("competition", "fotmob", int(comp))
    r = G.c.execute("SELECT eid FROM edition WHERE cid=? AND season=?", (cid, season)).fetchone() if cid else None
    return r[0] if r else None


def _player(G, reg, p, eid, kind):
    if p.get("fotmob"):
        return reg.get("player", "fotmob", int(p["fotmob"]))
    name = p["name"]
    hit = G.c.execute("""SELECT pid FROM player WHERE lower(name)=lower(?) ORDER BY
                         (pid IN (SELECT pid FROM honour WHERE eid=? AND kind=?)) DESC, pid LIMIT 1""", (name, eid, kind)).fetchone()
    if hit:
        return hit[0]
    pid = reg.mint("player", "correction", name)
    G.put("player", {"pid": pid, "name": name}, "wikidata")
    return pid


def load(G, reg, S, conf=None):
    conf = read() if conf is None else conf
    n = {"honours": 0, "kept": 0, "players": 0}
    for h in conf.get("honours") or []:
        eid = _edition(G, reg, h["comp"], h["season"])
        if eid is None:
            continue
        pids = [p for p in (_player(G, reg, x, eid, h["kind"]) for x in h["players"]) if p]
        G.c.execute("DELETE FROM honour WHERE eid=? AND kind=? AND rank=1", (eid, h["kind"]))
        G.c.executemany("INSERT OR IGNORE INTO honour(eid, kind, rank, pid, value, src) VALUES(?, ?, 1, ?, ?, 'correction')",
                        [(eid, h["kind"], p, h.get("value")) for p in pids])
        G.c.execute("DELETE FROM conflict WHERE type='honour' AND tifo_id=? AND field=?", (eid, h["kind"]))
        n["honours"] += 1
    for k in conf.get("keep") or []:
        eid = _edition(G, reg, k["comp"], k["season"])
        if eid is not None:
            G.c.execute("DELETE FROM conflict WHERE type='honour' AND tifo_id=? AND field=?", (eid, k["kind"]))
            n["kept"] += 1
    for m in conf.get("matches") or []:
        h, a = reg.get("team", "fotmob", int(m["home"])), reg.get("team", "fotmob", int(m["away"]))
        r = G.c.execute("SELECT mid FROM match WHERE home=? AND away=? AND substr(date,1,10)=?", (h, a, m["date"])).fetchone()
        if r:
            G.c.execute("UPDATE match SET hs=?, as_=? WHERE mid=?", (m["score"][0], m["score"][1], r[0]))
            G.c.execute("DELETE FROM conflict WHERE type='match' AND tifo_id=?", (r[0],))
            n["matches"] = n.get("matches", 0) + 1
    for p in conf.get("players") or []:
        pid = reg.get("player", "fotmob", int(p["fotmob"]))
        if pid is None:
            continue
        if p.get("born"):
            G.c.execute("UPDATE player SET born=? WHERE pid=?", (p["born"], pid))
            G.c.execute("DELETE FROM conflict WHERE type='player' AND tifo_id=? AND field='born'", (pid,))
        n["players"] += 1
    return n
