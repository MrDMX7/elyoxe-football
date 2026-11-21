"""Every Arabic player name checked against a second source made by people: FotMob's own Arabic names
(www.fotmob.com/api/translationmapping?locale=ar, «Participants»: 63k players and clubs by FotMob id). Owner 2026-11-21:
«شوف طريقة نتأكد من أسامي اللاعبين». FotMob's is never written over ours (it holds «المعماري» for «المعمري», and full legal
names): a name is «agree» (the same, written alike), «consistent» (FotMob's full name holds ours: first name and family name),
«spelling» (the same name in another transliteration: أغوديلو/أجوديلو), «differs» (a person decides; both go to
names/review_fotmob.csv, the UAE's first) or «none» (FotMob has no Arabic for him).

    python -m names.verify            # writes names/verify_players.json and names/review_fotmob.csv
"""
import csv, json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://www.fotmob.com/api/translationmapping?locale=ar"


def _norm(s):
    s = (s or "").replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    s = re.sub(r"(?<!\S)(عبد|ابو) (?=\S)", r"\1", s)                    # «عبد الله» and «عبدالله» are one name
    return "".join(ch for ch in s if not "ً" <= ch <= "ْ")          # short vowels and shadda are writing


LOOSE = str.maketrans({"غ": "ج", "ق": "ج", "ث": "ت", "ذ": "ز", "ظ": "ز", "ص": "س", "ض": "د", "ا": None, "و": None, "ي": None, "ه": None,
                       "ء": None, "ئ": None, "ؤ": None})


def _loose(t):
    """A word's transliteration skeleton: أغوديلو and أجوديلو, فكتور and فيكتور, الشاذلي and شاذلي are one"""
    t = t[2:] if t.startswith("ال") and len(t) > 3 else t
    return t.translate(LOOSE)


def _holds(a, b):
    """every word of a in b, the first names the same (a full name holds the short one)"""
    return bool(a) and a[0] == b[0] and all(t in b for t in a)


def classify(ours, fotmob):
    """agree | consistent | spelling | differs | none"""
    if not fotmob:
        return "none"
    a, b = _norm(ours).split(), _norm(fotmob).split()
    if "".join(a) == "".join(b):
        return "agree"
    if len(a) >= 2 and _holds(a, b):
        return "consistent"
    la, lb = [_loose(t) for t in a], [_loose(t) for t in b]
    if a and b and ("".join(la) == "".join(lb) or _holds(la, lb)):
        return "spelling"
    return "differs"


def report(ours, fm, first=frozenset()):
    """{counts, status {id: kind}, review [the «differs», `first` ids first]} for names/players_ar.json against FotMob's"""
    counts = {"agree": 0, "consistent": 0, "spelling": 0, "differs": 0, "none": 0, "approved": 0}
    status, review = {}, []
    for pid, v in ours.items():
        k = "approved" if v.get("owner_ok") else classify(v.get("ar"), fm.get(str(pid)))     # the owner's word is final
        counts[k] += 1
        status[str(pid)] = k
        if k in ("differs", "spelling"):
            review.append({"id": str(pid), "kind": k, "latin": v.get("latin"), "ours": v.get("ar"), "fotmob": fm.get(str(pid)), "source": v.get("source")})
    review.sort(key=lambda r: (r["id"] not in first, r["kind"] != "differs" if r["id"] not in first else 0, r["source"] == "manual", r["id"]))
    return {"counts": counts, "status": status, "review": review}


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "identity"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())["Participants"]


def main():
    ours = json.load(open(os.path.join(HERE, "players_ar.json"), encoding="utf-8"))
    uae = {r["id"] for r in csv.DictReader(open(os.path.join(HERE, "review_uae.csv"), encoding="utf-8"))}
    out = report(ours, fetch(), first=uae)
    with open(os.path.join(HERE, "verify_players.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"counts": out["counts"], "status": out["status"]}, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    with open(os.path.join(HERE, "review_fotmob.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, ["id", "kind", "latin", "ours", "fotmob", "source", "uae"], lineterminator="\n")
        w.writeheader()
        for r in out["review"]:
            w.writerow({**r, "uae": "1" if r["id"] in uae else ""})
    print(json.dumps(out["counts"]), flush=True)


if __name__ == "__main__":
    sys.exit(main())
