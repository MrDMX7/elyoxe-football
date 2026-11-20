"""The disagreements between sources that no rule settled (graph/load/settle.py), as a list a person can read: UAE first
(our league's matches and seasons, the national team, our players), then the rest by kind.

    python -m graph.review <tifo.db> [--out docs/GRAPH-CONFLICTS-<date>.md] [--all]
"""
import argparse, os, sqlite3
from collections import defaultdict
from datetime import date


def rows(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    q = lambda s, p=(): c.execute(s, p).fetchall()
    tn = {t: (a or n) for t, n, a in q("SELECT tid, name, name_ar FROM team")}
    pn = {p: (a or n) for p, n, a in q("SELECT pid, name, name_ar FROM player")}
    kn = {k: (a or n) for k, n, a in q("SELECT kid, name, name_ar FROM coach")}
    cn = {k: (a or n) for k, n, a in q("SELECT cid, name, name_ar FROM competition")}
    ed = {e: (cn.get(c) or f"#{c}", s, c) for e, c, s in q("SELECT eid, cid, season FROM edition")}
    fm = lambda t: {a: b for a, b in q(f"SELECT tifo_id, source_id FROM xref WHERE type='{t}' AND source='fotmob'")}
    fm_t, fm_c = fm("team"), fm("competition")
    uae_league = {c for c, s in fm_c.items() if str(s) == "538"}
    uae_nat = {t for t, s in fm_t.items() if str(s) == "5789"}
    uae_clubs = {t for (t,) in q("SELECT DISTINCT m.home FROM match m JOIN edition e ON e.eid=m.eid WHERE e.cid IN (%s)" % (",".join(map(str, uae_league)) or "NULL"))}
    uae_players = {p for (p,) in q("SELECT DISTINCT pid FROM appearance WHERE tid IN (%s)" % (",".join(map(str, uae_clubs | uae_nat)) or "NULL"))}
    who = lambda field, v: (tn.get(int(v), v) if field in ("champion", "runner_up") else v) if str(v).lstrip("-").isdigit() else v
    out = []
    for typ, tid, field, kept, ksrc, other, osrc in q("SELECT type, tifo_id, field, kept, kept_src, other, other_src FROM conflict"):
        if typ == "match":
            m = q("SELECT substr(date,1,10), home, away, eid FROM match WHERE mid=?", (tid,))
            if not m:
                continue
            d, h, a, eid = m[0]
            comp = ed.get(eid, ("", "", None))
            uae = bool({h, a} & (uae_clubs | uae_nat))
            what = f"{d} {tn.get(h, h)} - {tn.get(a, a)} ({comp[0]} {comp[1]})".strip()
        elif typ == "honour":
            comp = ed.get(tid, ("", "", None))
            uae = comp[2] in uae_league
            what = f"{comp[0]} {comp[1]}"
            kept, other = who(field, kept), who(field, other)
            if field not in ("champion", "runner_up"):
                kept, other = (pn.get(int(kept), kept) if str(kept).isdigit() else kept), (pn.get(int(other), other) if str(other).isdigit() else other)
        elif typ == "player":
            uae = tid in uae_players
            what = pn.get(tid, tid)
        elif typ == "coach":
            uae, what = False, kn.get(tid, tid)
        else:
            uae, what = False, f"{typ} {tid}"
        out.append({"uae": uae, "type": typ, "field": field, "what": str(what), "kept": f"{kept} ({ksrc})", "other": f"{other} ({osrc})"})
    seen, once = set(), []                    # one disagreement found by several tables of one article is listed once
    for r in out:
        k = (r["type"], r["field"], r["what"], r["kept"], r["other"])
        if k not in seen:
            seen.add(k)
            once.append(r)
    return once


LABEL = {("match", "score"): "النتيجة", ("match", "hs"): "أهداف صاحب الأرض", ("match", "as_"): "أهداف الضيف", ("player", "born"): "تاريخ الميلاد",
         ("honour", "champion"): "البطل", ("honour", "runner_up"): "الوصيف", ("honour", "top_scorer"): "الهداف", ("honour", "best_player"): "أفضل لاعب"}


def markdown(rs, all_rest=False):
    uae = [r for r in rs if r["uae"]]
    rest = defaultdict(list)
    for r in rs:
        if not r["uae"]:
            rest[(r["type"], r["field"])].append(r)
    lines = [f"# خلافات المصادر اللي تبي قرار ({date.today()})", "",
             f"بعد القواعد (ركلات الترجيح، الأرض والضيف المقلوبين، تاريخ الميلاد بالسنة بس) بقى {len(rs)} خلاف. "
             "القيمة الأولى هي اللي تطلع في الموقع الحين، والثانية من المصدر الثاني.", "",
             f"## الإمارات ({len(uae)})", "", "| النوع | وين | المعروض | المصدر الثاني |", "|---|---|---|---|"]
    lines += [f"| {LABEL.get((r['type'], r['field']), r['field'])} | {r['what']} | {r['kept']} | {r['other']} |" for r in sorted(uae, key=lambda r: (r["type"], r["what"]))]
    lines += ["", "## الباقي حسب النوع", ""]
    for (t, f), l in sorted(rest.items(), key=lambda x: -len(x[1])):
        lines += [f"### {LABEL.get((t, f), f)} ({len(l)})", "", "| وين | المعروض | المصدر الثاني |", "|---|---|---|"]
        lines += [f"| {r['what']} | {r['kept']} | {r['other']} |" for r in (l if all_rest else l[:15])]
        lines += [""] + ([f"و{len(l) - 15} غيرها في قاعدة البيانات (جدول conflict)."] if len(l) > 15 and not all_rest else []) + [""]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", f"GRAPH-CONFLICTS-{date.today()}.md"))
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    rs = rows(a.db)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(markdown(rs, a.all))
    print(f"{len(rs)} conflicts, {sum(r['uae'] for r in rs)} UAE -> {a.out}")


if __name__ == "__main__":
    main()
