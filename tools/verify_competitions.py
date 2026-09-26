"""Check that every competition in competitions.yaml (or ids given on the command line) returns data
from FotMob today: season, fixtures count, table rows, first/last kickoff, next scheduled match.
Sequential with a 1 s pause (polite).
  python tools/verify_competitions.py            # every entry in competitions.yaml
  python tools/verify_competitions.py 538 9943   # just these ids
  python tools/verify_competitions.py --yaml     # also print `verified:` lines to paste into the yaml
"""
import sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
from sources.fotmob import FotMob  # noqa: E402
from timeutil import now_utc, parse_utc  # noqa: E402


def check(fm, cid):
    c = fm.competition({"id": cid}, with_leaders=False)
    ms = c["matches"]
    kos = sorted(m["kickoff_utc"] for m in ms if m["kickoff_utc"])
    now = now_utc()
    nxt = next((m for m in sorted(ms, key=lambda m: m["kickoff_utc"] or "")
                if m["status"] == "scheduled" and m["kickoff_utc"] and parse_utc(m["kickoff_utc"]) > now), None)
    rows = sum(len(g["rows"]) for g in (c["standings"] or {}).get("groups", []))
    return {
        "season": c["competition"]["season"], "name": c["competition"]["name"], "matches": len(ms),
        "finished": sum(m["status"] == "finished" for m in ms), "table_rows": rows,
        "first": kos[0][:10] if kos else None, "last": kos[-1][:10] if kos else None,
        "next": nxt["kickoff_utc"][:10] if nxt else None, "teams": len(c["teams"]),
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ids = [int(a) for a in args] or [c["id"] for c in config.competitions()]
    fm = FotMob()
    for cid in ids:
        try:
            r = check(fm, cid)
            ok = r["matches"] > 0 or r["table_rows"] > 0
            print(f"{'OK ' if ok else 'EMPTY'} {cid:>6} {r['name']!s:32} season={r['season']} matches={r['matches']} "
                  f"(ft {r['finished']}) table={r['table_rows']} teams={r['teams']} {r['first']}..{r['last']} next={r['next']}")
            if "--yaml" in sys.argv:
                print(f"    verified: \"{now_utc():%Y-%m-%d} season {r['season']}, {r['matches']} matches, "
                      f"{r['table_rows']} table rows, next {r['next']}\"")
        except Exception as e:
            print(f"FAIL  {cid:>6} {type(e).__name__}: {e}")
        time.sleep(1)


if __name__ == "__main__":
    main()
