"""Arabic names for the clubs only the old sources know (RSSSF, 365Scores, Wikipedia: no FotMob id, so graph/load/names.py
cannot reach them): teams_ar.yaml `historic`, by the Latin name as the source spells it, and the old competitions'
names from `historic_competitions`. Runs after every source; fills
name_ar only where it is empty."""
import os
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def historic():
    return (yaml.safe_load(open(os.path.join(ROOT, "teams_ar.yaml"), encoding="utf-8")) or {}).get("historic") or {}


def historic_competitions():
    return (yaml.safe_load(open(os.path.join(ROOT, "teams_ar.yaml"), encoding="utf-8")) or {}).get("historic_competitions") or {}


def renames():
    return (yaml.safe_load(open(os.path.join(ROOT, "teams_ar.yaml"), encoding="utf-8")) or {}).get("rename") or {}


def load(G, reg, S, names=None, comps=None, rename=None):
    names = historic() if names is None else names
    comps = historic_competitions() if comps is None else comps
    rename = renames() if rename is None else rename
    n, c = 0, 0
    for latin, ar in sorted(rename.items()):          # forced: another source named one of our old clubs wrongly («الشباب العربي»)
        n += G.c.execute("UPDATE team SET name_ar=? WHERE name=?", (ar, latin)).rowcount
    for latin, ar in sorted(names.items()):
        n += G.c.execute("UPDATE team SET name_ar=? WHERE name=? AND (name_ar IS NULL OR name_ar='')", (ar, latin)).rowcount
    for latin, ar in sorted(comps.items()):
        c += G.c.execute("UPDATE competition SET name_ar=? WHERE name=? AND (name_ar IS NULL OR name_ar='')", (ar, latin)).rowcount
    p = 0                                                 # the old players FotMob does not know (names/people_ar.json, k<Tifo id>)
    for k, v in sorted((S.read(os.path.join(S.names, "people_ar.json")) or {}).items()):
        if str(k).startswith("k") and str(k)[1:].isdigit() and v.get("ar"):
            p += G.c.execute("UPDATE player SET name_ar=? WHERE pid=? AND (name_ar IS NULL OR name_ar='')", (v["ar"], int(k[1:]))).rowcount
    return {"teams": n, "competitions": c, "players": p}
