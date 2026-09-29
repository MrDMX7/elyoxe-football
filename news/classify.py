"""What a news item is about, from its headline and description, in the six languages the sources use.

kind: transfer | injury | presser | statement | official | match | other
stage (transfers): rumour < talks < agreed < here_we_go < official   (the furthest stage any word shows)
Rules only: cheap, predictable, and the Claude summary may refine a story's stage later."""
import re
from .entities import norm

KIND_WORDS = {
    "transfer": ["transfer", "signs", "signing", "sign ", "deal", "bid", "loan", "fee", "move to", "joins", "contract", "release clause",
                 "fichaje", "fichar", "ficha", "traspaso", "cesion", "renovacion", "renueva", "contrato", "clausula", "oferta",
                 "transfert", "signe", "prolonge", "mercato", "wechsel", "vertrag", "leihe", "trasferimento", "ingaggio",
                 "انتقال", "صفقه", "التعاقد", "يتعاقد", "يوقع", "توقيع", "عقد", "اعاره", "تجديد", "عرض", "مفاوضات", "ينضم", "الميركاتو"],
    "injury": ["injury", "injured", "ruled out", "out for", "hamstring", "fracture", "surgery", "lesion", "lesionado", "baja", "quirofano",
               "blessure", "blesse", "verletzung", "verletzt", "infortunio", "اصابه", "مصاب", "يغيب", "غياب", "جراحه", "عمليه جراحيه"],
    "presser": ["press conference", "news conference", "rueda de prensa", "conferencia de prensa", "conference de presse",
                "pressekonferenz", "conferenza stampa", "مؤتمر صحفي", "المؤتمر الصحفي"],
    "statement": ["says", "said", "admits", "insists", "reveals", "claims", "told", "declaraciones", "afirma", "asegura", "dijo",
                  "declare", "affirme", "sagt", "erklart", "dichiara", "تصريحات", "يصرح", "صرح", "قال", "يؤكد", "اكد", "يكشف", "كشف"],
    "official": ["official", "officially", "confirmed", "announce", "oficial", "oficialmente", "officiel", "offiziell", "ufficiale",
                 "رسميا", "رسمي", "يعلن", "اعلن", "بيان"],
    "match": ["beat", "beats", "win over", "draw with", "defeat", "vs", "highlights", "player ratings", "match report", "cronica",
              "resumen", "goles", "victoria", "empate", "derrota", "resume", "victoire", "sieg", "niederlage", "vittoria", "sconfitta",
              "يفوز", "فوز", "تعادل", "خساره", "يسحق", "يكتسح", "ملخص", "اهداف مباراه", "ثنائيه", "ثلاثيه", "رباعيه", "خماسيه"],
}
STAGE_WORDS = [
    ("official", ["official", "officially", "confirmed", "completes", "unveiled", "oficial", "officiel", "offiziell", "ufficiale", "رسميا", "يعلن التعاقد", "رسمي"]),
    ("here_we_go", ["here we go"]),
    ("agreed", ["agreed", "agreement", "deal done", "medical", "acuerdo", "reconocimiento medico", "accord", "einigung", "accordo",
                "اتفاق", "اتفق", "الكشف الطبي", "يقترب"]),
    ("talks", ["talks", "negotiat", "bid", "offer", "approach", "negociacion", "oferta", "negociations", "verhandlungen", "trattativa",
               "مفاوضات", "عرض", "يفاوض", "محادثات"]),
]
_K = {k: [norm(w) for w in ws] for k, ws in KIND_WORDS.items()}
_S = [(s, [norm(w) for w in ws]) for s, ws in STAGE_WORDS]
ORDER = ["transfer", "injury", "presser", "official", "statement", "match"]


def _has(text, words):
    t = " " + text + " "
    return any((" " + w + " ") in t or (len(w) > 5 and w in t) for w in words)


def classify(item):
    """-> {"kind", "stage" (transfers only, else None), "here_we_go": bool}."""
    t = norm((item.get("title") or "") + " " + (item.get("desc") or ""))
    kinds = [k for k in ORDER if _has(t, _K[k])]
    kind = kinds[0] if kinds else "other"
    if item.get("tier") == "official" and kind in ("other", "statement"):
        kind = "official"
    hwg = "here we go" in t
    stage = None
    if kind == "transfer" or hwg:
        kind = "transfer"
        stage = "rumour"
        for s, ws in _S:
            if (s == "here_we_go" and hwg) or (s != "here_we_go" and _has(t, ws)):
                stage = s; break
    return {"kind": kind, "stage": stage, "here_we_go": hwg}


OTHER_SPORTS = [norm(w) for w in ["volleyball", "voleibol", "basketball", "baloncesto", "basket", "handball", "balonmano", "tennis", "tenis",
                "futsal", "rugby", "cricket", "formula 1", "nba", "nfl", "baseball", "golf", "boxing", "ufc", "طائرة", "الطائرة", "كرة الطائرة",
                "كرة السلة", "السلة", "كرة اليد", "التنس", "الصالات", "الملاكمة", "الجولف", "فورمولا", "كرة الماء", "البادل"]]


def other_sport(item):
    """True for an item about another sport (a club's volleyball or basketball side comes up in its Google News query)."""
    from .entities import ar_variants
    toks = norm((item.get("title") or "") + " " + (item.get("desc") or "")[:160]).split()
    words = set()                                                 # every reading of every word: «للطائره» -> الطائره، طائره
    for x in toks:
        for v in ar_variants(x):
            words.add(v)
            if v.startswith("ال") and len(v) > 4:
                words.add(v[2:])
    t = " " + " ".join(toks) + " "
    return any((w in words) if " " not in w else (" " + w + " " in t) for w in OTHER_SPORTS)


WOMEN = [norm(w) for w in ["women", "womens", "women's", "wsl", "frauen", "femenino", "femenil", "feminine", "feminin", "féminine",
                            "femminile", "lfc women", "arsenal women", "chelsea women", "barca femeni", "femeni", "nwsl", "للسيدات", "السيدات"]]


def womens(item):
    """True for a women's-team item (a club channel posts both sides; the site's club pages are the men's)."""
    t = " " + norm((item.get("title") or "") + " " + (item.get("desc") or "")[:200]) + " "
    return any(" " + w + " " in t for w in WOMEN)


STAGE_RANK = {None: -1, "rumour": 0, "talks": 1, "agreed": 2, "here_we_go": 3, "official": 4}
