"""FotMob helpers for the graph, offline: the season label of each match (db/matches.py's own cache of FotMob's season
pages), the competitions' names, and ISO dates."""
import os, re
from graph.src import Sources

STEM = lambda lab: re.sub(r"[^0-9A-Za-z]+", "-", str(lab))


def _label(s):
    m = re.match(r"^\s*(\d{4}(?:/\d{4})?)", str(s or ""))
    return m.group(1) if m else (str(s) if s else None)


def iso(s):
    if not s:
        return None
    s = str(s)
    return s[:19] + "Z" if len(s) >= 19 and "T" in s else s[:10]


def season_map(S: Sources):
    """({match id: season label}, {calendar-year competitions}) from db/.cache/fm/seasons/<comp>/."""
    base = os.path.join(S.db, "fm", "seasons")
    out, calendar = {}, set()
    for cdir in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if not cdir.isdigit():
            continue
        labels = S.read(os.path.join(base, cdir, "_seasons.json")) or []
        if labels and sum(1 for x in labels if "/" not in str(x)) * 2 >= len(labels):
            calendar.add(int(cdir))
        by_stem = {STEM(lab): _label(lab) for lab in labels}
        for f in sorted(os.listdir(os.path.join(base, cdir))):
            stem = f[:-5]
            if f == "_seasons.json" or not f.endswith(".json"):
                continue
            lab = by_stem.get(stem) or (stem.replace("-", "/") if re.fullmatch(r"\d{4}-\d{4}", stem) else stem)
            for i in S.read(os.path.join(base, cdir, f)) or []:
                out.setdefault(int(i), lab)
    return out, calendar


def season_of(mid, date, comp, labels, calendar):
    """FotMob's label when we hold it, else the calendar year or the July-June season (db/matches.py's rule)."""
    lab = labels.get(mid)
    if lab:
        return lab
    y, mo = int(date[:4]), int(date[5:7])
    if comp in calendar:
        return str(y)
    return f"{y}/{y + 1}" if mo >= 7 else f"{y - 1}/{y}"


def comp_info(S: Sources):
    """{FotMob competition id: {name, name_ar, kind, scope, country}}: FotMob's league list, its Arabic map, and
    competitions.yaml (house names, kind, scope) over both."""
    out = {}
    al = S.read(os.path.join(S.db, "fm_allleagues.json")) or {}
    for grp in (al.get("international") or []) + (al.get("countries") or []):
        for lg in grp.get("leagues") or []:
            out[int(lg["id"])] = {"name": lg.get("name"), "name_ar": None, "kind": None, "scope": None, "country": grp.get("ccode")}
    ar = S.read(os.path.join(S.db, "fm_ar.json")) or {}
    lm, tt = ar.get("LeagueMapping") or {}, ar.get("TournamentTemplates") or {}
    for cid, d in out.items():
        d["name_ar"] = tt.get(str(lm.get(str(cid), cid)))
    try:
        import config
        for c in config.competitions():
            d = out.setdefault(int(c["id"]), {"name": c.get("name"), "name_ar": None, "kind": None, "scope": None, "country": None})
            d.update({k: v for k, v in (("name_ar", c.get("name_ar")), ("kind", c.get("kind")), ("scope", c.get("scope"))) if v})
    except Exception as e:
        print(f"competitions.yaml not read: {e}", flush=True)
    return out
