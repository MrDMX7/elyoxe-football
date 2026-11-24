"""FotMob player and coach profiles (db/.cache/fm/p/, ~65k): bio and career spells. A coach's profile makes a coach row;
FotMob gives no club tenure dates for coaches (phase 5 adds them)."""
import os

INFO = {"Height": "height", "Preferred foot": "foot", "Country": "nationality"}


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def day(v):
    """A career date: FotMob writes «2008-07-01T00:00:00», a bare year (2005) or epoch milliseconds."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        if 1800 <= v <= 2100:
            return str(int(v))
        from datetime import datetime, timezone
        return datetime.fromtimestamp(v / 1000, timezone.utc).strftime("%Y-%m-%d")
    return str(v)[:10] or None


def bio(d):
    row = {"name": d.get("name"), "born": ((d.get("birthDate") or {}).get("utcTime") or "")[:10] or None}
    if row["born"] == "0001-01-01":
        row["born"] = None
    for it in d.get("playerInformation") or []:
        k, v = INFO.get(it.get("title")), it.get("value") or {}
        if k == "height":
            row[k] = v.get("numberValue")
        elif k == "foot":
            row[k] = v.get("key")
        elif k == "nationality":
            row[k] = it.get("countryCode") or v.get("fallback")
    pos = [p for p in (d.get("positionDescription") or {}).get("positions") or [] if p.get("isMainPosition")]
    row["position"] = ((pos[0].get("strPos") or {}).get("label")) if pos else None
    return row


def load(G, reg, S):
    base = os.path.join(S.db, "fm", "p")
    files = sorted((f for f in os.listdir(base) if f.split(".")[0].isdigit()), key=lambda f: int(f.split(".")[0])) if os.path.isdir(base) else []
    n = coaches = spells = 0
    for f in files:
        d = S.read(os.path.join(base, f))
        if not d or not d.get("id"):
            continue
        b = bio(d)
        if d.get("isCoach"):
            kid = reg.mint("coach", "fotmob", d["id"])
            G.put("coach", {"kid": kid, "name": b["name"], "born": b["born"], "nationality": b.get("nationality"),
                            "pid": reg.get("player", "fotmob", d["id"])}, "fotmob")
            G.xref("coach", kid, "fotmob", d["id"], "fotmob-native")
            coaches += 1
            continue
        pid = reg.mint("player", "fotmob", d["id"])
        G.put("player", {"pid": pid, **b}, "fotmob")
        G.xref("player", pid, "fotmob", d["id"], "fotmob-native")
        n += 1
        for kind, entries in ((d.get("careerHistory") or {}).get("careerItems") or {}).items():
            for e in entries.get("teamEntries") or []:
                if (_int(e.get("teamId")) or 0) <= 0:           # -1: a club FotMob has no page of (40,121 spells stood under one record)
                    continue
                tid = reg.mint("team", "fotmob", e["teamId"])
                G.put("team", {"tid": tid, "name": e.get("team"), "kind": "national" if kind == "national team" else None}, "fotmob")
                G.xref("team", tid, "fotmob", e["teamId"], "fotmob-native")
                G.many("spell", [{"pid": pid, "tid": tid, "start": day(e.get("startDate")), "end": day(e.get("endDate")),
                                  "apps": _int(e.get("appearances")), "goals": _int(e.get("goals")), "assists": _int(e.get("assists")),
                                  "loan": 1 if "loan" in str(e.get("transferType") or "").lower() else 0,
                                  "national": 1 if kind == "national team" else 0, "youth": 1 if kind == "youth" else 0}], "fotmob")
                spells += 1
    return {"players": n, "coaches": coaches, "spells": spells}
