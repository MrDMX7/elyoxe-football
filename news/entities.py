"""Link a news item to the clubs, national teams, players and coaches it names.

The dictionary is built from Tifo's own data (teams.json from the feed, names/players_ar.json, names/coaches_ar.json,
names/clubs_ar.json) plus news/aliases.yaml (short forms and nicknames, written against team NAMES, never guessed ids).

Rules that keep a wrong link rarer than a missing one:
- An alias that names more than one entity is used only when the item settles it: a nisba right after it («النصر
  السعودي»), a league or country cue anywhere in the text or in the Google News query («دوري روشن» -> SA).
  Otherwise it is skipped.
- A surname alone links only when it is long, not a common first name, and unique in the whole dictionary.
- In Arabic a country name is the national team only after «منتخب» («في الإمارات» is a place, not a team).
- Arabic clitics are read through: «للهلال» «بالهلال» «والهلال» -> «الهلال»; «وميسي» «لميسي» -> «ميسي».
"""
import json, os, re, unicodedata
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

AR_DIAC = re.compile("[" + chr(0x064B) + "-" + chr(0x0652) + chr(0x0670) + chr(0x0640) + "]")
AR_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})
NON_WORD = re.compile(r"[^0-9a-z" + chr(0x0621) + "-" + chr(0x064A) + r"\s]+")
AR_LETTER = re.compile("[" + chr(0x0621) + "-" + chr(0x064A) + "]")

# a club / national-team alias that is one of these words alone is too generic to link
LATIN_GENERIC = {"real", "united", "city", "inter", "sporting", "athletic", "athletico", "national", "olympic", "olympique", "union",
                 "racing", "al", "club", "fc", "sc", "ac", "cf", "cd", "town", "rovers", "wanderers", "albion", "hotspur", "the"}
LATIN_SUFFIX = {"fc", "sc", "cf", "afc", "ac", "cd", "sd", "club", "saudi", "fk", "sk", "calcio", "cp"}
# surnames that are also common words or common first names: never linked alone
LATIN_STOP = {"silva", "santos", "costa", "junior", "fernandes", "fernandez", "rodriguez", "gonzalez", "martinez", "garcia", "lopez",
              "perez", "sanchez", "gomez", "diaz", "alves", "souza", "oliveira", "pereira", "ali", "hassan", "mohamed", "mohammed",
              "ahmed", "king", "young", "white", "brown", "walker", "james", "rice", "stones", "green", "hall", "long", "moore",
              "wood", "love", "may", "bell", "hill", "cash", "gray", "grey", "ward", "cook", "fox", "rose", "mount", "sterling",
              "day", "english", "rashid", "saeed", "khalil", "salem", "nasser", "abdullah", "said"}
AR_STOP = {"محمد", "احمد", "علي", "حسن", "حسين", "عبدالله", "عبد", "الله", "سالم", "خالد", "سعيد", "راشد", "سعد", "فهد", "عمر",
           "يوسف", "ابراهيم", "عبدالرحمن", "ناصر", "حمد", "سلطان", "مبارك", "جاسم", "صالح", "عيسي", "موسي", "طارق", "كريم",
           "امين", "ايمن", "جمال", "مصطفي", "محمود", "عادل", "سامي", "هاني", "رامي", "مالك", "ماجد", "منصور", "بن", "ابو",
           "دي", "دا", "فان", "الدين", "عبدالعزيز", "هيثم", "زياد", "بدر", "فيصل", "نواف", "تركي", "مهدي", "علاء"}
NISBA = {"السعودي": "SA", "السعوديه": "SA", "الاماراتي": "AE", "الاماراتيه": "AE", "المصري": "EG", "القطري": "QA", "الكويتي": "KW",
         "المغربي": "MA", "العراقي": "IQ", "الاردني": "JO", "التونسي": "TN", "الجزائري": "DZ", "اللبناني": "LB", "البحريني": "BH",
         "العماني": "OM", "الليبي": "LY", "السوداني": "SD", "السوري": "SY"}
