"""National-team Elo for the tournament simulator (Gulf Cup, Asian Cup).

History: martj42/international_results (GitHub, CC0; every men's international since 1872, updated a
few weeks behind), plus FotMob's own national-team results after that file's last date.
World Football Elo style: K = 60 World Cup, 50 continental finals (Asian Cup, Gulf Cup, Arab Cup ...),
40 qualifiers, 30 other tournaments, 20 friendlies; x goal-difference multiplier; home advantage HOME
unless the venue is neutral. Probabilities reuse compute/rating.probs with NATIONAL params (fitted by
tools/calibrate_national.py, out-of-sample Brier in docs/TIFO-RATING.md).
FotMob names are mapped to the dataset's names with ALIASES; anything unmatched is listed in the output.
"""
import csv, io

from . import rating as R

CSV_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
NATIONAL = {"k_scale": 1.0, "home": 100, "d0": 0.30, "ds": 450, "base": 1500, "newcomer": 1300, "regress": 0}
ALIASES = {"UAE": "United Arab Emirates", "USA": "United States", "South Korea": "South Korea", "Korea Republic": "South Korea",
           "North Korea": "North Korea", "China PR": "China", "China": "China", "Kyrgyz Republic": "Kyrgyzstan",
           "Iran": "Iran", "IR Iran": "Iran", "Palestine": "Palestine", "Chinese Taipei": "Taiwan", "Türkiye": "Turkey",
           "Turkiye": "Turkey", "Côte d'Ivoire": "Ivory Coast", "Ivory Coast": "Ivory Coast", "Czechia": "Czech Republic",
           "Cabo Verde": "Cape Verde", "Hong Kong": "Hong Kong", "Macau": "Macau", "Timor-Leste": "East Timor",
           "Brunei Darussalam": "Brunei", "DR Congo": "DR Congo", "Curacao": "Curaçao", "Bosnia-Herzegovina": "Bosnia and Herzegovina"}


def k_for(tournament):
    t = (tournament or "").lower()
    if t == "fifa world cup":
        return 60
    if "qualification" in t:
        return 40
    if t in ("afc asian cup", "gulf cup", "arabian gulf cup", "fifa arab cup", "arab cup", "uefa euro", "copa américa",
             "african cup of nations", "concacaf gold cup", "confederations cup"):
        return 50
    if t == "friendly":
        return 20
    return 30


def parse_csv(text):
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            hs, as_ = int(r["home_score"]), int(r["away_score"])
        except (TypeError, ValueError):
            continue          # scheduled fixtures carry NA
        rows.append((r["date"], r["home_team"], r["away_team"], hs, as_, r["tournament"], r["neutral"] == "TRUE"))
    return rows


def elo(rows, p=None, predict_from=None):
    """rows [(date, home, away, hs, as, tournament, neutral)] -> (ratings by name, predictions)."""
    p = {**NATIONAL, **(p or {})}
    r, preds = {}, []
    for date, h, a, hs, as_, tour, neutral in sorted(rows):
        rh, ra = r.get(h, p["base"]), r.get(a, p["base"])
        ph, pd, pa = R.probs(rh, ra, p, neutral)
        out = 0 if hs > as_ else 1 if hs == as_ else 2
        if predict_from and date >= predict_from:
            preds.append({"p": (ph, pd, pa), "outcome": out, "ko": date})
        e = 1 / (1 + 10 ** (-(rh + (0 if neutral else p["home"]) - ra) / 400))
        s = 1 if out == 0 else 0.5 if out == 1 else 0
        d = p["k_scale"] * k_for(tour) * R.gd_mult(hs - as_) * (s - e)
        r[h], r[a] = rh + d, ra - d
    return r, preds


def dataset_name(fotmob_name, known):
    n = ALIASES.get(fotmob_name, fotmob_name)
    if n in known:
        return n
    stripped = fotmob_name.replace(" U23", "")
    return stripped if stripped in known else None
