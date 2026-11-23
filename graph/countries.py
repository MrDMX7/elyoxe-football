"""One spelling of a country, whatever the source wrote: ISO 3166 alpha-2, the home nations as news/nations.json writes them
(GB-ENG, GB-SCT, GB-WLS, GB-NIR). Transfermarkt's leagues say «TR», FotMob's «TUR», a club's own «Turkiye»; read as three
countries they kept 497 clubs on two pages each (Hearts, Aalborg, Alanyaspor: 23 Nov 2026).

graph/country_codes.json: the three-letter codes (FIFA's, Wikidata P3441 on the national teams, and ISO alpha-3, P298) to
alpha-2, the ones Wikidata gives two countries for set by hand (POR, IRL, GRE...). A region («Asia», «International») is no
country: None."""
import json
import os
import re
import unicodedata
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
CODES = os.path.join(HERE, "country_codes.json")
NATIONS = os.path.join(os.path.dirname(HERE), "news", "nations.json")
# FotMob's own three letters where they are not FIFA's
EXTRA = {"BOS": "BA", "CDR": "CD", "CHT": "TW", "CON": "CG", "CPR": "CN", "CVI": "CV", "FGU": "GF", "IVR": "CI", "KIT": "KN"}


def _fold(s):
    return re.sub(r"[^a-z ]", "", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()).strip()


@lru_cache(maxsize=1)
def _tables():
    codes = json.load(open(CODES, encoding="utf-8"))
    codes.update(EXTRA)
    nat = json.load(open(NATIONS, encoding="utf-8"))
    names = {_fold(x): k for k, vs in nat["names"].items() for x in vs if _fold(x)}
    names.update({_fold(k): v for k, v in nat["fotmob"].items() if _fold(k)})
    names["the phillipines"] = "PH"
    return codes, set(nat["names"]), names


def canon(x):
    if not x:
        return None
    codes, iso2, names = _tables()
    s = str(x).strip()
    if len(s) == 2 and s.upper() in iso2:
        return s.upper()
    if len(s) == 3 and s.upper() in codes:
        return codes[s.upper()]
    return names.get(_fold(s))