CUES = {"روشن": "SA", "ادنوك": "AE", "نجوم قطر": "QA", "الدوري المصري": "EG", "الدوري السعودي": "SA", "الدوري الاماراتي": "AE",
        "الدوري الكويتي": "KW", "الدوري القطري": "QA", "saudi pro league": "SA", "roshn": "SA", "uae pro league": "AE",
        "adnoc pro league": "AE", "egyptian premier league": "EG", "qatar stars": "QA"}
NATIONAL_AR = {"منتخب", "المنتخب", "لمنتخب", "بمنتخب", "ومنتخب"}


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c) or AR_LETTER.match(c))
    s = AR_DIAC.sub("", s).translate(AR_MAP)
    return re.sub(r"\s+", " ", NON_WORD.sub(" ", s)).strip()


def ar_variants(tok):
    """«للهلال» -> {للهلال, الهلال}; «وميسي» -> {وميسي, ميسي}; Latin tokens come back as they are."""
    out = {tok}
    if not AR_LETTER.match(tok):
        return out
    for p in ("وال", "بال", "فال", "كال"):
        if tok.startswith(p) and len(tok) > len(p) + 1:
            out.add("ال" + tok[len(p):])
    if tok.startswith("لل") and len(tok) > 3:
        out.add("ال" + tok[2:])
    for p in ("و", "ب", "ل", "ف"):
        if tok.startswith(p) and len(tok) > 4:
            out.add(tok[1:])
    return out


LATIN_GENERIC |= {"nations", "league", "cup", "stars", "legends", "all"}
# a club whose Arabic name is also a word the press uses otherwise: not linked right after a competition word
# («كأس الخليج», «دوري الخليج»), and «الاتحاد» not before a federation word («الاتحاد الأوروبي/الدولي/السعودي…»)
COMP_WORDS = {"كاس", "دوري", "بطوله", "خليجي", "cup", "copa", "coupe", "coppa"}
FED_WORDS = {"الاوروبي", "الدولي", "الاسيوي", "الافريقي", "العربي", "الانجليزي", "الاسباني", "الايطالي", "الالماني", "الفرنسي",
             "لكره", "المحلي", "الكروي", "الوطني"} | set(NISBA)
CLUB_WORDS = {"نادي", "فريق", "لنادي", "بنادي", "club"}
# household names the press calls by one word (a surname or a mononym): full names as the dictionary has them
STARS = ["Lionel Messi", "Cristiano Ronaldo", "Kylian Mbappé", "Erling Haaland", "Mohamed Salah", "Lamine Yamal", "Neymar",
         "Vinícius Júnior", "Jude Bellingham", "Harry Kane", "Robert Lewandowski", "Luka Modric", "Karim Benzema", "Riyad Mahrez",
         "Achraf Hakimi", "Yassine Bounou", "Pedri", "Gavi", "Raphinha", "Rodrygo", "Bukayo Saka", "Phil Foden", "Cole Palmer",
         "Martin Ødegaard", "Jamal Musiala", "Florian Wirtz", "Antoine Griezmann", "Ousmane Dembélé", "Victor Osimhen",
         "Lautaro Martínez", "N'Golo Kanté", "Sadio Mané", "Roberto Firmino", "Aleksandar Mitrovic", "Kalidou Koulibaly",
         "Ivan Toney", "Rúben Neves", "João Félix", "Hakim Ziyech", "Sofyan Amrabat", "Youssef En-Nesyri", "Brahim Díaz",
         "Pep Guardiola", "Carlo Ancelotti", "José Mourinho", "Jürgen Klopp", "Diego Simeone", "Mikel Arteta", "Thomas Tuchel",
         "Zinedine Zidane", "Hansi Flick", "Xabi Alonso", "Luis Enrique", "Jorge Jesus", "Stefano Pioli", "Roberto Mancini",
         "Hervé Renard", "Walid Regragui"]


