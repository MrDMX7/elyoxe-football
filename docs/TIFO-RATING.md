# Tifo rating and match probabilities

The code is in `compute/rating.py` (clubs) and `compute/national.py` (national teams). The parameters live in
`competitions.yaml` under `rating:` and in `compute/national.NATIONAL`. The outputs are:

- `ratings/uae-clubs.json`
- `ratings/team/{id}.json` (history for charts)
- `probs` on every scheduled UAE club match
- `comp/538/sim.json`
- `ratings/national.json`
- `comp/{329,290}/tournament-sim.json`

## Club rating

- **Data:** every UAE club match FotMob has, 2873 finished matches:
  - Pro League from 2010/11
  - President's Cup from 2018/19
  - League Cup and Super Cup from 2025/26
- **Update:** Elo in the World Football Elo style: `r += K × G × (S − E)`.
  - `E = 1/(1+10^(−(r_home + H − r_away)/400))`
  - `G` = 1 (0–1 goals), 1.5 (2), (11+n)/8 (n ≥ 3)
  - `H` = 0 in the Super Cup and cup finals
- **Between seasons:** ratings regress 10% toward 1500.
- **New clubs:** a club seen for the first time after 2010/11 (promoted) starts at 1350.
- **Team ids:** they are continuous in FotMob. Shabab Al Ahli is 102119 from 2015/16 on. The clubs merged into it in 2017 (Al Shabab 102115, Dubai CSC) keep their own ids and simply stop.
- **Draws:** `draw = 0.26 × exp(−(d/350)²)`, where `d` is the rating gap including home advantage. Home = `E − draw/2`, away = `1 − E − draw/2`.
- **Older seasons:** no free machine-readable source has UAE league results before 2010/11.
  - TheSportsDB's free tier caps every list at 5 rows.
  - ESPN and openfootball have no UAE league.
  - RSSSF and Wikipedia have champions tables, not match results.
  - The all-time champions since 1973–74 therefore come from `alltime.yaml` (facts from Wikipedia and RSSSF), not from the rating.

### Calibration (out of sample)

- **Method:** `tools/calibrate_rating.py` grid-searched K, H, the regression, the draw shape and the newcomer rating.
- **Fit:** 2010/11–2021/22 (1910 matches scored after the 2010/11 burn-in). Each match is predicted before the rating sees it.
- **Test:** 2022/23–2025/26 (831 matches) with the chosen parameters.
- **Brier convention:** the 3-class sum over home/draw/away of the squared error. 0 is perfect, 2 is the worst, and always predicting 1/3 each scores 0.667.

| | Brier |
|---|---|
| Tifo rating, test 2022/23–2025/26 | **0.5599** |
| Base rates (home 0.434, draw 0.23, away 0.336 from the training seasons), same test | 0.6531 |
| Tifo rating, training seasons | 0.5695 |

Parameters: `{"k": 17, "home": 40, "regress": 0.1, "d0": 0.26, "ds": 350, "newcomer": 1350}`.

Reliability of the home-win probability on the test set:

| predicted | matches | mean predicted | observed |
|---|---|---|---|
| 0.0-0.1 | 17 | 0.087 | 0.000 |
| 0.1-0.2 | 126 | 0.150 | 0.159 |
| 0.2-0.3 | 124 | 0.253 | 0.153 |
| 0.3-0.4 | 117 | 0.349 | 0.299 |
| 0.4-0.5 | 104 | 0.451 | 0.404 |
| 0.5-0.6 | 109 | 0.551 | 0.495 |
| 0.6-0.7 | 99 | 0.648 | 0.606 |
| 0.7-0.8 | 88 | 0.748 | 0.682 |
| 0.8-0.9 | 44 | 0.837 | 0.864 |
| 0.9-1.0 | 3 | 0.911 | 1.000 |

The model is slightly over-confident on the favourite at 0.5–0.8. A later version could shrink toward the base rate.

## National teams

- **Data:** the martj42/international_results dataset (GitHub, every men's international since 1872, updated within weeks). FotMob's national-team results after the dataset's last date are appended through name mapping; unmatched names are listed in `ratings/national.json`.
- **Update:** K = 60 World Cup, 50 continental finals, 40 qualifiers, 30 other tournaments, 20 friendlies. Home advantage is 100 unless the venue is neutral.
- **Calibration:** `tools/calibrate_national.py` fitted on 1990–2017 (scored from 2010) and tested on 2018–2026 (8247 matches).
  - Brier: **0.514**, against 0.634 for base rates.
  - Parameters: home 100, d0 0.30, ds 450.

## Simulators

- **Season (`comp/538/sim.json`):** 10,000 seasons. The remaining fixtures come from FotMob plus the official uaepl.ae pairings, and the file checks played + remaining = 182.
  - Each game is drawn from the probabilities at today's ratings.
  - Ties go on current goal difference, then random. This is not the official head-to-head rule.
  - The seed is (season, games played), so the numbers change only when a result arrives.
- **Tournaments (`comp/329`, `comp/290`):** the remaining group games are simulated.
  - Best third-placed teams fill FotMob's `3BEF`-style bracket slots.
  - Knockout draws are settled 50/50.
  - The host (Saudi Arabia for both) gets home advantage.

## Danger index (xG proxy for competitions without xG)

- **Model:** `compute/danger.py`. It computes `xg_proxy = b0 + b1·shots on target + b2·big chances + b3·shots inside the box + b4·corners` per team and match.
- **Fitting:** ordinary least squares against FotMob's own team xG on every stored match that has both. The model is refitted daily and published in `models/danger.json`.
- **First fit (2026-09-27, 798 team-matches from the Saudi, Qatar, European and AFC ledgers):**
  - intercept 0.040; shots on target 0.039; big chances 0.246; shots inside the box 0.081; corners −0.007
  - R² against xG: **0.79**
  - correlation with goals scored: proxy **0.586**, real xG 0.613
- **Where it is used:** competitions with no source xG (the UAE Pro League) get `comp/{id}/xg.json` with `"proxy": true`, including the "fair table" (xPts and luck from the proxy).
