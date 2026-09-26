"""Fit national-team Elo parameters on martj42 results before 2018, score 2018-2026 out of sample
(Brier, 3-class sum). Prints the chosen parameters for compute/national.NATIONAL.
  python tools/calibrate_national.py [results.csv]"""
import itertools, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from compute import national as N, rating as R  # noqa: E402


def main():
    if len(sys.argv) > 1:
        text = open(sys.argv[1], encoding="utf-8").read()
    else:
        text = urllib.request.urlopen(N.CSV_URL, timeout=60).read().decode("utf-8")
    rows = [r for r in N.parse_csv(text) if r[0] >= "1990-01-01"]
    best = None
    for k, home, d0, ds in itertools.product([0.8, 1.0, 1.2], [60, 80, 100], [0.28, 0.31, 0.34, 0.38], [400, 550, 700, 900]):
        p = {"k_scale": k, "home": home, "d0": d0, "ds": ds}
        _, preds = N.elo([r for r in rows if r[0] < "2018-01-01"], p, predict_from="2010-01-01")
        b = R.brier(preds)
        if best is None or b < best[0]:
            best = (b, p)
    _, preds = N.elo(rows, best[1], predict_from="2018-01-01")
    _, train = N.elo([r for r in rows if r[0] < "2018-01-01"], best[1], predict_from="2010-01-01")
    base, f = R.base_rate_brier(train, preds)
    print({"params": best[1], "brier_train_2010_2017": round(best[0], 4), "brier_test_2018_on": round(R.brier(preds), 4),
           "brier_base_rate_test": round(base, 4), "n_test": len(preds)})


if __name__ == "__main__":
    main()
