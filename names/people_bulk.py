"""Arabic names for the archive's men, in bulk (23 Nov 2026: half the names on the 107,000 profiles read in Latin letters; the
weekly people job, names/build_names.py --kind people, reads the legends and the Arab leagues' old matches only, and its
one-search-per-name Wikidata pass would take a day for 90,000).

    python -m names.people_bulk --db <graph tifo.db> [--limit N]

1. the pool: the graph's men with a record (a career line, a game, an honour, a move, caps) and no Arabic name, the most seen
   first (a man of 300 games before one of 3);
2. Wikidata: the Arabic label of the men the graph ties to an item, 400 items a query (QLever); a bot's spelling
   (پ/چ/ڤ/گ) refused, as in build_names;
3. the rest by Gemini with build_names' player prompt (an Arab's real name, the others as Arab media transliterate them), his
   nationality, club and birth year as hints.

Out: names/people_ar.json (k<Tifo id>, the file the graph's old_names loader reads), saved after every batch."""
import argparse, json, os, re, sqlite3, sys, time, urllib.parse, urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "people_ar.json")
ARABIC = re.compile("[%s-%s]" % (chr(0x600), chr(0x6FF)))
BOT = re.compile("[%s]" % "".join(map(chr, (0x67E, 0x686, 0x6A4, 0x6AF))))      # پ چ ڤ گ


def labels(rows):
    """QLever rows {p, ar} -> {qid: Arabic}, a bot's spelling or a Latin label refused"""
    out = {}
    for r in rows:
        q, ar = r["p"]["value"].rsplit("/", 1)[1], r["ar"]["value"].strip()
        if ARABIC.search(ar) and not BOT.search(ar) and not re.search(r"[A-Za-z]", ar):
            out.setdefault(q, ar)
    return out


def order(pool):
    return sorted(pool, key=lambda k: (-pool[k]["weight"], k))


def pool_of(db, have):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    q = lambda s, p=(): c.execute(s, p).fetchall()
    w = {}
    for sql in ("SELECT pid, count(*) FROM player_season GROUP BY pid", "SELECT pid, count(*) FROM appearance GROUP BY pid",
                "SELECT pid, 10 * count(*) FROM honour WHERE pid IS NOT NULL GROUP BY pid", "SELECT pid, 3 * count(*) FROM intl_record GROUP BY pid"):
        try:
            for pid, n in q(sql):
                if pid is not None:
                    w[pid] = w.get(pid, 0) + n
        except sqlite3.OperationalError:
            pass
    fm = {t for (t,) in q("SELECT tifo_id FROM xref WHERE type='player' AND source='fotmob'")}
    qid = {t: s for t, s in q("SELECT tifo_id, source_id FROM xref WHERE type='player' AND source='wikidata'") if str(s).startswith("Q")}
    club = {}
    for pid, name in q("""SELECT ps.pid, coalesce(t.name, t.name_ar) FROM player_season ps JOIN team t ON t.tid=ps.tid GROUP BY ps.pid, ps.tid
                          ORDER BY ps.pid, count(*) DESC"""):
        club.setdefault(pid, name)
    out = {}
    for pid, name, ar, born, nat in q("SELECT pid, name, name_ar, born, nationality FROM player"):
        k = f"k{pid}"
        if ar or not name or pid in fm or pid not in w or k in have:
            continue
        out[k] = {"name": name, "weight": w[pid], "qid": qid.get(pid), "nat": nat, "club": club.get(pid), "born": (born or "")[:4]}
    return out


def wikidata(qids):
    out = {}
    qids = sorted(set(qids))
    for i in range(0, len(qids), 400):
        q = ("PREFIX wd: <http://www.wikidata.org/entity/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
             "SELECT ?p ?ar WHERE { VALUES ?p { %s } ?p rdfs:label ?ar FILTER(LANG(?ar)=\"ar\") }" % " ".join("wd:" + x for x in qids[i:i + 400]))
        u = "https://qlever.cs.uni-freiburg.de/api/wikidata?" + urllib.parse.urlencode({"query": q})
        for t in range(3):
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "elyoxe-tifo/0.1 (hello@elyoxe.com)", "Accept": "application/sparql-results+json"})
                out.update(labels(json.loads(urllib.request.urlopen(req, timeout=120).read())["results"]["bindings"]))
                break
            except Exception:
                time.sleep(5 * (t + 1))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=80)
    a = ap.parse_args(argv)
    sys.path.insert(0, os.path.dirname(HERE))
    from names import build_names as B
    out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    save = lambda: json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    today = date.today().isoformat()
    P = pool_of(a.db, out)
    todo = order(P)
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(P)} men with a record and no Arabic name; {len(todo)} this run", flush=True)
    wd = wikidata([P[k]["qid"] for k in todo if P[k]["qid"]])
    for k in todo:
        if P[k]["qid"] in wd:
            out[k] = {"latin": P[k]["name"], "ar": wd[P[k]["qid"]], "source": "wikidata", "qid": P[k]["qid"], "checked": today}
    save()
    todo = [k for k in todo if k not in out]
    print(f"{sum(1 for k in P if out.get(k, {}).get('source') == 'wikidata')} from Wikidata; {len(todo)} for Gemini", flush=True)
    key = B.gemini_key()
    if not key:
        print("no Gemini key: Wikidata only")
        return 0
    for i in range(0, len(todo), a.batch):
        chunk = todo[i:i + a.batch]
        ids = {str(j): k for j, k in enumerate(chunk)}
        hint = lambda p: "\t".join(x for x in (f"nationality={p['nat']}" if p["nat"] else "", f"club={p['club']}" if p["club"] else "",
                                               f"born={p['born']}" if p["born"] else "") if x)
        text = B.PROMPT + "\n\nid\tname\thints\n" + "\n".join(f"{j}\t{P[k]['name']}\t{hint(P[k])}" for j, k in ids.items())
        got = B.gemini_call(key, text, len(chunk))
        for j, k in ids.items():
            ar = (got.get(j) or "").strip()
            if ar and ARABIC.search(ar) and not re.search(r"[A-Za-z]", ar):
                out[k] = {"latin": P[k]["name"], "ar": ar, "source": "generated", "qid": P[k]["qid"], "checked": today}
        save()
        print(f"  {min(i + a.batch, len(todo))}/{len(todo)}", flush=True)
        time.sleep(0.5)
    print(f"done: {len(out)} men named")
    return 0


if __name__ == "__main__":
    sys.exit(main())
