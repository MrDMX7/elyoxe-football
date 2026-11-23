"""The Arabic names of the competitions known only by a code or a slug (Transfermarkt's «TR1», «SC1», schochastics' «hungary»,
«ddr», «ireland-republic»: 589 holding a million games on 22 Nov 2026).

    python -m names.comps --db <graph tifo.db>

Each one goes to Gemini with what tells it apart: its clubs with the most games and its years («TR1»: Galatasaray,
Fenerbahçe, 1995-2024 -> «الدوري التركي الممتاز»). Out: names/comps_ar.json {name: {ar, source, clubs, years}}, saved after
every batch; graph/load/comp_names.py fills name_ar from it."""
import argparse, json, os, re, sqlite3, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "comps_ar.json")
ARABIC = re.compile("[%s-%s]" % (chr(0x600), chr(0x6FF)))
PROMPT = """You are an Arabic sports editor (beIN Sports, Kooora, Al Ittihad). Each line is a football competition known in our
database only by a code or a slug, with the clubs that played most in it and its years. Write its name in Arabic exactly as Arab
sports media write it.
- A country's top league: "الدوري <adjective>" as media say it ("TR1" -> "الدوري التركي الممتاز", "hungary" -> "الدوري المجري",
  "SC1" -> "الدوري الاسكتلندي الممتاز", "ddr" -> "الدوري الألماني الشرقي", "ireland-republic" -> "الدوري الأيرلندي").
- A second tier: "دوري الدرجة الثانية <adjective>"; a cup: "كأس <country>"; a continental competition by its Arabic media name.
- Arabic script only, no diacritics, no Latin letters. If the clubs show it is a youth or women's competition, say so.
Return one item per input, with the same id."""


def pool(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = c.execute("""SELECT c.cid, c.name, count(m.mid), min(substr(m.date,1,4)), max(substr(m.date,1,4)) FROM competition c
                        JOIN edition e ON e.cid=c.cid JOIN match m ON m.eid=e.eid
                        WHERE (c.name_ar IS NULL OR c.name_ar='') AND c.name NOT LIKE '%(aside)' GROUP BY c.cid ORDER BY 3 DESC""").fetchall()
    out = {}
    for cid, name, n, y0, y1 in rows:
        if name in out:
            continue
        clubs = [t for (t,) in c.execute("""SELECT coalesce(t.name, t.name_ar) FROM match m JOIN edition e ON e.eid=m.eid JOIN team t ON t.tid=m.home
                                            WHERE e.cid=? GROUP BY m.home ORDER BY count(*) DESC LIMIT 4""", (cid,))]
        out[name] = {"clubs": [x for x in clubs if x], "years": f"{y0}-{y1}", "games": n}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--batch", type=int, default=40)
    a = ap.parse_args(argv)
    sys.path.insert(0, os.path.dirname(HERE))
    from names import build_names as B
    out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    save = lambda: json.dump(dict(sorted(out.items())), open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    P = pool(a.db)
    todo = [k for k in P if k not in out]
    print(f"{len(P)} competitions with no Arabic name, {len(todo)} to do", flush=True)
    key = B.gemini_key()
    if not key:
        print("no Gemini key")
        return 1
    for i in range(0, len(todo), a.batch):
        chunk = todo[i:i + a.batch]
        ids = {str(j): k for j, k in enumerate(chunk)}
        text = PROMPT + "\n\nid\tcompetition\tclubs\tyears\n" + "\n".join(f"{j}\t{k}\t{', '.join(P[k]['clubs'])}\t{P[k]['years']}" for j, k in ids.items())
        got = B.gemini_call(key, text, len(chunk))
        for j, k in ids.items():
            ar = (got.get(j) or "").strip()
            if ar and ARABIC.search(ar) and not re.search(r"[A-Za-z]", ar):
                out[k] = {"ar": ar, "source": "generated", "clubs": P[k]["clubs"][:3], "years": P[k]["years"]}
        save()
        print(f"  {min(i + a.batch, len(todo))}/{len(todo)}", flush=True)
        time.sleep(1)
    print(f"done: {len(out)} competitions named")
    return 0


if __name__ == "__main__":
    sys.exit(main())
