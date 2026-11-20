"""Award tables from an English Wikipedia article (spec §7.3): the article's HTML (REST, Parsoid) -> every table that pairs
a season with a linked person (an award, a top scorer list) or with a champion and a runner-up club. Merged cells are
unfolded first, so a year spanning a three-row podium dates all three rows. Pure: no network, no graph."""
import re
import urllib.parse
from lxml import html as LH

REF = re.compile(r"\[(?:\d+|[a-z]|note \d+|nb \d+)\]", re.I)
MARK = re.compile(r"[†‡*^§¶#]+")
SEASON = re.compile(r"^(\d{4})(?:\s*[–\-/]\s*(\d{4}|\d{2})(?!\d))?")
H_YEAR = re.compile(r"\b(year|season|edition|tournament)\b|^ed\.?$", re.I)          # singular: «Years» / «Seasons» are spans and lists
SKIP_SECTION = re.compile(r"multiple|by (player|club|team|country|nation|nationality|position|league)|all[- ]time|nominee|shortlist|"
                          r"finalist|record|statistic|dream team|team of|all[- ]star|selection|squad|list of (players|nominees)", re.I)
NOT_A_WINNER = re.compile(r"^(not awarded|no award|not held|none|vacant|cancel+ed|withheld|abandoned|void|tb[ad]|n/?a|[—–-])\b|^[—–-]$", re.I)
POSITIONS = re.compile(r"goalkeeper|defender|midfielder|forward|striker", re.I)
H_TEAM = re.compile(r"club|team|nation|country|nationality|^nat\.?$|position|league", re.I)
H_PERSON = re.compile(r"player|winner|scorer|^name|recipient|goalkeeper|manager|coach|footballer|best|^top", re.I)
H_CHAMP = re.compile(r"champion|winner", re.I)
H_RUNNER = re.compile(r"runner", re.I)
H_VALUE = re.compile(r"goals?\b|points?\b|votes?\b|^pts|%", re.I)
H_RANK = re.compile(r"^(rank|place|pos\.?)$", re.I)
KINDS = [("top_scorer", re.compile(r"scorer|golden boot|goalscor|pichichi|capocannoniere|torj[aä]ger|golden shoe|top goal", re.I)),
         ("best_goalkeeper", re.compile(r"goalkeeper|golden glove|yashin|zamora", re.I)),
         ("best_young", re.compile(r"young|golden boy|kopa|rookie|revelation|breakthrough", re.I)),
         ("coach", re.compile(r"manager|coach", re.I))]


def clean(t):
    return re.sub(r"\s+", " ", MARK.sub("", REF.sub("", t or ""))).strip()


