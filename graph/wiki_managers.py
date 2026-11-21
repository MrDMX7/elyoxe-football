"""Managers by spell from English Wikipedia (the clubs' «List of <club> managers» pages and their own articles' managerial
history tables), for the decades FotMob's coachHistory (2012 on) never reached. Pure parser + a weekly fetch stage in the
pattern of graph.awards_fetch (Parsoid HTML, one request a second, a gzip copy kept 30 days, the cache carried in S3).

    python -m graph.wiki_managers [--upload]

Files (graph/.cache/managers/, and S3 state/graph/managers/cache.tar.gz between runs): pages/<sha1>.html.gz, pages.json.
The clubs and their articles: graph/wiki_managers.yaml ({FotMob team id: [article titles]})."""
import argparse, calendar, io, json, os, re, sys, tarfile
from lxml import html as LH

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from graph import awards_fetch as AF
from graph.awards_wiki import clean, grid, _section

CACHE = os.path.join(HERE, ".cache", "managers")
CONF = os.path.join(HERE, "wiki_managers.yaml")
STATE_KEY = "state/graph/managers/cache.tar.gz"
_key = AF._key

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
MONTHS["sept"] = 9
YEAR = re.compile(r"^(\d{4})$")
D_M_Y = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)\.?\s+(\d{4})$")
M_D_Y = re.compile(r"^([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})$")
M_Y = re.compile(r"^([A-Za-z]+)\.?\s+(\d{4})$")
OPEN = re.compile(r"^(present|current|now|incumbent|today)\b", re.I)
ROLE = re.compile(r"\s*\((caretaker|interim|player[- ]manager|player[- ]coach|acting)[^)]*\)", re.I)
SEC_OK = re.compile(r"manager|coach|trainer", re.I)          # not «Management»: the board
SEC_NO = re.compile(r"president|chairm|board|owner|captain|kit|sponsor|player", re.I)
H_NAME = re.compile(r"^(name|head coach|manager|coach|head coaches|managers|trainer)$", re.I)
H_FROM = re.compile(r"^(from|start|appointed|began)$", re.I)
H_TO = re.compile(r"^(to|until|end|left|departed|till)$", re.I)


def day(text, end=False):
    """A Wikipedia date cell -> «YYYY-MM-DD»: a bare year is its first day (its last for an end), a month its first (last)."""
    t = clean(text).strip(" .")
    m = YEAR.match(t)
    if m:
        return f"{m.group(1)}-12-31" if end else f"{m.group(1)}-01-01"
    for rx, order in ((D_M_Y, "dmy"), (M_D_Y, "mdy")):
        m = rx.match(t)
        if m:
            d, mon, y = (m.group(1), m.group(2), m.group(3)) if order == "dmy" else (m.group(2), m.group(1), m.group(3))
            mo = MONTHS.get(mon.lower())
            if mo and 1 <= int(d) <= calendar.monthrange(int(y), mo)[1]:
                return f"{y}-{mo:02d}-{int(d):02d}"
            return None
    m = M_Y.match(t)
    if m and MONTHS.get(m.group(1).lower()):
        y, mo = int(m.group(2)), MONTHS[m.group(1).lower()]
        return f"{y}-{mo:02d}-{calendar.monthrange(y, mo)[1]:02d}" if end else f"{y}-{mo:02d}-01"
    return None


def _cols(header):
    names = [clean(c[0]).split("}")[-1].strip() for c in header]      # a tooltip's inline style leaks into «Nat.»
    pick = lambda rx: next((i for i, h in enumerate(names) if rx.match(h)), None)
    return pick(H_NAME), pick(H_FROM), pick(H_TO)


def parse(raw, listing=False):
    """Every managers table of an article -> [{name, title, start, end, open}] in the page's order. listing: a «List of
    <club> managers» page, whose table may sit under no heading."""
    doc = LH.fromstring(raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw)     # bytes: lxml would guess latin-1
    out = []
    for table in doc.xpath("//table"):
        if table.xpath(".//table"):                # a layout wrapper: its inner table is read on its own
            continue
        g = grid(table)
        if len(g) < 2:
            continue
        ni, fi, ti = _cols(g[0])
        if ni is None or fi is None or ti is None:
            continue
        sec = _section(table)
        if SEC_NO.search(sec) and not SEC_OK.search(sec):
            continue
        if not SEC_OK.search(sec) and not (listing and not sec) and not re.search(r"coach|manager", clean(g[0][ni][0]), re.I):
            continue
        for row in g[1:]:
            if len(row) <= max(ni, fi, ti) or row[ni][2]:
                continue
            name = ROLE.sub("", clean(row[ni][0])).strip()
            start, to = day(row[fi][0]), clean(row[ti][0])
            is_open = bool(OPEN.match(to))
            end = None if is_open else day(to, end=True)
            if not name or not start or (end is None and not is_open) or (end and end < start):
                continue
            out.append({"name": name, "title": (row[ni][1] or [None])[0], "start": start, "end": end, "open": is_open})
    return out


def clubs():
    import yaml
    try:
        d = yaml.safe_load(open(CONF, encoding="utf-8")) or {}
    except OSError:
        return {}
    return {int(k): list(v or []) for k, v in d.items()}


def restore(S, d=CACHE):
    try:
        raw = S.store().b.s3.get_object(Bucket=S.store().b.bucket, Key=STATE_KEY)["Body"].read()
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
            tf.extractall(os.path.dirname(d), filter="data")
        return True
    except Exception as e:
        print(f"no managers cache in S3 ({type(e).__name__})", flush=True)
        return False


def _tar(d):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        tf.add(d, arcname="managers")
    return buf.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload", action="store_true")
    a = ap.parse_args(argv)
    from graph.src import Sources
    S = Sources()
    if a.upload and not os.path.exists(os.path.join(CACHE, "pages.json")):
        restore(S)
    titles = sorted({t for ts in clubs().values() for t in ts})
    out = AF.fetch_pages(AF.HTTP(), CACHE, titles)
    out["spells"] = sum(len(parse(AF.read_page(CACHE, t) or b"<html/>", t.startswith("List of"))) for t in titles)
    print(json.dumps(out), flush=True)
    if a.upload:
        st = S.store()
        st.b.s3.put_object(Bucket=st.b.bucket, Key=STATE_KEY, Body=_tar(CACHE), ContentType="application/gzip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
