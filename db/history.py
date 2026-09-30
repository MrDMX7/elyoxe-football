"""Every club's full history (owner 2026-09-30: «الداتا بيس لكل الاندية العالمية… كلها»), stage 1: results since 1888 (England: every division and both cups).

    python -m db.history [--upload | --out DIR] [--club 8456]

    --out DIR writes the would-be files under DIR (history/club/<id>.json, …/matches.json, history/index.json,
    crosswalk.json) and uploads nothing: a dry run to diff against what is published.

Sources:
  schochastics/football-data  games.parquet: 1.3M league and continental matches, 207 top divisions, 1888 -> 2025-09
                              (ODC-By). Teams are keyed by strings like «Al Hilal FC (Saudi Arabia)».
  our FotMob archive          v1/archive/all/<season>.json: the covered competitions since 2010, with FotMob ids; it
                              links the two (below) and adds every game the dataset lacks, at any date (domestic cups,
                              leagues it does not carry, the 2025 Club World Cup, and everything after its last date).

Dataset hygiene (audit 2026-09-30): its 2025 block is loaded twice (one copy kept), placeholder teams («NA (NA)»,
« ()») and «X v X» rows are dropped, and a season's minority national league is dropped when one of its games falls
within a day of another game of the club (the dataset files Al-Ahli Amman's Jordanian seasons under «Al Ahly (Egypt)»
and Al Duhail's Qatar league under «Al Shorta (Iraq)»; a club plays one league at a time and one game a day).

Linking, never by name: a FotMob match and a dataset match on the same date (+-1 day, time zones) with the same score
vote for «FotMob home id = dataset home key» and the same for away. A club is linked when one key has at least 5 votes,
70% of its votes, and that key's own best FotMob id is the same club (both directions agree).

Out (public): v1/history/club/<fotmob id>.json (record, per competition, per decade, every opponent, biggest wins and
defeats, first match, scope: since when domestic cups and lower divisions are in) and v1/history/club/<id>/matches.json
(every match), v1/history/index.json (who has a history).
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
# the dataset's placeholder teams: 441 rows «NA (NA)» (Jordan 2000s) and 389 rows « ()» (2025-26, the name missing)
BLANK = ("NA (NA)", " ()")
CUP_KINDS = ("cup", "supercup", "tournament")     # index.json kinds that, with a country, are a domestic cup
LOWER_FM = {10721}                                 # second tiers among our competitions (Saudi First Division)


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


def crosswalk(con, prev=None):
    """{FotMob id: dataset key}. prev: the last run's links (crosswalk.json), kept while still the mutual best pair."""
    con.execute("""create or replace table votes as
      with pairs as (
        select f.h fm, g.home_ident sk from fm f join g on g.gh = f.gh and g.ga = f.ga and g.date between f.date - 1 and f.date + 1
        union all
        select f.a fm, g.away_ident sk from fm f join g on g.gh = f.gh and g.ga = f.ga and g.date between f.date - 1 and f.date + 1)
      select fm, sk, count(*) n from pairs group by 1, 2""")
    # every match also agrees by chance with dozens of others that day with the same score, so the share of votes is
    # meaningless; what separates the real pair is how far it leads the runner-up, in both directions
    best = """with b1 as (select fm, sk, n, row_number() over (partition by fm order by n desc) r from {v}),
        s1 as (select fm, max(n) filter (where r = 2) n2 from b1 group by 1),
        b2 as (select sk, fm, n, row_number() over (partition by sk order by n desc) r from {v}),
        s2 as (select sk, max(n) filter (where r = 2) n2 from b2 group by 1)
      select b1.fm, b1.sk, b1.n from b1 join s1 using (fm) join b2 on b2.sk = b1.sk and b2.r = 1 and b2.fm = b1.fm join s2 on s2.sk = b1.sk
      where b1.r = 1 and b1.n >= 5 and b1.n >= 3 * coalesce(s1.n2, 0) and b2.n >= 3 * coalesce(s2.n2, 0)"""
    out = {int(fm): sk for fm, sk, n in con.execute(best.format(v="votes")).fetchall()}
    # the chance votes grow with the archive (its South American leagues put 20 from one Brazilian club on «Kashima
    # Antlers (Japan)», 54 for the real pair: under the 3x rule): a link made before stays while its two sides are still
    # each other's first choice with 5+ votes; new links still need the 3x lead
    if prev:
        taken = set(out.values())
        mutual = con.execute("""with b1 as (select fm, sk, n, row_number() over (partition by fm order by n desc) r from votes),
            b2 as (select sk, fm, row_number() over (partition by sk order by n desc) r from votes)
          select b1.fm, b1.sk from b1 join b2 on b2.sk = b1.sk and b2.fm = b1.fm and b2.r = 1 where b1.r = 1 and b1.n >= 5""").fetchall()
        for fm, sk in mutual:
            if int(fm) not in out and prev.get(int(fm)) == sk and sk not in taken:
                out[int(fm)] = sk
    return out


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


