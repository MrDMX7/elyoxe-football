"""The Arabic names of the old leagues' clubs with no Transfermarkt id (23 Nov 2026: 11,067 — Bristol Rovers, Hearts,
Ferencváros, Tigres UANL — named only in Latin letters on the old clubs' pages, the head-to-heads and the seasons).

    python -m names.clubs_k --db <graph tifo.db>

Gemini with names/tm_clubs.py's club prompt and each club's country, the most played first. Out: names/clubs_k_ar.json
{t<Tifo id>: {latin, ar, source}}, saved after every batch; graph/load/comp_names.py fills name_ar from it by Tifo id."""
import argparse, json, os, re, sqlite3, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "clubs_k_ar.json")
ARABIC = re.compile("[%s-%s]" % (chr(0x600), chr(0x6FF)))


def pool(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    tm = {t for (t,) in c.execute("SELECT tifo_id FROM xref WHERE type='team' AND source IN ('tm', 'fotmob')")}
    games = {}
    for side in ("home", "away"):
        for t, n in c.execute(f"SELECT {side}, count(*) FROM match GROUP BY {side}"):
            games[t] = games.get(t, 0) + n
    out = {}
    for tid, name, country, kind in c.execute("SELECT tid, name, country, kind FROM team WHERE (name_ar IS NULL OR name_ar='') AND name IS NOT NULL"):
        if tid in tm or not games.get(tid):
            continue
        out[f"t{tid}"] = {"name": re.sub(r"\s*\([A-Za-z .'-]+\)$", "", name), "country": country, "games": games[tid], "national": kind == "national"}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--batch", type=int, default=60)
    a = ap.parse_args(argv)
    sys.path.insert(0, os.path.dirname(HERE))
    from names import build_names as B
    from names.tm_clubs import PROMPT
    out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}

    def save():
        tmp = OUT + ".tmp"
        for t in range(6):
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(out, f, ensure_ascii=False, indent=0)
                os.replace(tmp, OUT)
                return
            except OSError:
                time.sleep(2 * (t + 1))
    P = pool(a.db)
    todo = sorted((k for k in P if k not in out), key=lambda k: -P[k]["games"])
    print(f"{len(P)} clubs with no Arabic name and no Transfermarkt id; {len(todo)} to do", flush=True)
    key = B.gemini_key()
    if not key:
        print("no Gemini key")
        return 1
    for i in range(0, len(todo), a.batch):
        chunk = todo[i:i + a.batch]
        ids = {str(j): k for j, k in enumerate(chunk)}
        text = PROMPT + "\n\nid\tname\tcountry\n" + "\n".join(f"{j}\t{P[k]['name']}\t{P[k]['country'] or 'unknown'}" for j, k in ids.items())
        got = B.gemini_call(key, text, len(chunk))
        for j, k in ids.items():
            ar = (got.get(j) or "").strip()
            if ar and ARABIC.search(ar) and not re.search(r"[A-Za-z]", ar):
                out[k] = {"latin": P[k]["name"], "ar": ar, "source": "generated"}
        save()
        print(f"  {min(i + a.batch, len(todo))}/{len(todo)}", flush=True)
        time.sleep(0.5)
    print(f"done: {len(out)} clubs named")
    return 0


if __name__ == "__main__":
    sys.exit(main())
