"""Player photos (owner item 463, 2026-09-30: «اللعيبة كل الصور»; condition from 2026-09-29: never at the cost of the site's
simplicity). One black-and-white portrait per player where a free photo exists, shown in the player hero over the club's
colour.

    python -m photos.build [--limit N] [--dry] [--pid 30981]

1. who: names/players_ar.json carries a Wikidata id per player (6.8k of 9.6k), matched by name when the Arabic names were
   built, so it can point at a namesake. A photo is taken only when Wikidata says «association football player» AND its
   date of birth equals FotMob's (state/dobs.json + state/squads.json); without a FotMob date, the file name must carry
   the player's surname.
2. licence: Commons metadata per file. Share-Alike (CC BY-SA, GFDL, GPL) is out, the owner's one standing licence rule;
   CC0, public domain and CC BY are in, and the author + licence go in v1/ph/index.json for the credit line.
3. picture: a face must be found (OpenCV) and big enough; the crop is 4:5 around it, grey, 400x500 WebP. No face = no
   photo: a wide match shot cut blindly looks worse than the plain hero.
4. out: s3://<data bucket>/v1/ph/<pid>.webp (served at tifo.elyoxe.com/v1/ph/) + v1/ph/index.json; progress in
   state/photos.json so a run only asks about players not checked in the last 60 days.
"""
import argparse, gzip, io, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
UA = "elyoxe-tifo/0.1 (https://tifo.elyoxe.com; hello@elyoxe.com)"
FOOTBALLER = "Q937857"
RECHECK_DAYS = 60


