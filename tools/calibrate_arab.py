"""Calibrate the Arab clubs rating (one Elo scale over every Arab league and the AFC/CAF/Arab club
competitions that link them). Fetches every season FotMob has of competitions.yaml `history_comps`
(cached in /tmp/tifo-arab-history.json), fits on matches before 2022-07-01 (first season of each
league = burn-in), scores 2022-07-01 onward. Prints params + Brier vs base rates.
  python tools/calibrate_arab.py [--refetch]"""
import itertools, json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
from compute import history as H, rating as R  # noqa: E402
from sources.fotmob import FotMob  # noqa: E402

CACHE = "/tmp/tifo-arab-history.json"


def fetch():
    if os.path.exists(CACHE) and "--refetch" not in sys.argv:
        return json.load(open(CACHE))
    fm, hist = FotMob(), {}
    for cid in config.settings()["history_comps"]:
        try:
            _, _, seasons = H.season_rows(fm, cid, None)
        except Exception as e:
            print(f"  {cid}: {e}", file=sys.stderr)
            continue
        for s in seasons:
            try:
                ss, rows, _ = H.season_rows(fm, cid, s)
                hist.setdefault(str(cid), {})[ss] = rows
            except Exception as e:
                print(f"  {cid} {s}: {e}", file=sys.stderr)
            time.sleep(0.4)
        print(f"  {cid}: {len(hist.get(str(cid), {}))} seasons", file=sys.stderr)
    json.dump(hist, open(CACHE, "w"))
    return hist


def main():
    rows = H.finished(H.all_rows(fetch()))
    seen, uniq = set(), []
    for r in rows:
        if r["id"] not in seen:
            seen.add(r["id"])
            uniq.append(r)
    rows = [r for r in uniq if r["ko"]]
    for r in rows:              # one season clock for all competitions: the calendar year of July-June
        y = int(r["ko"][:4]) - (1 if int(r["ko"][5:7]) < 7 else 0)
        r["season"] = f"{y}/{y + 1}"
    cut, burn = "2022-07-01", "2013-07-01"
    train = [r for r in rows if r["ko"] < cut]
    best = None
    for k, home, regress, d0, ds, nc in itertools.product([10, 13, 16], [50, 60, 70], [0.2, 0.3, 0.4], [0.27, 0.30], [400, 500],
                                                         [1400]):
        p = {"k": k, "home": home, "regress": regress, "d0": d0, "ds": ds, "newcomer": nc}
        _, _, preds = R.run(train, p, predict_from=burn)
        b = R.brier(preds)
        if best is None or b < best[0]:
            best = (b, p)
    _, _, allp = R.run(rows, best[1], predict_from=burn)
    tr = [x for x in allp if x["ko"] < cut]
    te = [x for x in allp if x["ko"] >= cut]
    base, f = R.base_rate_brier(tr, te)
    print(json.dumps({"params": best[1], "brier_train": round(best[0], 4), "brier_test": round(R.brier(te), 4),
                      "brier_base_rate_test": round(base, 4), "base_rates": [round(x, 3) for x in f],
                      "n_train_scored": len(tr), "n_test": len(te), "matches_total": len(rows),
                      "comps": sorted(fetch().keys(), key=int)}, indent=1))


if __name__ == "__main__":
    main()
