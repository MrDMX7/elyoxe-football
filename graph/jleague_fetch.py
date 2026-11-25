"""The J.League's own record (data.j-league.or.jp, «日程・結果»): every game of J1 since 1993, J2 since 1999, J3 since 2014
and the League Cup since 1992, each with its attendance. One page a competition and a year.

  python -m graph.jleague_fetch fetch DIR        # l_<frame>_<year>.html, a page not yet in DIR
  python -m graph.jleague_fetch pack DIR OUT     # one gz file for the graph build (graph/load/jleague.py)

A row of the pack: [frame, year, the record's game id, date, home, away, home goals, away goals, shoot-out home, shoot-out
away, round, attendance]. The record writes a club by its short Japanese name; CLUBS gives each the club's name in Latin
letters, the same for every name one club has played under (市原 and 千葉 are JEF United). A cancelled game is left out."""
import argparse, glob, gzip, html, json, os, re, time, unicodedata, urllib.request

URL = "https://data.j-league.or.jp/SFMS01/search?competition_years={y}&competition_frame_ids={f}"
FRAMES = {1: 1993, 2: 1999, 3: 2014, 11: 1992}           # J1, J2, J3, the League Cup: the first year of each
CLUBS = {
    "清水": "Shimizu S-Pulse", "名古屋": "Nagoya Grampus", "浦和": "Urawa Red Diamonds", "鹿島": "Kashima Antlers",
    "広島": "Sanfrecce Hiroshima", "G大阪": "Gamba Osaka", "磐田": "Júbilo Iwata", "C大阪": "Cerezo Osaka", "柏": "Kashiwa Reysol",
    "福岡": "Avispa Fukuoka", "京都": "Kyoto Sanga FC", "札幌": "Hokkaido Consadole Sapporo", "神戸": "Vissel Kobe",
    "山形": "Montedio Yamagata", "甲府": "Ventforet Kofu", "鳥栖": "Sagan Tosu", "仙台": "Vegalta Sendai", "B仙台": "Vegalta Sendai",
    "新潟": "Albirex Niigata", "湘南": "Shonan Bellmare", "平塚": "Shonan Bellmare", "大宮": "Omiya Ardija", "水戸": "Mito HollyHock",
    "川崎F": "Kawasaki Frontale", "大分": "Oita Trinita", "横浜FM": "Yokohama F. Marinos", "横浜M": "Yokohama F. Marinos",
    "横浜FC": "Yokohama FC", "横浜F": "Yokohama Flügels", "東京V": "Tokyo Verdy", "V川崎": "Tokyo Verdy", "徳島": "Tokushima Vortis",
    "千葉": "JEF United Chiba", "市原": "JEF United Chiba", "愛媛": "Ehime FC", "熊本": "Roasso Kumamoto", "岐阜": "FC Gifu",
    "岡山": "Fagiano Okayama", "栃木": "Tochigi SC", "栃木SC": "Tochigi SC", "栃木C": "Tochigi City", "富山": "Kataller Toyama",
    "F東京": "FC Tokyo", "FC東京": "FC Tokyo", "北九州": "Giravanz Kitakyushu", "松本": "Matsumoto Yamaga", "長崎": "V-Varen Nagasaki",
    "町田": "Machida Zelvia", "鳥取": "Gainare Tottori", "群馬": "Thespa Gunma", "草津": "Thespa Gunma", "金沢": "Zweigen Kanazawa",
    "讃岐": "Kamatamare Sanuki", "山口": "Renofa Yamaguchi", "琉球": "FC Ryukyu", "秋田": "Blaublitz Akita", "相模原": "SC Sagamihara",
    "藤枝": "Fujieda MYFC", "長野": "AC Nagano Parceiro", "福島": "Fukushima United", "YS横浜": "YSCC Yokohama",
    "鹿児島": "Kagoshima United", "沼津": "Azul Claro Numazu", "八戸": "Vanraure Hachinohe", "岩手": "Iwate Grulla Morioka",
    "盛岡": "Iwate Grulla Morioka", "今治": "FC Imabari", "宮崎": "Tegevajaro Miyazaki", "いわき": "Iwaki FC", "FC大阪": "FC Osaka",
    "奈良": "Nara Club", "高知": "Kochi United", "C大23": "Cerezo Osaka U-23", "G大23": "Gamba Osaka U-23", "F東23": "FC Tokyo U-23",
    "J-22": "J.League U-22 Selection"}
ROUNDS = (("準々決勝", "1/4"), ("準決勝", "1/2"), ("決勝", "final"))
SCORE = re.compile(r"(\d+)-(\d+)(?:\(PK(\d+)-(\d+)\))?")


def _nfkc(s):
    return unicodedata.normalize("NFKC", s or "").strip()


def _round(frame, label, rnd):
    """the matchday of a league season played in one stage; a cup's last three rounds"""
    label, rnd = _nfkc(label), _nfkc(rnd)
    if frame == 11:
        return next((r for k, r in ROUNDS if rnd.startswith(k)), None)
    m = re.match(r"第(\d+)節", rnd)
    return m.group(1) if m and label in ("J1", "J2", "J3") else None


def parse(text, frame, year):
    """the rows of one page"""
    out = []
    body = text[text.find("<tbody"):text.find("</tbody")]
    for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        c = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", x))).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        card = re.search(r"match_card_id=(\d+)", tr)
        if len(c) < 10 or not card:
            continue
        m, d = SCORE.fullmatch(_nfkc(c[6])), re.match(r"(\d\d)/(\d\d)/(\d\d)", c[3])
        home, away = CLUBS.get(_nfkc(c[5])), CLUBS.get(_nfkc(c[7]))
        if not m or not d or not home or not away:
            continue
        g = [int(x) if x is not None else None for x in m.groups()]
        att = re.sub(r"\D", "", c[9])
        out.append([frame, year, int(card.group(1)), f"{year}-{d.group(2)}-{d.group(3)}", home, away, *g, _round(frame, c[1], c[2]), int(att) if att else None])
    return out


def fetch(d, pause=1.5):
    os.makedirs(d, exist_ok=True)
    for f, first in FRAMES.items():
        for y in range(first, time.gmtime().tm_year + 1):
            p = os.path.join(d, f"l_{f}_{y}.html")
            if os.path.exists(p):
                continue
            req = urllib.request.Request(URL.format(y=y, f=f), headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r, open(p, "wb") as o:
                o.write(r.read())
            time.sleep(pause)


def pack(d, out):
    rows = []
    for p in sorted(glob.glob(os.path.join(d, "l_*.html"))):
        f, y = re.match(r"l_(\d+)_(\d+)", os.path.basename(p)).groups()
        rows += parse(open(p, encoding="utf-8", errors="replace").read(), int(f), int(y))
    rows.sort(key=lambda r: (r[3], r[2]))
    with gzip.open(out, "wt", encoding="utf-8") as z:
        json.dump(rows, z, ensure_ascii=False, separators=(",", ":"))
    return len(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("fetch", "pack"))
    ap.add_argument("dir")
    ap.add_argument("out", nargs="?")
    a = ap.parse_args()
    print(fetch(a.dir) if a.cmd == "fetch" else pack(a.dir, a.out))