def http(url, data=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept": "application/json"})
    for i in range(4):
        try:
            return urllib.request.urlopen(req, timeout=timeout).read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and i < 3:
                time.sleep(10 * (i + 1)); continue
            raise


def fold(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def wikidata(qids):
    """qid -> {"img": Commons file name, "dob": "YYYY-MM-DD" or None, "fb": is a footballer}; only qids with an image."""
    out = {}
    for i in range(0, len(qids), 250):
        chunk = qids[i:i + 250]
        q = ("SELECT ?p ?img ?dob ?fb WHERE { VALUES ?p { %s } ?p wdt:P18 ?img . OPTIONAL { ?p wdt:P569 ?dob } "
             "BIND(EXISTS { ?p wdt:P106 wd:%s } AS ?fb) }") % (" ".join("wd:" + x for x in chunk), FOOTBALLER)
        r = json.loads(http("https://query.wikidata.org/sparql", urllib.parse.urlencode({"query": q, "format": "json"}).encode()))
        for b in r["results"]["bindings"]:
            qid = b["p"]["value"].rsplit("/", 1)[1]
            if qid in out:
                continue
            out[qid] = {"img": urllib.parse.unquote(b["img"]["value"].rsplit("/", 1)[1]).replace("_", " "),
                        "dob": b.get("dob", {}).get("value", "")[:10] or None, "fb": b["fb"]["value"] == "true"}
        time.sleep(1)
    return out


def commons(files):
    """file name -> {"license", "short", "artist", "thumb"} from Commons (50 titles a request)."""
    out = {}
    for i in range(0, len(files), 50):
        chunk = files[i:i + 50]
        qs = urllib.parse.urlencode({"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "extmetadata|url",
                                     "iiurlwidth": 800, "titles": "|".join("File:" + f for f in chunk)})
        r = json.loads(http("https://commons.wikimedia.org/w/api.php?" + qs))
        norm = {n["to"]: n["from"] for n in r.get("query", {}).get("normalized", [])}
        for pg in r.get("query", {}).get("pages", {}).values():
            ii = (pg.get("imageinfo") or [{}])[0]
            md = ii.get("extmetadata") or {}
            val = lambda k: re.sub(r"<[^>]+>", "", (md.get(k) or {}).get("value", "")).strip()
            name = norm.get(pg.get("title"), pg.get("title", ""))[5:]
            out[name] = {"license": val("License").lower(), "short": val("LicenseShortName"), "artist": val("Artist")[:120],
                         "thumb": ii.get("thumburl"), "page": ii.get("descriptionurl")}
        time.sleep(0.5)
    return out


def free(lic):
    """True for a licence without Share-Alike (the owner's rule): CC0, public domain, CC BY."""
    l, s = lic["license"], lic["short"].lower()
    if "sa" in re.split(r"[-\s]", l) or "sa" in re.split(r"[-\s]", s) or any(x in l + " " + s for x in ("gfdl", "gpl", "share")):
        return False
    return l.startswith("cc0") or l.startswith("pd") or "public domain" in s or l.startswith("cc-by") or s.startswith("cc by")


_FACE = None


def portrait(raw):
    """Image bytes -> 400x500 grey WebP around the largest face, or None (no face / too small)."""
    # YuNet (opencv_zoo, photos/face_yunet.onnx): the Haar cascade took a knee for a face on the first test sheet
    global _FACE
    import cv2, numpy as np
    from PIL import Image, ImageOps
    if _FACE is None:
        _FACE = cv2.FaceDetectorYN.create(os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_yunet.onnx"), "", (320, 320), 0.88)
    rgb = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    im = rgb.convert("L")
    bgr = np.array(rgb)[:, :, ::-1].copy()
    _FACE.setInputSize((bgr.shape[1], bgr.shape[0]))
    _, faces = _FACE.detect(bgr)
    if faces is None or not len(faces):
        return None
    x, y, w, h = [int(v) for v in max(faces, key=lambda f: f[2] * f[3])[:4]]
    W, H = im.size
    if w < W * 0.07:                               # a face lost in a crowd or a wide stadium shot
        return None
    cw = min(W, int(w * 3.2)); ch = int(cw * 5 / 4)  # head and shoulders
    if ch > H:
        ch = H; cw = int(ch * 4 / 5)
    cx, cy = x + w / 2, y + h * 0.95                 # the face sits in the upper third
    left = int(min(max(0, cx - cw / 2), W - cw)); top = int(min(max(0, cy - ch * 0.42), H - ch))
    out = ImageOps.autocontrast(im.crop((left, top, left + cw, top + ch)).resize((400, 500), Image.LANCZOS), cutoff=1)
    buf = io.BytesIO(); out.save(buf, "WEBP", quality=74, method=6)
    return buf.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0); ap.add_argument("--dry", action="store_true"); ap.add_argument("--pid")
    a = ap.parse_args(argv)
    store = Store(S3Backend(BUCKET))
    names = json.load(open(os.path.join(HERE, "names", "players_ar.json"), encoding="utf-8"))
    dobs = dict(store.get_state("dobs.json", {}) or {})
    for groups in (store.get_state("squads.json", {}) or {}).values():
        for g in groups or []:
            for pl in g.get("players") or []:
                if pl.get("dob"):
                    dobs[str(pl["id"])] = pl["dob"][:10]
    st = store.get_state("photos.json", {}) or {}
    now = datetime.now(timezone.utc); cut = (now - timedelta(days=RECHECK_DAYS)).isoformat()
    todo = [pid for pid, v in names.items() if v.get("qid") and (a.pid == pid or (not a.pid and (st.get(pid, {}).get("checked") or "") < cut))]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(todo)} players to check ({len(dobs)} FotMob birth dates)")
    wd = wikidata(sorted({names[p]["qid"] for p in todo}))
    cand = {}
    for pid in todo:
        v, w = names[pid], wd.get(names[pid]["qid"])
        rec = {"qid": v["qid"], "checked": now.isoformat()[:19] + "Z"}
        if not w:
            rec["status"] = "no image"
        elif not w["fb"]:
            rec["status"] = "not a footballer (namesake)"
        elif dobs.get(pid) and w["dob"] and dobs[pid] != w["dob"]:
            rec["status"] = f"birth date differs ({dobs[pid]} vs {w['dob']})"
        elif not (dobs.get(pid) and w["dob"]) and fold(v["latin"]).split()[-1:] and fold(v["latin"]).split()[-1] not in fold(w["img"]):
            rec["status"] = "unverified (no birth date, name not in file)"
        else:
            rec["file"] = w["img"]; cand[pid] = w["img"]
        st[pid] = dict(st.get(pid, {}), **rec)
    print(f"{len(cand)} identity-checked photos; licences next")
    lic = commons(sorted(set(cand.values())))
    index = store.get_json("ph/index.json") or {"players": {}}
    made = 0
    for pid, f in cand.items():
        L = lic.get(f)
        if not L or not L.get("thumb"):
            st[pid]["status"] = "no Commons record"; continue
        st[pid]["license"] = L["short"] or L["license"]
        if not free(L):
            st[pid]["status"] = "share-alike"; index["players"].pop(pid, None); continue
        try:
            pic = portrait(http(L["thumb"], timeout=60))
        except Exception as e:
            st[pid]["status"] = f"download failed: {str(e)[:60]}"; continue
        if not pic:
            st[pid]["status"] = "no clear face"; index["players"].pop(pid, None); continue
        st[pid]["status"] = "ok"; made += 1
        index["players"][pid] = {"artist": L["artist"], "license": L["short"] or L["license"], "page": L["page"]}
        if not a.dry:
            store.b.put(f"v1/ph/{pid}.webp", pic, "image/webp", "public, max-age=2592000")
        else:
            open(os.path.join(os.environ.get("TEMP", "/tmp"), f"ph-{pid}.webp"), "wb").write(pic)
    index["generated"] = now.isoformat()[:19] + "Z"
    from collections import Counter
    print(json.dumps(Counter(v.get("status", "?").split(" (")[0] for k, v in st.items() if k in set(todo)), ensure_ascii=False))
    print(f"{made} portraits made; {len(index['players'])} in the index")
    if not a.dry:
        store.put_json("ph/index.json", index, cache="warm")
        store.put_state("photos.json", st)
    return 0


if __name__ == "__main__":
    sys.exit(main())
