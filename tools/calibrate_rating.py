"""Fit the Tifo rating parameters out of sample and report the Brier score.
Fetches every UAE club season FotMob has (cached in /tmp/tifo-history.json), fits on 2010/11-2021/22
(each match predicted before the rating sees it; 2010/11 is burn-in and not scored), then scores
2022/23-2025/26 with the chosen parameters. Prints the YAML block for competitions.yaml `rating:`.
  python tools/calibrate_rating.py [--refetch]
"""
import itertools, json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from compute import history as H, rating as R  # noqa: E402
from sources.fotmob import FotMob  # noqa: E402

CACHE = "/tmp/tifo-history.json"


def fetch():
    if os.path.exists(CACHE) and "--refetch" not in sys.argv:
        return json.load(open(CACHE))
    fm, hist = FotMob(), {}
    for cid in R.UAE_CLUB_COMPS:
        _, _, seasons = H.season_rows(fm, cid, None)
        for s in seasons:
            ss, rows, _ = H.season_rows(fm, cid, s)
            hist.setdefault(str(cid), {})[ss] = rows
            print(f"  {cid} {ss}: {len(rows)} matches", file=sys.stderr)
            time.sleep(0.5)
    json.dump(hist, open(CACHE, "w"))
    return hist


def main():
    rows = H.finished(H.all_rows(fetch()))
    rows = [r for r in rows if r["season"] and r["season"] <= "2025/2026"]
    train_end, test_start = "2022-07-01", "2022-07-01"
    burn = "2011-07-01"
    grid = {"k": [14, 17, 20, 24, 28], "home": [10, 20, 30, 40, 55], "regress": [0.0, 0.05, 0.1, 0.2],
            "d0": [0.20, 0.23, 0.26, 0.30], "ds": [250, 350, 500], "newcomer": [1350, 1400, 1450]}
    keys = list(grid)
    best = None
    train_rows = [r for r in rows if r["ko"] < train_end]
    for vals in itertools.product(*[grid[k] for k in keys]):
        p = dict(zip(keys, vals))
        _, _, preds = R.run(train_rows, p, predict_from=burn)
        b = R.brier(preds)
        if best is None or b < best[0]:
            best = (b, p)
    b_train, p = best
    _, _, all_preds = R.run(rows, p, predict_from=burn)
    train = [x for x in all_preds if x["ko"] < train_end]
    test = [x for x in all_preds if x["ko"] >= test_start]
    b_test = R.brier(test)
    b_base, freq = R.base_rate_brier(train, test)
    # calibration table on the test set (home-win probability deciles)
    bins = {}
    for x in test:
        k = min(int(x["p"][0] * 10), 9)
        bins.setdefault(k, []).append(x)
    cal = {f"{k/10:.1f}-{(k+1)/10:.1f}": [len(v), round(sum(y["p"][0] for y in v) / len(v), 3),
                                          round(sum(1 for y in v if y["outcome"] == 0) / len(v), 3)] for k, v in sorted(bins.items())}
    out = {"params": p, "brier_train": round(b_train, 4), "brier_test": round(b_test, 4),
           "brier_base_rate_test": round(b_base, 4), "base_rates_train": [round(f, 3) for f in freq],
           "n_train_scored": len(train), "n_test": len(test), "matches_total": len(rows),
           "calibration_test_home_win": cal}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
