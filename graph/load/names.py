"""Arabic names: the house spellings (teams_ar.yaml), names/*_ar.json (Wikidata, Arabic Wikipedia, then generated) and
FotMob's Arabic map for teams. Run after the FotMob loaders: it fills name_ar, never a name."""
import os


def load(G, reg, S):
    n = {"team": 0, "player": 0, "coach": 0, "referee": 0, "wikidata": 0}
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
