"""Every club's full history (owner 2026-09-30: «الداتا بيس لكل الاندية العالمية… كلها»), stage 1: results since 1888 (England: every division and both cups).

    python -m db.history [--upload] [--club 8456]

Sources:
  schochastics/football-data  games.parquet: 1.3M league and continental matches, 207 top divisions, 1888 -> 2025-09
                              (ODC-By). Teams are keyed by strings like «Al Hilal FC (Saudi Arabia)».
  our FotMob archive          v1/archive/all/<season>.json: the covered competitions since 2010, with FotMob ids; it
                              links the two (below) and carries history past the dataset's last date.

Linking, never by name: a FotMob match and a dataset match on the same date (+-1 day, time zones) with the same score
vote for «FotMob home id = dataset home key» and the same for away. A club is linked when one key has at least 5 votes,
70% of its votes, and that key's own best FotMob id is the same club (both directions agree).

Out (public): v1/history/club/<fotmob id>.json (record, per competition, per decade, every opponent, biggest wins and
defeats, first match) and v1/history/club/<id>/matches.json (every match), v1/history/index.json (who has a history).
Local: db/.cache/ (the parquet, crosswalk.json).
"""
import argparse, gzip, json, os, sys, time, urllib.request
from collections import defaultdict
from datetime import date

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from store import Store, S3Backend  # noqa: E402

CACHE = os.path.join(HERE, ".cache")
PARQUET = os.path.join(CACHE, "games.parquet")
SRC = "https://raw.githubusercontent.com/schochastics/football-data/master/data/results/games.parquet"
BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
COMPS_AR = {}