def season_label(text):
    m = SEASON.match(clean(text))
    if not m:
        return None
    y1 = int(m.group(1))
    if not m.group(2):
        return str(y1)
    y2 = int(m.group(2))
    if len(m.group(2)) == 2:
        y2 += (y1 // 100) * 100
        if y2 < y1:
            y2 += 100
    return f"{y1}/{y2}"


def _links(c):
    out, red = [], []
    for a in c.xpath(".//a[@rel='mw:WikiLink']"):
        h = a.get("href") or ""
        if not h.startswith("./"):
            continue
        if "redlink=1" in h or "new" in (a.get("class") or "").split():
            red.append(clean(a.text_content()))
            continue
        t = urllib.parse.unquote(h[2:].split("#")[0].split("?")[0])
        if t and ":" not in t:
            out.append(t)
    return out, red


def grid(table):
    """Rows of cells (text, links, is_th, redlinks) with rowspan/colspan unfolded."""
    rows = table.xpath("./tr|./thead/tr|./tbody/tr|./tfoot/tr")
    out, carry = [], {}
    for tr in rows:
        cells, row, col, ci = tr.xpath("./th|./td"), [], 0, 0
        while ci < len(cells) or col in carry:
            if col in carry:
                cell, left = carry[col]
                row.append(cell)
                if left <= 1:
                    del carry[col]
                else:
                    carry[col] = (cell, left - 1)
                col += 1
                continue
            c = cells[ci]
            ci += 1
            try:
                rs, cs = max(1, int(c.get("rowspan") or 1)), max(1, int(c.get("colspan") or 1))
            except ValueError:
                rs, cs = 1, 1
            links, red = _links(c)
            val = (clean(c.text_content()), links, c.tag == "th", red)
            for _ in range(min(cs, 30)):
                row.append(val)
                if rs > 1:
                    carry[col] = (val, rs - 1)
                col += 1
        out.append(row)
    return out


def _section(t):
    s = t.getparent()
    while s is not None and s.tag != "section":
        s = s.getparent()
    if s is not None:
        for tag in ("h2", "h3", "h4"):
            h = s.find(f"./{tag}")
            if h is not None:
                return clean(h.text_content())
    return ""


def _rank(text):
    m = re.match(r"(\d+)", clean(text))
    return int(m.group(1)) if m else None


def _col(hdr, rx, skip=()):
    return next((i for i, h in enumerate(hdr) if i not in skip and rx.search(h)), None)


def _kind(*texts):
    for k, rx in KINDS:
        if any(rx.search(t or "") for t in texts):
            return k
    return None


def table_rows(g, page, section):
    """The award tables in one wikitable: [] when it is not one (no season column, no person/club, < 3 dated rows); one per
    award column when a table sets several awards side by side («Season | Player of the Season | Young Player | Coach»)."""
    if SKIP_SECTION.search(section):
        return []
    nh = 0
    while nh < len(g) and g[nh] and all(c[2] for c in g[nh]):
        nh += 1
    if not nh or nh >= len(g):
        return []
    # the header is the all-<th> row naming the most distinct columns, not a separator row («Ballon d'Or (1956–2009)»)
    hdr = [c[0] for c in max(g[:nh], key=lambda r: len({c[0] for c in r if c[0]}))]
    body = g[nh:]
    if sum(1 for h in hdr if POSITIONS.search(h)) >= 2:          # a team of the tournament, not an award
        return []
    yi = _col(hdr, H_YEAR)
    if yi is None and sum(1 for r in body if r and season_label(r[0][0])) >= 3:
        yi = 0
    if yi is None:
        return []
    teams = {i for i, h in enumerate(hdr) if H_TEAM.search(h)}
    award_cols = [i for i, h in enumerate(hdr) if i != yi and i not in teams and (H_PERSON.search(h) or _kind(h))
                  and not H_VALUE.search(h) and not H_RANK.search(h)]
    if len(award_cols) >= 2 and len({hdr[i] for i in award_cols}) == len(award_cols) and not any(H_RUNNER.search(hdr[i]) for i in award_cols):
        out = []
        for i in award_cols:
            got = _rows(body, page, f"{section} — {hdr[i]}", yi, i, None, None, None, _kind(hdr[i]) or "winner")
            if got:
                out.append(got)
        return out
    ri = _col(hdr, H_RUNNER, {yi})
    ci = _col(hdr, H_CHAMP, {yi, ri}) if ri is not None else None
    team_table = ri is not None and ci is not None
    pi = None if team_table else _col(hdr, H_PERSON, {yi} | {i for i, h in enumerate(hdr) if H_TEAM.search(h)})
    if not team_table and pi is None:
        return []
    ti = None if team_table else _col(hdr, re.compile(r"club|team", re.I), {yi, pi})
    vi = _col(hdr, H_VALUE, {yi, pi, ti})
    ki = _col(hdr, H_RANK, {yi})
    if team_table:
        kind = "champion_table"
    else:
        kind = _kind(section, " ".join(hdr)) or _kind(page) or "winner"
    got = _rows(body, page, section, yi, pi, ti, vi, ki, kind, ci, ri)
    return [got] if got else []


def _rows(body, page, section, yi, pi, ti, vi, ki, kind, ci=None, ri=None):
    team_table = kind == "champion_table"
    rows = []
    for r in body:
        if len(r) <= max(i for i in (yi, pi, ci, ri, ti, vi, ki, 0) if i is not None):
            continue
        season = season_label(r[yi][0])
        if not season:
            continue
        if team_table:
            champ, run = r[ci][1], r[ri][1]
            if not champ:
                continue
            rows.append({"season": season, "rank": 1, "person": None, "name": r[ci][0], "team": champ[0], "runner_up": run[0] if run else None,
                         "runner_up_name": r[ri][0] or None, "value": None})
            continue
        cell = r[pi]
        if not cell[0] or NOT_A_WINNER.search(cell[0]):
            continue
        rk = _rank(r[ki][0]) if ki is not None else None
        rows.append({"season": season, "rank": rk or 1, "person": cell[1][0] if cell[1] else None,
                     "name": (cell[3][0] if cell[3] and not cell[1] else cell[0]),
                     "team": (r[ti][1][0] if ti is not None and r[ti][1] else None),
                     "value": (r[vi][0] or None) if vi is not None else None})
    if len(rows) < 3:
        return None
    if ki is None and not team_table and len(rows) > 3 * len({r["season"] for r in rows}):
        return None          # many names a season and no rank: nominees or a squad, not winners
    return {"page": page, "section": section, "kind": kind, "who": "team" if team_table else "person", "rows": rows}


def canonical(html, page):
    """The article a title is served from: «FIFA World Cup Golden Ball» redirects to «FIFA World Cup awards»."""
    m = re.search(rb'rel="dc:isVersionOf" href="//[a-z]+\.wikipedia\.org/wiki/([^"]+)"', html if isinstance(html, bytes) else html.encode())
    return urllib.parse.unquote(m.group(1).decode()).replace("_", " ") if m else page


def extract(html, page):
    doc = LH.fromstring(html.decode("utf-8", "replace") if isinstance(html, bytes) else html)   # bytes alone read as Latin-1
    for st in doc.xpath("//style|//sup[contains(@class,'reference')]"):
        st.drop_tree()
    out = []
    for t in doc.xpath("//table[contains(concat(' ', normalize-space(@class), ' '), ' wikitable ')]"):
        out.extend(table_rows(grid(t), page, _section(t)))
    return out


# ---- a season's own article («2016–17 UAE Pro League»): its awards table and its top scorers (the season is the title's)
SEASON_KINDS = [("best_local", re.compile(r"emirati|saudi|qatari|local|national player|best (arab|egyptian|moroccan|tunisian|algerian|iraqi|kuwaiti|omani|bahraini|jordanian)", re.I)),
                ("best_goalkeeper", re.compile(r"goalkeeper", re.I)), ("best_young", re.compile(r"young|youth|rookie|revelation|u-?2[13]", re.I)),
                ("best_coach", re.compile(r"coach|manager", re.I)), ("top_scorer", re.compile(r"top ?scorer|golden boot|top goal", re.I)),
                ("best_player", re.compile(r"player of the (season|year)|best player|most valuable|\bmvp\b|footballer of the", re.I))]
H_AWARD = re.compile(r"^(award|awards|category|prize|title)$", re.I)
SEASON_TITLE = re.compile(r"^(\d{4}(?:[–-]\d{2,4})?)[ _](.+)$")
SEASON_LINK = re.compile(r"(league|liga|serie|bundesliga|ligue|division|cup|championship|eredivisie|primeira|s[uü]per lig)", re.I)


def season_links(html):
    """Season articles a competition's article links («2016–17_UAE_Pro_League»), in page order, once each."""
    out = []
    for h in re.findall(rb'href="\./([^"#?]+)"', html if isinstance(html, bytes) else html.encode()):
        t = urllib.parse.unquote(h.decode("utf-8", "replace"))
        m = SEASON_TITLE.match(t)
        if m and SEASON_LINK.search(m.group(2)) and not re.search(r"\bin\b", m.group(2)) and t not in out:
            out.append(t)
    return out


def extract_season(html, page):
    m = SEASON_TITLE.match(page.replace("_", " "))
    season = season_label(m.group(1)) if m else None
    doc = LH.fromstring(html.decode("utf-8", "replace") if isinstance(html, bytes) else html)
    for st in doc.xpath("//style|//sup[contains(@class,'reference')]"):
        st.drop_tree()
    rows = []
    for t in doc.xpath("//table[contains(concat(' ', normalize-space(@class), ' '), ' wikitable ')]"):
        g, section = grid(t), _section(t)
        if not g or not g[0]:
            continue
        hdr = [c[0] for c in g[0]]
        body = g[1:]
        ai = _col(hdr, H_AWARD)
        pi = _col(hdr, re.compile(r"player|winner|name|recipient", re.I), {ai} if ai is not None else set())
        ti = _col(hdr, re.compile(r"club|team", re.I), {ai, pi})
        if ai is not None and pi is not None:                      # Award | Winner | Club
            for r in body:
                if len(r) <= max(ai, pi):
                    continue
                kind = next((k for k, rx in SEASON_KINDS if rx.search(r[ai][0])), None)
                if not kind or not r[pi][0]:
                    continue
                rows.append({"kind": kind, "rank": 1, "person": r[pi][1][0] if r[pi][1] else None, "name": r[pi][0],
                             "team": r[ti][1][0] if ti is not None and len(r) > ti and r[ti][1] else None, "value": None})
            continue
        if pi is not None and re.search(r"scorer|goalscor", section, re.I):   # Rank | Player | Club | Goals
            ki, vi = _col(hdr, re.compile(r"^(rank|pos\.?|#)$", re.I)), _col(hdr, re.compile(r"goals?", re.I))
            last, got = 0, []
            for r in body:
                if len(r) <= pi or not r[pi][0]:
                    continue
                rk = _rank(r[ki][0]) if ki is not None and len(r) > ki else None
                if ki is not None:
                    rk = rk or last or 1
                    last = rk
                got.append({"kind": "top_scorer", "rank": rk, "person": r[pi][1][0] if r[pi][1] else None, "name": r[pi][0],
                            "team": r[ti][1][0] if ti is not None and len(r) > ti and r[ti][1] else None,
                            "value": r[vi][0] if vi is not None and len(r) > vi else None})
            if ki is None:                                         # no rank column: the goals rank them, ties share a rank
                got.sort(key=lambda x: -(_rank(x["value"] or "") or 0))
                prev = None
                for i, x in enumerate(got):
                    g = _rank(x["value"] or "") or 0
                    x["rank"] = prev[1] if prev and prev[0] == g else i + 1
                    prev = (g, x["rank"])
            rows += [x for x in got if x["rank"] <= 10]
    return {"page": page, "season": season, "rows": rows}


# ---- a national team's article: «Most appearances» and «Top goalscorers» (caps, goals and years for that country; the
# totals of the players before FotMob, whose matches our archive holds only in part)
RECORD_SECTION = re.compile(r"most (appearances|capped)|top (goal)?scorers|most goals|leading (goal)?scorers|player records", re.I)
NOT_SENIOR = re.compile(r"women|under-\d|u-?\d{2}|olympic|\bb\b|futsal|beach|amputee|youth", re.I)


def _num(text):
    m = re.match(r"\s*(\d+)", text or "")
    return int(m.group(1)) if m else None


def intl_records(html):
    doc = LH.fromstring(html.decode("utf-8", "replace") if isinstance(html, bytes) else html)
    for st in doc.xpath("//style|//sup[contains(@class,'reference')]"):
        st.drop_tree()
    by = {}
    for t in doc.xpath("//table[contains(concat(' ', normalize-space(@class), ' '), ' wikitable ')]"):
        if not RECORD_SECTION.search(_section(t) or ""):
            continue
        g = grid(t)
        if not g or not g[0]:
            continue
        hdr = [clean(c[0]) for c in g[0]]
        col = lambda rx: next((i for i, h in enumerate(hdr) if re.search(rx, h, re.I)), None)
        pi, ci, gi, yi = col(r"^(player|name)"), col(r"^(caps|apps|appearances)"), col(r"^goals"), col(r"career|years|period")
        if pi is None or (ci is None and gi is None):
            continue
        for r in g[1:]:
            if pi >= len(r) or not r[pi][1]:
                continue
            person = r[pi][1][0]
            d = by.setdefault(person, {"person": person, "name": re.sub(r"\s*\(list\)\s*$", "", clean(r[pi][0])), "caps": None, "goals": None, "career": None})
            for k, i in (("caps", ci), ("goals", gi)):
                if i is not None and i < len(r) and d[k] is None:
                    d[k] = _num(r[i][0])
            if yi is not None and yi < len(r) and not d["career"]:
                d["career"] = clean(r[yi][0]) or None
    return list(by.values())


def national_articles(html):
    """The men's senior national teams Wikipedia's «List of men's national association football teams» links."""
    h = html.decode("utf-8", "replace") if isinstance(html, bytes) else html
    out = set()
    for m in re.findall(r'href="\./([^"#]+_national_football_team)(?:#[^"]*)?"', h):
        t = urllib.parse.unquote(m).replace("_", " ")
        if not NOT_SENIOR.search(t):
            out.add(t)
    return sorted(out)
