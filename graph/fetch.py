"""The graph's one network step, before the loaders: martj42's internationals (CC0), weekly."""
import os, time, urllib.request

MARTJ42 = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"


def martj42(S, max_age_days=7):
    p = os.path.join(S.db, "martj42_results.csv")
    if not os.path.exists(p) or time.time() - os.path.getmtime(p) > max_age_days * 86400:
        data = urllib.request.urlopen(urllib.request.Request(MARTJ42, headers={"User-Agent": "elyoxe-tifo/0.1"}), timeout=120).read()
        tmp = p + ".tmp"
        open(tmp, "wb").write(data)
        os.replace(tmp, p)
    return p
