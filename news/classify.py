"""What a news item is about, from its headline and description, in the six languages the sources use.

kind: transfer | injury | presser | statement | official | match | other
stage (transfers): rumour < talks < agreed < here_we_go < official   (official only when the headline says it is done: official())
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
# «official» needs the HEADLINE to say the deal is done. A word like «official», «confirmed» or «رسمي» anywhere is not enough
# (owner 2026-10-06: «أرسنال وريال مدريد وبرشلونة يدخلون سباق ضم هالاند» went out as رسمي): «عرض رسمي» is an official bid,
# «موعد الإعلان الرسمي» an announcement still to come, «confirmed interest» a rumour. So: the headline opens with the word
# («Oficial: el Madrid ficha a Olise», «رسمياً.. الهلال يعلن…»), or names the completion («completes the signing», «يعلن التعاقد»,
# «رسميا» beside a signing verb), and carries no word of a deal still open (a bid, a race, interest, an announcement to come).
OFFICIAL_OPEN = ["official", "oficial", "officiel", "offiziell", "ufficiale", "رسميا", "رسمي", "done deal"]
OFFICIAL_DONE = ["officially", "completes", "complete the signing", "completed the signing", "completes the signing", "complete signing",
                 "unveiled", "signs for", "has signed", "announce the signing", "announces the signing", "confirm the signing",
                 "confirms the signing", "confirmed the signing", "es oficial", "ficha por", "nuevo jugador del", "s engage", "wechselt zu",
                 "ufficializzato", "يعلن التعاقد", "يعلن ضم", "يعلن رسميا", "ينضم رسميا", "يوقع رسميا", "اعلن التعاقد", "اعلن ضم"]
AR_SIGN = ["يعلن", "اعلن", "ينضم", "انضم", "يوقع", "وقع", "يضم", "ضم", "التعاقد", "تعاقد", "انتقال"]   # with «رسميا» anywhere
NOT_DONE = ["official offer", "official bid", "official approach", "oferta oficial", "offre officielle", "offerta ufficiale",
            "عرض رسمي", "الاعلان الرسمي", "race", "interest", "interested", "monitor", "monitoring", "keen", "eyeing", "target", "linked",
            "rumour", "rumor", "carrera", "interes", "interesse", "interessato", "pourrait", "could", "would", "set to", "close to",
            "سباق", "يراقب", "مهتم", "اهتمام", "يسعى", "يرغب", "يدرس", "مرشح", "يستهدف", "قريب من", "يقترب", "مفاوضات", "عرض",
            "موعد", "قد", "ربما", "تقارير", "تقرير",
            # still to come: «will be officially signed soon» (Arda Güler, 2026-10-06), «fichará por»
            "soon", "will", "expected", "pending", "coming", "tomorrow", "next week", "fichara", "firmara", "signera",
            "قريبا", "سيعلن", "سيوقع", "سينضم", "ينتظر", "مرتقب", "خلال ساعات", "الساعات المقبله", "غدا"]
STAGE_WORDS = [
    ("here_we_go", ["here we go"]),
    ("agreed", ["agreed", "agreement", "deal done", "medical", "acuerdo", "reconocimiento medico", "accord", "einigung", "accordo",
                "اتفاق", "اتفق", "الكشف الطبي", "يقترب"]),
    ("talks", ["talks", "negotiat", "bid", "offer", "approach", "negociacion", "oferta", "negociations", "verhandlungen", "trattativa",
               "مفاوضات", "عرض", "يفاوض", "محادثات"]),
]
_K = {k: [norm(w) for w in ws] for k, ws in KIND_WORDS.items()}
_S = [(s, [norm(w) for w in ws]) for s, ws in STAGE_WORDS]
_OPEN, _DONE, _AR_SIGN, _NOT = ({norm(w) for w in OFFICIAL_OPEN}, [norm(w) for w in OFFICIAL_DONE], {norm(w) for w in AR_SIGN},
                                [norm(w) for w in NOT_DONE])


def official(title):
    """The headline says the deal is done (OFFICIAL_*), and nothing in it says the deal is still open (NOT_DONE)."""
    t = norm(title or "")
    w = t.split()
    if not w or _has(t, _NOT):
        return False
    return w[0] in _OPEN or " ".join(w[:2]) in _OPEN or _has(t, _DONE) or ("رسميا" in w and any(x in _AR_SIGN for x in w))
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
        stage = "official" if official(item.get("title")) else "rumour"
        for s, ws in ([] if stage == "official" else _S):
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
                            "femminile", "lfc women", "arsenal women", "chelsea women", "barca femeni", "femeni", "nwsl", "للسيدات", "السيدات",
                            # the clubs' own hashtags for their women's side, and the women's competitions
                            "awfc", "lfcw", "mcwfc", "cfcw", "mufcw", "fcbfemeni", "uwcl", "wwc", "fifawwc", "barclayswsl", "liga f"]]


def womens(item):
    """True for a women's-team item (a club channel posts both sides; the site's club pages are the men's)."""
    t = " " + norm((item.get("title") or "") + " " + (item.get("desc") or "")[:200]) + " "
    return any(" " + w + " " in t for w in WOMEN)


STAGE_RANK = {None: -1, "rumour": 0, "talks": 1, "agreed": 2, "here_we_go": 3, "official": 4}
