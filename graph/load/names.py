"""Arabic names: the house spellings (teams_ar.yaml), names/*_ar.json (Wikidata, Arabic Wikipedia, then generated) and
FotMob's Arabic map for teams. Run after the FotMob loaders: it fills name_ar, never a name."""
import json, os
from datetime import date
from graph.load.people import fold

YEAR_DAYS = 366


def plausible(fm_name, fm_born, wd_name, wd_born):
    """A FotMob player and a Wikidata item can be one man: refused when both birth dates are known and more than a year
    apart (Mohamed Hamed 1994 / Mohamed Salah 1992), or, with no two dates, when the names share no surname (Amer Khalil /
    Amer Deeb). A side that says nothing never refuses."""
    if fm_born and wd_born:
        try:
            a, b = date.fromisoformat(fm_born[:10]), date.fromisoformat(wd_born[:10])
        except ValueError:
            a = b = None
        if a and b:
            if (a.month, a.day) == (b.month, b.day):          # a slipped year on one side (Marchesin 1988 / 1945)
                return True
            if (b.month, b.day) == (1, 1) or (a.month, a.day) == (1, 1):   # 1 January: only the year is known
                return abs(a.year - b.year) <= 1
            return abs((a - b).days) <= YEAR_DAYS
    a, b = fold(fm_name).split(), fold(wd_name).split()
    if not a or not b:
        return True
    return a[-1] in "".join(b) or b[-1] in "".join(a)        # «Aldawsari» is «Al-Dawsari»


def _items_by_qid(S):
    """{qid: (English label, born)} from the awards stage's Wikidata cache (graph/.cache/awards/items.json)."""
    p = os.path.join(S.root, "graph", ".cache", "awards", "items.json")
    if not os.path.exists(p) and getattr(S, "s3", None):
        try:
            from graph import awards_fetch as AF
            AF.restore(S, os.path.dirname(p))
        except Exception as e:
            print(f"awards cache not restored: {e}", flush=True)
    try:
        with open(p, encoding="utf-8") as f:
            items = json.load(f)
    except (OSError, ValueError):
        return {}
    return {v["qid"]: (v.get("en"), v.get("born")) for v in items.values() if isinstance(v, dict) and v.get("qid") and v.get("human")}


def load(G, reg, S):
    n = {"team": 0, "player": 0, "coach": 0, "referee": 0, "wikidata": 0, "wikidata_refused": 0}
    wd = _items_by_qid(S)
    born = dict(G.c.execute("SELECT pid, born FROM player WHERE born IS NOT NULL").fetchall())
    teams = {}
    try:
        import config
        for k, v in (config.team_overrides() or {}).items():
            if isinstance(v, dict) and v.get("name_ar"):
                teams.setdefault(str(k), v["name_ar"])
            elif isinstance(v, str):
                teams.setdefault(str(k), v)
    except Exception as e:
        print(f"teams_ar.yaml not read: {e}", flush=True)
    for k, v in (S.read(os.path.join(S.names, "clubs_ar.json")) or {}).items():
        if v.get("ar"):
            teams.setdefault(str(k), v["ar"])
    for k, v in ((S.read(os.path.join(S.db, "fm_ar.json")) or {}).get("Participants") or {}).items():
        teams.setdefault(str(k), v)
    for k, ar in sorted(teams.items()):
        tid = reg.get("team", "fotmob", int(k)) if k.isdigit() else None
        if tid:
            G.put("team", {"tid": tid, "name_ar": ar}, "names")
            n["team"] += 1
    for t, f in (("player", "players_ar.json"), ("coach", "coaches_ar.json")):
        for k, v in sorted((S.read(os.path.join(S.names, f)) or {}).items()):
            i = reg.get(t, "fotmob", int(k)) if k.isdigit() else None
            if i and v.get("ar"):
                G.put(t, {{"player": "pid", "coach": "kid"}[t]: i, "name_ar": v["ar"]}, "names")
                n[t] += 1
            if i and v.get("qid") and t == "player" and v.get("source") != "manual" and v["qid"] in wd \
                    and not plausible(v.get("latin"), born.get(i), *wd[v["qid"]]):
                n["wikidata_refused"] += 1                # another man's item (an old match the names job kept)
                if reg.get(t, "wikidata", v["qid"]) == reg.resolve(t, i):
                    reg.unlink(t, "wikidata", v["qid"])   # tied by an earlier build: the registry would keep it
                continue
            if i and v.get("qid"):
                if reg.alias(t, "wikidata", v["qid"], i):
                    G.xref(t, i, "wikidata", v["qid"], "names-" + str(v.get("source")))
                    n["wikidata"] += 1
                elif v.get("source") == "manual":        # checked by hand: the item's other record is this player (Ali Mabkhout)
                    other = reg.get(t, "wikidata", v["qid"])
                    keep = reg.merge(t, other, i)
                    reg.run_merges.append((t, max(other, i), keep))
                    n["manual_merged"] = n.get("manual_merged", 0) + 1
    for k, v in sorted((S.read(os.path.join(S.names, "referees_ar.json")) or {}).items()):
        rid = reg.get("referee", "fotmob-name", v.get("latin")) if v.get("latin") else None
        if rid and v.get("ar"):
            G.put("referee", {"rid": rid, "name_ar": v["ar"]}, "names")
            reg.alias("referee", "fotmob", k, rid)
            G.xref("referee", rid, "fotmob", k, "same-name-same-source")
            n["referee"] += 1
    return n
