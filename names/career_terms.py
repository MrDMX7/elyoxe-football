"""Arabic for what the profiles' career and injury tables still showed in Latin letters (23 Nov 2026: 507k career lines whose
competition is in none of our names — «FA Cup», «Italy Cup», «Super League» of several countries — and 149k injuries,
«Muscle injury»).

    python -m names.career_terms --db <graph tifo.db>

A competition goes to Gemini with its clubs' country (one name, several countries: «Super League|Greece», «Super League|
Switzerland»); an injury once. Out: names/career_terms_ar.json {comps: {"<name>|<country>": Arabic}, injuries: {kind:
Arabic}}, saved after every batch; graph/archive_export.persons reads it."""
import argparse, json, os, re, sqlite3, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "career_terms_ar.json")
ARABIC = re.compile("[%s-%s]" % (chr(0x600), chr(0x6FF)))
COMP_PROMPT = """You are an Arabic sports editor (beIN Sports, Kooora). Each line is a football competition as Transfermarkt names it, with
the country of the clubs that played in it. Write its name in Arabic exactly as Arab sports media write it ("FA Cup|England"
-> "كأس الاتحاد الإنجليزي", "Italy Cup|Italy" -> "كأس إيطاليا", "Super League|Greece" -> "الدوري اليوناني الممتاز",
"Super League|Switzerland" -> "الدوري السويسري الممتاز", "U19 Bundesliga|Germany" -> "الدوري الألماني تحت 19"). Youth
and reserve competitions say so. Arabic script only, no Latin letters. Return one item per input, with the same id."""
INJ_PROMPT = """You are an Arabic sports editor. Each line is a football injury or absence as Transfermarkt names it. Write it in Arabic as
Arab sports media write it ("Muscle injury" -> "إصابة عضلية", "Cruciate ligament tear" -> "قطع في الرباط الصليبي",
"Ill" -> "مرض", "unknown injury" -> "إصابة"). Short, Arabic script only. Return one item per input, with the same id."""


def pools(db, have):
    sys.path.insert(0, os.path.dirname(HERE))
    from graph import archive_export as X
    G = X.open_graph(db)
    cn = {c: (a or n) for c, n, a in G.c.execute("SELECT cid, name, name_ar FROM competition")}
    f = X.career_names(G, cn)
    country = {t: c for t, c in G.c.execute("SELECT tid, country FROM team")}
    comps = {}
    for comp, cid, tid, k in G.c.execute("SELECT comp, cid, tid, count(*) FROM player_season GROUP BY comp, cid, tid"):
        own = cn.get(cid)
        if not comp or any(x and ARABIC.search(x) for x in (own, f(comp, tid))):
            continue
        key = f"{comp}|{country.get(tid) or ''}"
        if key not in have["comps"]:
            comps[key] = comps.get(key, 0) + k
    inj = {k: n for k, n in G.c.execute("SELECT kind, count(*) FROM injury WHERE kind IS NOT NULL GROUP BY kind") if k not in have["injuries"]}
    return comps, inj


def run(key, items, prompt, batch, out, save, B):
    todo = sorted(items, key=lambda k: -items[k])
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        ids = {str(j): k for j, k in enumerate(chunk)}
        got = B.gemini_call(key, prompt + "\n\nid\tname\n" + "\n".join(f"{j}\t{k}" for j, k in ids.items()), len(chunk))
        for j, k in ids.items():
            ar = (got.get(j) or "").strip()
            if ar and ARABIC.search(ar) and not re.search(r"[A-Za-z]", ar):
                out[k] = ar
        save()
        print(f"  {min(i + batch, len(todo))}/{len(todo)}", flush=True)
        time.sleep(0.5)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--batch", type=int, default=60)
    a = ap.parse_args(argv)
    sys.path.insert(0, os.path.dirname(HERE))
    from names import build_names as B
    d = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    d.setdefault("comps", {}); d.setdefault("injuries", {})

    def save():
        tmp = OUT + ".tmp"
        for t in range(6):
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(d, f, ensure_ascii=False, indent=0)
                os.replace(tmp, OUT)
                return
            except OSError:
                time.sleep(2 * (t + 1))
    comps, inj = pools(a.db, d)
    print(f"{len(comps)} competitions (name|country), {len(inj)} injuries to name", flush=True)
    key = B.gemini_key()
    if not key:
        print("no Gemini key")
        return 1
    run(key, inj, INJ_PROMPT, a.batch, d["injuries"], save, B)
    run(key, comps, COMP_PROMPT, a.batch, d["comps"], save, B)
    print(f"done: {len(d['comps'])} competitions, {len(d['injuries'])} injuries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