class Dictionary:
    def __init__(self):
        self.alias = defaultdict(set)        # normalized alias -> {(kind, id)}; "W:" weak (surname or one-word name), "N:" national (Arabic)
        self.country = {}                    # (kind, id) -> iso2 for teams
        self.national = set()                # team ids that are national teams
        self.names = {}                      # (kind, id) -> Arabic display name (or Latin)
        self.stars = set()                   # (kind, id) a one-word mention may name on its own
        self.player_team = {}                # player id -> team id (from the league player tables), for weak mentions
        self.maxlen = 1

    def add(self, text, ent, national=False, person=False):
        a = norm(text)
        if not a or len(a) < 3:
            return
        toks = a.split()
        if len(toks) == 1 and toks[0] in LATIN_GENERIC:
            return
        prefix = "N:" if national else "W:" if person and len(toks) == 1 else ""
        self.alias[prefix + a].add(ent)
        self.maxlen = max(self.maxlen, len(toks))

    def surname(self, full, ent, is_ar):
        toks = norm(full).split()
        if len(toks) < 2:
            return
        last = toks[-1]
        stop = AR_STOP if is_ar else LATIN_STOP
        if len(last) >= (4 if is_ar else 5) and last not in stop and last not in LATIN_GENERIC and last not in NISBA:
            self.alias["W:" + last].add(ent)


def build(teams, players, coaches, clubs_ar, aliases, national_comps=frozenset()):
    """teams: teams.json["teams"]; players/coaches/clubs_ar: names/*.json; aliases: news/aliases.yaml parsed.
    teams.json has no national flag: a team whose competitions are all national-team competitions is a national team."""
    D = Dictionary()
    for tid, t in teams.items():
        ent = ("team", int(tid))
        nat = bool(t.get("national")) or bool(t.get("comps") and set(t["comps"]) <= set(national_comps))
        c = t.get("country")
        if isinstance(c, dict) and c.get("iso2"):
            D.country[ent] = c["iso2"]
        if nat:
            D.national.add(int(tid))
        for n in filter(None, [t.get("name"), t.get("short_name")]):
            D.add(n, ent)
            stripped = " ".join(w for w in norm(n).split() if w not in LATIN_SUFFIX)
            if stripped and stripped != norm(n):
                D.add(stripped, ent)
        ar = t.get("name_ar") or (clubs_ar.get(str(tid)) or {}).get("ar")
        if ar:
            D.add(ar, ent, national=nat)        # an Arabic country name is the national team only after «منتخب»
            D.names[ent] = ar
        elif t.get("name"):
            D.names[ent] = t["name"]
    latin_of = {}
    for kind, table in (("player", players), ("coach", coaches)):
        for pid, p in table.items():
            ent = (kind, int(pid))
            if p.get("latin"):
                D.add(p["latin"], ent, person=True); D.surname(p["latin"], ent, False)
                latin_of.setdefault(norm(p["latin"]), []).append(ent)
            if p.get("ar"):
                D.add(p["ar"], ent, person=True); D.surname(p["ar"], ent, True)
                D.names[ent] = p["ar"]
            elif p.get("latin"):
                D.names[ent] = p["latin"]
    for s in STARS:
        ents = latin_of.get(norm(s)) or []
        if len(ents) == 1:
            D.stars.add(ents[0])
    by_name = defaultdict(list)
    for tid, t in teams.items():
        by_name[norm(t.get("name"))].append(int(tid))
    for alias, target in (aliases.get("teams") or {}).items():
        ids = by_name.get(norm(target)) or []
        if len(ids) == 1:
            D.add(alias, ("team", ids[0]))
    for alias, target in (aliases.get("people") or {}).items():   # «Cristiano», «Vinicius», «CR7»: strong, the press means one person
        ents = latin_of.get(norm(target)) or []
        if len(ents) == 1:
            D.alias[norm(alias)].add(ents[0])
            D.maxlen = max(D.maxlen, len(norm(alias).split()))
    return D


