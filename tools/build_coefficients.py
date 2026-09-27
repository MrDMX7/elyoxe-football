"""AFC club competitions ranking (associations) and the CAF 5-year ranking (associations and clubs)
-> coefficients.json (committed; the analytics function publishes it as arabs/coefficients.json).

Source: the English Wikipedia articles "AFC club competitions ranking" and "CAF 5-year ranking", which
cite FootyRankings (AFC, recomputed from AFC results) and CAF / RSSSF. Facts only (ranks, points,
countries, clubs); the revision ids are recorded. Totals written as {{#expr: ...}} are evaluated here.
Rerun weekly by hand:   python tools/build_coefficients.py > coefficients.json
"""
import ast, json, operator, re, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402

UA = "elyoxe-tifo-data/0.1 (hello@elyoxe.com)"
API = "https://en.wikipedia.org/w/api.php?action=parse&page={}&prop=wikitext|revid&format=json&formatversion=2"
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _eval(expr):
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in OPS:
            return OPS[type(n.op)](ev(n.left), ev(n.right))
        raise ValueError(expr)
    return ev(ast.parse(expr, mode="eval"))


def page(title):
    d = json.loads(urllib.request.urlopen(urllib.request.Request(API.format(title), headers={"User-Agent": UA}), timeout=30).read())["parse"]
    return d["wikitext"], d["revid"]


def section_table(w, heading):
    i = w.find(heading)
    if i < 0:
        return None
    j = w.find("{|", i)
    k = w.find("\n|}", j)
    return w[j:k]


def cells(row):
    out = []
    for line in row.split("\n"):
        line = line.strip()
        if not line.startswith("|") or line.startswith("|-") or line.startswith("|}"):
            continue
        for c in line[1:].split("||"):
            c = re.sub(r'^\s*(?:align|bgcolor|style|data-sort-type)="?[^|]*"?\s*\|', "", c)
            out.append(c.strip())
    return out


def num(c):
    m = re.search(r"\{\{#expr:\s*([^}]*)\}\}", c)
    if m:
        return round(_eval(m.group(1)), 3)
    c = re.sub(r"'''|<[^>]+>|\{\{efn[^}]*\}\}", "", c).strip()
    try:
        return float(c)
    except ValueError:
        return None


def flag(c):
    m = re.search(r"\{\{(?:flagicon|fba|fb|flag)\|([A-Z]{3})", c)
    return m.group(1) if m else None


def link_name(c):
    m = re.search(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", c)
    return m.group(1).replace("&nbsp;", " ") if m else None


def main():
    arab = {c["fotmob_code"]: c for c in config.countries() if c.get("arab")}
    fifa = {"KSA": "KSA", "UAE": "UAE", "QAT": "QAT", "KUW": "KUW", "BHR": "BHR", "OMA": "OMA", "IRQ": "IRQ", "JOR": "JOR", "SYR": "SYR",
            "LBN": "LBN", "PLE": "PLE", "YEM": "YEM", "EGY": "EGY", "MAR": "MAR", "ALG": "ALG", "TUN": "TUN", "LBY": "LBY", "SDN": "SDN",
            "MTN": "MTN", "SOM": "SOM", "DJI": "DJI", "COM": "COM"}

    def country(code):
        c = arab.get(fifa.get(code, code))
        return {"code": code, "arab": bool(c), "iso2": c["iso2"] if c else None, "name_ar": c["name_ar"] if c else None}

    afc_w, afc_rev = page("AFC_club_competitions_ranking")
    caf_w, caf_rev = page("CAF_5-year_ranking")
    afc = []
    t = section_table(afc_w, "==== 2026–27 season ====")
    for row in (t or "").split("\n|-")[1:]:
        cs = cells(row)
        if len(cs) < 14 or not flag(" ".join(cs[:6])):
            continue
        code = next(flag(c) for c in cs if flag(c))
        vals = [num(c) for c in cs[5:13]]
        afc.append({"region_rank": cs[0], "rank": int(num(cs[1]) or 0), "prev_rank": int(num(cs[2]) or 0) or None,
                    "association": link_name(cs[4]), **country(code), "season_points": vals, "total": num(cs[13])})
    caf_assoc, caf_clubs = [], []
    t = section_table(caf_w, "==Association ranking for the 2026–27 CAF club season==")
    for row in (t or "").split("\n|-")[1:]:
        cs = cells(row)
        code = next((flag(c) for c in cs if flag(c)), None)
        if not code:
            continue
        caf_assoc.append({"rank": int(num(cs[0]) or 0), "prev_rank": int(num(cs[1]) or 0) or None, **country(code),
                          "total": num(cs[-1])})
    t = section_table(caf_w, "==Club ranking for the 2026–27 CAF club season==")
    for row in (t or "").split("\n|-")[1:]:
        cs = cells(row)
        if len(cs) < 3 or not flag(cs[1]):
            continue
        caf_clubs.append({"rank": int(num(cs[0]) or 0), "club": link_name(cs[1]), **country(flag(cs[1])),
                          "season_points": [num(c) for c in cs[2:-1]], "total": num(cs[-1])})
    print(json.dumps({
        "sources": {"afc": {"url": f"https://en.wikipedia.org/w/index.php?title=AFC_club_competitions_ranking&oldid={afc_rev}",
                            "cites": "https://footyrankings.github.io/crank2027/ (AFC ranking recomputed from AFC results)"},
                    "caf": {"url": f"https://en.wikipedia.org/w/index.php?title=CAF_5-year_ranking&oldid={caf_rev}",
                            "cites": "CAF / RSSSF as cited in the article"}},
        "afc_associations_2026_27": afc, "caf_associations_2026_27": caf_assoc, "caf_clubs_2026_27": caf_clubs,
        "history": "the articles keep only the current and previous season; the previous season's AFC table and CAF 'Historical "
                   "rankings since 2011' are not parsed yet",
        "note": "facts only (ranks, points); AFC has no official club ranking table, only associations"}, ensure_ascii=False, indent=0))


if __name__ == "__main__":
    main()
