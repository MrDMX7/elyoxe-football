"""The results files of worldfootballR_data (github.com/JaseZiv/worldfootballR_data, releases «match_results» and
«match_results_cups»: one .rds a country or a cup, frozen in September 2025), for what they hold beside the score: the
referee, the ground and the attendance of each game (research/tifo-sources-2026-11-24.md §1.4). Men's games only.

  gh release download match_results -R JaseZiv/worldfootballR_data -D DIR/l
  gh release download match_results_cups -R JaseZiv/worldfootballR_data -D DIR/c
  python -m graph.fbref_fetch pack DIR OUT       # one gz file for the graph build (graph/load/fbref.py)

Run on the laptop (pyreadr reads .rds). A row of the pack: [file, date, home, away, home goals, away goals, referee, ground,
attendance]; a game with none of the three is left out."""
import argparse, glob, gzip, json, os, re

WOMEN = re.compile(r"women|frauen|femenina|nwsl|algarve|she_believes|_w_", re.I)


def _txt(v):
    s = str(v).strip() if v is not None else ""
    return None if s in ("", "nan", "NaN", "None", "<NA>", "NA") else s


def _int(v):
    try:
        f = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return int(f) if f == f else None


def _goals(v):
    """«(4) 1» of a shoot-out is 1"""
    n = _int(v)
    if n is not None:
        return n
    m = re.search(r"(\d+)\s*$", re.sub(r"\(\d+\)", "", str(v if v is not None else "")).strip())
    return int(m.group(1)) if m else None


def _side(v):
    """«Iraq iq» and «th Thailand» are Iraq and Thailand: the flag's code is no part of the name"""
    s = _txt(v)
    return re.sub(r"^[a-z]{2,3}(?:-[a-z]{2,3})?\s+|\s+[a-z]{2,3}(?:-[a-z]{2,3})?$", "", s).strip() or None if s else None


def rows_of(frame, name):
    out = []
    for r in frame.to_dict("records"):
        if _txt(r.get("Gender")) not in (None, "M"):
            continue
        d, h, a = _txt(r.get("Date")), _side(r.get("Home")), _side(r.get("Away"))
        hs, as_ = _goals(r.get("HomeGoals")), _goals(r.get("AwayGoals"))
        ref, ven, att = _txt(r.get("Referee")), _txt(r.get("Venue")), _int(r.get("Attendance"))
        if not d or not h or not a or hs is None or as_ is None or not (ref or ven or att):
            continue
        ven = re.sub(r"\s*\(Neutral Site\)\s*$", "", ven) if ven else None
        out.append([name, d[:10], h, a, hs, as_, ref, ven, att if att and att > 0 else None])
    return out


def pack(root, out):
    import pyreadr
    rows = []
    for f in sorted(glob.glob(os.path.join(root, "*", "*.rds"))):
        name = os.path.basename(f).replace("_match_results.rds", "")
        if WOMEN.search(name):
            continue
        got = rows_of(list(pyreadr.read_r(f).values())[0], name)
        print(name, len(got), flush=True)
        rows += got
    with gzip.open(out, "wt", encoding="utf-8") as z:
        json.dump(rows, z, ensure_ascii=False, separators=(",", ":"))
    print(len(rows), "rows ->", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["pack"])
    ap.add_argument("root")
    ap.add_argument("out")
    a = ap.parse_args()
    pack(a.root, a.out)