def _cues(text_norm):
    got = set()
    for k, iso in CUES.items():
        if norm(k) in text_norm:
            got.add(iso)
    for w, iso in NISBA.items():
        if " " + w in " " + text_norm:
            got.add(iso)
    return got


def link(D, text, query=None):
    """-> sorted list of (kind, id). Strong mentions (a full name, a club, a known short form) link on their own; a weak
    one (a surname or a one-word name) only when it is a star, or when the player's team is in the same item, or when it
    is the Google News query. `query` also counts as context for ambiguous names."""
    t = norm(text)
    qn = norm(query or "")
    ctx = _cues(t + " " + qn)
    toks = t.split()
    strong, weak, used = set(), [], set()
    nat_words = {norm(x) for x in NATIONAL_AR}
    for i in range(len(toks)):
        for n in range(min(D.maxlen, len(toks) - i), 0, -1):
            if any(j in used for j in range(i, i + n)):
                continue
            prev = toks[i - 1] if i > 0 else ""
            nxt = toks[i + n] if i + n < len(toks) else ""
            hit = None
            for first in ar_variants(toks[i]):
                key = " ".join([first] + toks[i + 1:i + n])
                # a country is its national team after «منتخب», or as the first word of the headline («مصر تكتسح…»)
                cands = set(D.alias.get(key, ())) | (set(D.alias.get("N:" + key, ())) if prev in nat_words or i == 0 else set())
                is_weak = False
                if not cands:
                    cands, is_weak = set(D.alias.get("W:" + key, ())), True
                if not cands:
                    continue
                teams = {c for c in cands if c[0] == "team"}
                if teams and prev not in CLUB_WORDS:
                    if prev in COMP_WORDS or (key in NISBA) or (nxt in FED_WORDS and key == norm("الاتحاد")):
                        continue
                if len(cands) > 1:
                    stars = cands & D.stars
                    if stars:
                        cands = stars
                    else:                        # settle by the nisba right after, then by the item's cues
                        iso = {NISBA[nxt]} if nxt in NISBA else ctx
                        cands = {c for c in cands if D.country.get(c) in iso} if iso else set()
                if len(cands) == 1:
                    hit = (next(iter(cands)), is_weak)
                    break
            if hit:
                (weak.append(hit[0]) if hit[1] else strong.add(hit[0]))
                used.update(range(i, i + n))
                break
    team_ids = {e[1] for e in strong if e[0] == "team"}
    for e in weak:
        if e in D.stars or D.player_team.get(e[1]) in team_ids or (qn and D.names.get(e) and norm(D.names[e]).split()[-1] in qn.split()):
            strong.add(e)
    return sorted(strong)


def load(teams_json, names_dir=None, aliases_path=None):
    import yaml
    nd = names_dir or os.path.join(ROOT, "names")
    rd = lambda f: json.load(open(os.path.join(nd, f), encoding="utf-8")) if os.path.exists(os.path.join(nd, f)) else {}
    al = yaml.safe_load(open(aliases_path or os.path.join(HERE, "aliases.yaml"), encoding="utf-8")) or {}
    return build((teams_json or {}).get("teams", teams_json or {}), rd("players_ar.json"), rd("coaches_ar.json"), rd("clubs_ar.json"), al,
                 national_competitions())


NATIONAL_KEYS = {"world-cup", "arab-cup", "arab-cup-qualification", "gulf-cup", "asian-cup", "asian-cup-qualification",
                 "wc-qualification-afc", "afc-u23-asian-cup"}


def national_competitions():
    """Competition ids whose sides are national teams (scope national, plus the world/Asian/Gulf/Arab tournaments)."""
    import sys
    sys.path.insert(0, ROOT)
    import config
    return frozenset(c["id"] for c in config.competitions() if c.get("scope") == "national" or c.get("key") in NATIONAL_KEYS)