def fetch():
    os.makedirs(CACHE, exist_ok=True)
    if not os.path.exists(PARQUET) or time.time() - os.path.getmtime(PARQUET) > 6 * 86400:
        raw = urllib.request.urlopen(urllib.request.Request(SRC, headers={"User-Agent": "elyoxe-tifo/0.1"}), timeout=300).read()
        open(PARQUET + ".tmp", "wb").write(raw); os.replace(PARQUET + ".tmp", PARQUET)
        print("dataset downloaded", len(raw) // 1024 // 1024, "MB")


def fotmob_archive(store):
    rows, y = [], date.today().year + 1
    for a in range(2010, y):
        d = store.get_json(f"archive/all/{a}-{a + 1}.json")
        for m in (d or {}).get("matches") or []:
            if m[5] is not None and m[6] is not None:
                rows.append((m[0], m[1][:10], m[2], m[3], m[4], m[5], m[6]))
    return rows


def crosswalk(con):
    con.execute("""create or replace table votes as
      with pairs as (
        select f.h fm, g.home_ident sk from fm f join g on g.gh = f.gh and g.ga = f.ga and g.date between f.date - 1 and f.date + 1
        union all
        select f.a fm, g.away_ident sk from fm f join g on g.gh = f.gh and g.ga = f.ga and g.date between f.date - 1 and f.date + 1)
      select fm, sk, count(*) n from pairs group by 1, 2""")
    # every match also agrees by chance with dozens of others that day with the same score, so the share of votes is
    # meaningless; what separates the real pair is how far it leads the runner-up, in both directions
    rows = con.execute("""with b1 as (select fm, sk, n, row_number() over (partition by fm order by n desc) r from votes),
        s1 as (select fm, max(n) filter (where r = 2) n2 from b1 group by 1),
        b2 as (select sk, fm, n, row_number() over (partition by sk order by n desc) r from votes),
        s2 as (select sk, max(n) filter (where r = 2) n2 from b2 group by 1)
      select b1.fm, b1.sk, b1.n from b1 join s1 using (fm) join b2 on b2.sk = b1.sk and b2.r = 1 and b2.fm = b1.fm join s2 on s2.sk = b1.sk
      where b1.r = 1 and b1.n >= 5 and b1.n >= 3 * coalesce(s1.n2, 0) and b2.n >= 3 * coalesce(s2.n2, 0)""").fetchall()
    return {int(fm): sk for fm, sk, n in rows}


ENG = "https://raw.githubusercontent.com/jalapic/engsoccerdata/master/data-raw/"
ENG_COMPS = {"eng:2": "الدرجة الثانية الإنجليزية", "eng:3": "الدرجة الثالثة الإنجليزية", "eng:4": "الدرجة الرابعة الإنجليزية",
             "facup": "كأس الاتحاد الإنجليزي", "leaguecup": "كأس الرابطة الإنجليزية"}


def eng_matches():
    """England beyond the top flight, from jalapic/engsoccerdata (GPL; the owner allows every source): divisions 2-4
    since 1892, the FA Cup since 1871 and the League Cup since 1960. {folded club name: [[date, opp name, home, gf, ga, comp]]}.
    The top flight is left out: the main dataset already has it."""
    import csv, io, re, unicodedata
    fold = lambda x: re.sub(r"[^a-z0-9]+", " ", re.sub(r"\b(fc|afc)\b", " ", unicodedata.normalize("NFKD", x or "").encode("ascii", "ignore").decode().lower())).strip()
    out = defaultdict(list)
    for f, comp in (("england", None), ("facup", "facup"), ("leaguecup", "leaguecup")):
        cp = os.path.join(CACHE, f"eng_{f}.csv")
        if not os.path.exists(cp) or time.time() - os.path.getmtime(cp) > 6 * 86400:
            open(cp, "wb").write(urllib.request.urlopen(urllib.request.Request(ENG + f + ".csv", headers={"User-Agent": "elyoxe-tifo/0.1"}), timeout=300).read())
        for r in csv.DictReader(open(cp, encoding="utf-8")):
            try:
                hg, vg = int(r["hgoal"]), int(r["vgoal"])
            except (ValueError, KeyError):
                continue
            c = comp or (f"eng:{r['tier']}" if r.get("tier") and r["tier"] != "1" else None)
            if not c:
                continue
            d = r["Date"][:10]
            out[fold(r["home"])].append([d, r["visitor"], 1, hg, vg, c])
            out[fold(r["visitor"])].append([d, r["home"], 0, vg, hg, c])
    return out, fold


INTL = {"UEFA CL": "دوري أبطال أوروبا", "UEFA EL": "الدوري الأوروبي", "UEFA CONF L": "دوري المؤتمر الأوروبي", "UEFA SC": "كأس السوبر الأوروبي",
        "UEFA ITC": "كأس إنترتوتو", "Copa Lib": "كأس ليبرتادوريس", "Copa Sud": "كوبا سود أمريكانا", "Recopa": "ريكوبا", "CAF CL": "دوري أبطال أفريقيا",
        "CAF CC": "كأس الكونفدرالية الأفريقية", "CAF SC": "كأس السوبر الأفريقي", "AFC CL": "دوري أبطال آسيا", "AFC Pokal": "كأس الاتحاد الآسيوي",
        "AFC Pres. Cup": "كأس رئيس الاتحاد الآسيوي", "CONCACAF CC": "أبطال الكونكاكاف", "CONCACAF L": "دوري الكونكاكاف", "OFC CC": "أبطال أوقيانوسيا",
        "CFU CC": "أبطال الكاريبي", "Fifa Club": "كأس العالم للأندية", "ddr-intl": "كأس الكؤوس الأوروبية وكأس الإنتركونتيننتال"}


def rec():
    return {"p": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0}


def add(r, gf, ga):
    r["p"] += 1; r["gf"] += gf; r["ga"] += ga
    r["w" if gf > ga else "l" if gf < ga else "d"] += 1


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); ap.add_argument("--club", type=int)
    a = ap.parse_args(argv)
    fetch()
    store = Store(S3Backend(BUCKET))
    con = duckdb.connect()
    con.execute(f"create table g as select * from read_parquet('{PARQUET.replace(chr(92), '/')}') where gh is not null and ga is not null")
    last = con.execute("select max(date) from g").fetchone()[0]
    fmr = fotmob_archive(store)
    con.execute("create table fm (id bigint, date date, comp int, h int, a int, gh int, ga int)")
    con.executemany("insert into fm values (?, ?, ?, ?, ?, ?, ?)", fmr)
    print(f"dataset: {con.execute('select count(*) from g').fetchone()[0]} matches to {last}; FotMob archive: {len(fmr)}")
    cw = crosswalk(con)
    print(len(cw), "FotMob clubs linked to the dataset")
    json.dump({str(k): v for k, v in sorted(cw.items())}, open(os.path.join(CACHE, "crosswalk.json"), "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=0)
    key_of = {v: k for k, v in cw.items()}                                   # dataset key -> FotMob id
    teams = (store.get_json("teams.json") or {}).get("teams") or {}
    global COMPS_AR
    COMPS_AR = {c["id"]: c.get("name_ar") for c in ((store.get_json("index.json") or {}).get("competitions") or []) if c.get("id")}

    ENGM, efold = eng_matches()
    eng_sk = {efold(r[0].rsplit(" (", 1)[0]): r[0] for r in con.execute("select distinct home_ident from g where home_ident like '%(England)'").fetchall()}
    targets = [a.club] if a.club else sorted(cw)
    index = {}
    for fid in targets:
        sk = cw.get(fid)
        if not sk:
            continue
        rows = con.execute("""select date, home_ident, away_ident, gh, ga, competition, level from g where home_ident = ? or away_ident = ? order by date""", [sk, sk]).fetchall()
        ms = []
        for d, hi, ai, gh, ga, comp, lvl in rows:
            home = hi == sk; opp = ai if home else hi
            # the dataset files the Cup Winners' Cup and the Intercontinental Cup under «ddr» (level international) together with
            # the leagues of states that no longer exist (level national: USSR, Yugoslavia, East Germany)
            c = "ddr-intl" if comp == "ddr" and lvl == "international" else "league" if comp == "ddr" else (comp or "league")
            ms.append([d.isoformat(), key_of.get(opp) or "s:" + opp, 1 if home else 0, gh if home else ga, ga if home else gh, c])
        # English clubs: the lower divisions and the two cups (opponents linked through the main dataset's names)
        if sk.endswith("(England)"):
            for d, oname, h, gf, ga, comp in ENGM.get(efold(sk.rsplit(" (", 1)[0]), []):
                osk = eng_sk.get(efold(oname))
                ms.append([d, key_of.get(osk) or ("s:" + osk if osk else "e:" + oname), h, gf, ga, comp])
            ms.sort(key=lambda m: m[0])
        # after the dataset's last date: our own FotMob archive (every covered competition)
        for mid, d, comp, h, aw, gh, ga in con.execute("select * from fm where (h = ? or a = ?) and date > ? order by date", [fid, fid, last]).fetchall():
            home = h == fid
            ms.append([d.isoformat(), aw if home else h, 1 if home else 0, gh if home else ga, ga if home else gh, f"fm:{comp}"])
        if not ms:
            continue
        tot, by_comp, by_dec, opp = rec(), defaultdict(rec), defaultdict(rec), defaultdict(lambda: dict(rec(), last=None))
        for d, o, h, gf, ga, comp in ms:
            add(tot, gf, ga); add(by_comp[comp], gf, ga); add(by_dec[d[:3] + "0"], gf, ga)
            r = opp[str(o)]; add(r, gf, ga); r["last"] = d
        wins = sorted((m for m in ms if m[3] > m[4]), key=lambda m: (-(m[3] - m[4]), -m[3], m[0]))[:6]
        losses = sorted((m for m in ms if m[3] < m[4]), key=lambda m: (-(m[4] - m[3]), -m[4], m[0]))[:6]
        # names travel with the file: Arabic for every club on the site, the dataset's own name for the others
        names = {}
        for o in opp:
            if o.startswith("s:"):
                names[o] = o[2:].rsplit(" (", 1)[0]
            elif o.startswith("e:"):
                names[o] = o[2:]
            else:
                t = teams.get(o) or {}
                names[o] = t.get("name_ar") or t.get("name") or (cw.get(int(o)) or o).rsplit(" (", 1)[0]   # a linked club we have no page for
        comps = {}
        for c in by_comp:
            comps[c] = INTL.get(c) or ENG_COMPS.get(c) or (COMPS_AR.get(int(c[3:])) if c.startswith("fm:") else "الدوري")
        doc = {"club": fid, "key": sk, "name": (teams.get(str(fid)) or {}).get("name"), "since": ms[0][0], "until": ms[-1][0],
               "total": tot, "by_comp": by_comp, "by_decade": dict(sorted(by_dec.items())),
               "opponents": sorted(([k, v["p"], v["w"], v["d"], v["l"], v["gf"], v["ga"], v["last"]] for k, v in opp.items()), key=lambda x: -x[1]),
               "biggest_wins": wins, "biggest_losses": losses, "first": ms[0], "names": names, "comps": comps,
               "source": "schochastics/football-data (ODC-By) to " + last.isoformat() + ", then Tifo's FotMob archive",
               "fields": {"match": ["date", "opponent (FotMob id or s:dataset key)", "home", "goals for", "goals against", "competition"]}}
        index[fid] = {"since": ms[0][0][:4], "p": tot["p"]}
        if a.upload:
            store.put_json(f"history/club/{fid}.json", doc, cache="warm")
            store.put_json(f"history/club/{fid}/matches.json", {"club": fid, "fields": doc["fields"]["match"], "matches": ms, "names": names}, cache="warm")
        elif a.club:
            print(json.dumps({k: doc[k] for k in ("name", "since", "total", "by_decade")}, ensure_ascii=False)[:800]); print(doc["opponents"][:8]); print(wins[:3])
    if a.upload and not a.club:
        store.put_json("history/index.json", {"generated": date.today().isoformat(), "clubs": index, "dataset_until": last.isoformat()}, cache="warm")
    print(f"{len(index)} club histories" + (" uploaded" if a.upload else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