def _season(d):
    return d.year if d.month >= 7 else d.year - 1


def merged_blocks(sk, rows, fm_games):
    """{(competition, season)} of the club's dataset rows that belong to another club filed under the same key.
    A club plays one national league per season and one game a day: when a season has two national leagues, the
    minority one is dropped if any of its games falls within a day of another game of the club — another dataset row, or
    a FotMob archive game with a different score (the same score is the same game). Legit moves keep their rows: Cardiff
    or Monaco have one national league a season, the Soviet 1991 → Ukraine 1992 switch has no clash."""
    per = defaultdict(lambda: defaultdict(int))
    for d, hi, ai, gh, ga, comp, lvl in rows:
        if lvl == "national":
            per[_season(d)][comp] += 1
    drop = set()
    for s, cs in per.items():
        if len(cs) < 2:
            continue
        main = max(cs, key=lambda c: cs[c])
        for comp in cs:
            if comp == main:
                continue
            blk = [r for r in rows if r[6] == "national" and r[5] == comp and _season(r[0]) == s]
            other = {r[0].toordinal() for r in rows if not (r[6] == "national" and r[5] == comp and _season(r[0]) == s)}
            for d, hi, ai, gh, ga, *_ in blk:
                gf_ga = (gh, ga) if hi == sk else (ga, gh)
                o = d.toordinal()
                if any(o + k in other for k in (-1, 0, 1)) or any(sc != gf_ga for k in (-1, 0, 1) for sc in fm_games.get(o + k, ())):
                    drop.add((comp, s))
                    break
    return drop


def scope(ms, domestic_cups):
    """The first game we hold in domestic cups and in lower divisions (None: none), so the page says what is in."""
    cup = lower = None
    for d, o, h, gf, ga, c in ms:
        c = str(c)
        fmc = int(c[3:]) if c.startswith("fm:") and c[3:].isdigit() else None
        if c in ("facup", "leaguecup") or (c.startswith("rsssf:") and c.endswith(":cup")) or fmc in domestic_cups:
            cup = cup or d
        if c.startswith("eng:") or fmc in LOWER_FM:
            lower = lower or d
    return {"domestic_cups_since": cup, "lower_divisions_since": lower}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); ap.add_argument("--club", type=int)
    ap.add_argument("--out", help="write the would-be files under this folder and upload nothing (a dry run)")
    a = ap.parse_args(argv)
    fetch()
    store = Store(S3Backend(BUCKET))

    def put(path, obj):
        if a.out:
            p = os.path.join(a.out, *path.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        elif a.upload:
            store.put_json(path, obj, cache="warm")

    con = duckdb.connect()
    con.execute("SET enable_progress_bar=false")
    src = f"read_parquet('{PARQUET.replace(chr(92), '/')}')"
    raw = con.execute(f"select count(*) from {src} where gh is not null and ga is not null").fetchone()[0]
    # one copy of each game (the dataset carries 2025-06-06..09-15 twice), no placeholder team, no «X v X»
    con.execute(f"""create table g as select * from {src}
        where gh is not null and ga is not null and home_ident <> away_ident
          and home_ident not in {BLANK} and away_ident not in {BLANK}
        qualify row_number() over (partition by date, home_ident, away_ident, gh, ga, competition order by level) = 1""")
    last = con.execute("select max(date) from g").fetchone()[0]
    fmr = fotmob_archive(store)
    con.execute("create table fm (id bigint, date date, comp int, h int, a int, gh int, ga int)")
    con.executemany("insert into fm values (?, ?, ?, ?, ?, ?, ?)", fmr)
    print(f"dataset: {con.execute('select count(*) from g').fetchone()[0]} matches to {last} ({raw} before dropping duplicates, "
          f"placeholder teams and X v X); FotMob archive: {len(fmr)}")
    try:
        prev = {int(k): v for k, v in json.load(open(os.path.join(CACHE, "crosswalk.json"), encoding="utf-8")).items()}
    except (OSError, ValueError):
        prev = {}
    cw = crosswalk(con, prev)
    print(len(cw), "FotMob clubs linked to the dataset;", sum(1 for k in prev if k not in cw), "links of the last run lost:",
          sorted((k, v) for k, v in prev.items() if k not in cw)[:10])
    json.dump({str(k): v for k, v in sorted(cw.items())}, open(os.path.join(a.out or CACHE, "crosswalk.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=0)
    key_of = {v: k for k, v in cw.items()}                                   # dataset key -> FotMob id
    teams = (store.get_json("teams.json") or {}).get("teams") or {}
    comp_meta = {c["id"]: c for c in ((store.get_json("index.json") or {}).get("competitions") or []) if c.get("id")}
    global COMPS_AR
    COMPS_AR = {cid: c.get("name_ar") for cid, c in comp_meta.items()}
    domestic_cups = {cid for cid, c in comp_meta.items() if (c.get("country") or {}).get("iso2") and c.get("kind") in CUP_KINDS}
    # names for FotMob ids we have no team page for: the encyclopedia's clubs, then FotMob's own Arabic mapping
    world = {str(c[0]): c for c in ((store.get_json("world/index.json") or {}).get("clubs") or [])}
    try:
        fm_ar = (json.load(open(os.path.join(CACHE, "fm_ar.json"), encoding="utf-8")).get("Participants")) or {}
    except (OSError, ValueError):
        fm_ar = {}
    fm_by_club = defaultdict(list)                                           # every archive game of a club, any date
    for r in fmr:
        fm_by_club[r[3]].append(r)
        fm_by_club[r[4]].append(r)

    ENGM, efold = eng_matches()
    # the Arab leagues before the datasets start: RSSSF's season pages (db/rsssf.py) — positions per season, dated matches
    try:
        RS = json.load(open(os.path.join(CACHE, "rsssf_clubs.json"), encoding="utf-8"))
    except (OSError, ValueError):
        RS = {}
    eng_sk = {efold(r[0].rsplit(" (", 1)[0]): r[0] for r in con.execute("select distinct home_ident from g where home_ident like '%(England)'").fetchall()}
    targets = [a.club] if a.club else sorted(set(cw) | {int(k) for k in RS})
    index, stats = {}, defaultdict(int)
    for fid in targets:
        sk = cw.get(fid) or ""
        if not sk and not RS.get(str(fid)):
            continue
        if ((teams.get(str(fid)) or {}).get("country") or {}).get("national"):
            stats["national teams skipped"] += 1           # a national team is not a club (RSSSF once linked «Oman» Club to it)
            continue
        fm_games = defaultdict(list)                        # day -> the club's (goals for, against) in the archive
        for mid, d, comp, h, aw, gh, ga in fm_by_club.get(fid, []):
            fm_games[date.fromisoformat(d).toordinal()].append((gh, ga) if h == fid else (ga, gh))
        rows = [] if not sk else con.execute("""select date, home_ident, away_ident, gh, ga, competition, level from g where home_ident = ? or away_ident = ? order by date""", [sk, sk]).fetchall()
        drop = merged_blocks(sk, rows, fm_games) if rows else set()
        if drop:
            n0 = len(rows)
            rows = [r for r in rows if not (r[6] == "national" and (r[5], _season(r[0])) in drop)]
            stats["rows of another club dropped"] += n0 - len(rows)
            print(f"  {fid} {sk}: dropped {n0 - len(rows)} rows of another club ({', '.join(f'{c} {s}/{s + 1}' for c, s in sorted(drop))})")
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
        # RSSSF matches only where no other source has this club on that date (±2 days) against that opponent
        rs = RS.get(str(fid)) or {}
        if rs.get("matches"):
            from datetime import date as _d
            seen = {(m[0], str(m[1])) for m in ms}
            near = lambda d, o: any((str(_d.fromordinal(_d.fromisoformat(d).toordinal() + k)), str(o)) in seen for k in (-2, -1, 0, 1, 2))
            for m in rs["matches"]:
                if not near(m[0], m[1]):
                    ms.append(m)
            ms.sort(key=lambda m: m[0])
        # our own FotMob archive, every date: each game no other source has (no game of the club within a day against the
        # same opponent or with the same score) — domestic cups, leagues the dataset lacks, and everything after its last date
        have = defaultdict(list)
        for m in ms:
            have[date.fromisoformat(m[0]).toordinal()].append(m)
        for mid, d, comp, h, aw, gh, ga in sorted(fm_by_club.get(fid, []), key=lambda r: r[1]):
            home = h == fid; opp = aw if home else h; gf, ga_ = (gh, ga) if home else (ga, gh)
            o = date.fromisoformat(d).toordinal()
            same = [x for k in (-1, 0, 1) for x in have.get(o + k, []) if str(x[1]) == str(opp) or (x[3], x[4]) == (gf, ga_)]
            if same:
                # the same game: FotMob's club id wins over a dataset key linked to another club (the dataset files Al Duhail
                # as «Al Shorta (Iraq)» in 2023-25, so Al Hilal's 7-0 of 2023-02-26 read «v Al Shorta») — only when FotMob's
                # club is itself linked: an unlinked id is FotMob's old id for the same club (Al Sahel was 101715 in 2010/11)
                for x in same:
                    if isinstance(x[1], int) and x[1] != opp and opp in cw and (x[3], x[4]) == (gf, ga_) and not str(x[5]).startswith(("fm:", "rsssf:")):
                        x[1] = opp
                        stats["dataset opponents corrected by FotMob"] += 1
                continue
            row = [d, opp, 1 if home else 0, gf, ga_, f"fm:{comp}"]
            ms.append(row)
            have[o].append(row)
            stats["archive games added"] += 1
        ms.sort(key=lambda m: m[0])
        if not ms:
            continue
        tot, by_comp, by_dec, opp = rec(), defaultdict(rec), defaultdict(rec), defaultdict(lambda: dict(rec(), last=None))
        for d, o, h, gf, ga, comp in ms:
            add(tot, gf, ga); add(by_comp[comp], gf, ga); add(by_dec[d[:3] + "0"], gf, ga)
            r = opp[str(o)]; add(r, gf, ga); r["last"] = d
        wins = sorted((m for m in ms if m[3] > m[4]), key=lambda m: (-(m[3] - m[4]), -m[3], m[0]))[:6]
        losses = sorted((m for m in ms if m[3] < m[4]), key=lambda m: (-(m[4] - m[3]), -m[4], m[0]))[:6]
        # names travel with the file: Arabic for every club on the site or in the encyclopedia, the dataset's own name for the others
        names = {}
        for o in opp:
            if o.startswith("s:"):
                names[o] = o[2:].rsplit(" (", 1)[0]
            elif o.startswith("e:") or o.startswith("r:"):
                names[o] = o[2:]
            else:
                t, w = teams.get(o) or {}, world.get(o) or [None, None, None]
                names[o] = (t.get("name_ar") or w[1] or fm_ar.get(o) or t.get("name") or w[2]
                            or (cw.get(int(o)) or o).rsplit(" (", 1)[0])   # a linked club we have no page for
                if names[o] == o:
                    stats["opponents still named by id"] += 1
        comps = {}
        for c in by_comp:
            comps[c] = INTL.get(c) or ENG_COMPS.get(c) or (COMPS_AR.get(int(c[3:])) if c.startswith("fm:") else
                                                            "الكؤوس (RSSSF)" if c.endswith(":cup") else "الدوري")
        doc = {"club": fid, "key": sk, "name": (teams.get(str(fid)) or {}).get("name"), "since": ms[0][0], "until": ms[-1][0],
               "total": tot, "by_comp": by_comp, "by_decade": dict(sorted(by_dec.items())),
               "opponents": sorted(([k, v["p"], v["w"], v["d"], v["l"], v["gf"], v["ga"], v["last"]] for k, v in opp.items()), key=lambda x: -x[1]),
               "biggest_wins": wins, "biggest_losses": losses, "first": ms[0], "names": names, "comps": comps,
               "positions": sorted(rs.get("positions") or [], key=lambda x: x[0]),
               "scope": scope(ms, domestic_cups),
               "source": "schochastics/football-data (ODC-By) to " + last.isoformat() + ", and Tifo's FotMob archive (every covered "
                         "competition since 2010/11) for each game the dataset lacks",
               "fields": {"match": ["date", "opponent (FotMob id or s:dataset key)", "home", "goals for", "goals against", "competition"]}}
        index[fid] = {"since": ms[0][0][:4], "p": tot["p"]}
        if a.upload or a.out:
            put(f"history/club/{fid}.json", doc)
            put(f"history/club/{fid}/matches.json", {"club": fid, "fields": doc["fields"]["match"], "matches": ms, "names": names})
        if a.club:
            print(json.dumps({k: doc[k] for k in ("name", "since", "total", "by_decade", "scope")}, ensure_ascii=False)[:900]); print(doc["opponents"][:8]); print(wins[:3])
    if (a.upload or a.out) and not a.club:
        put("history/index.json", {"generated": date.today().isoformat(), "clubs": index, "dataset_until": last.isoformat()})
    print(dict(stats))
    print(f"{len(index)} club histories" + (" uploaded" if a.upload and not a.out else f" written under {a.out}" if a.out else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
