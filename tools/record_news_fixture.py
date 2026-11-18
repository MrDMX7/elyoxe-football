"""Writes tests/fixtures/articles/news_state.json: three stories of the live journal and their items, in this order:
a transfer story carried by 3+ outlets (one with an official item if there is one), an «other» story with 2+ outlets, and
an injury / statement / presser story with one outlet. Reads the journal's state from S3 with the repo's own Store."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from store import Store, S3Backend  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "articles" / "news_state.json"
st = Store(S3Backend("elyoxe-football-574771023173-ap-south-1")).get_state("news/state.json")
items, stories = st["items"], st["stories"]
outlets = lambda s: len({items[i]["source"] for i in s["items"] if i in items})
official = lambda s: any(items.get(i, {}).get("tier") == "official" for i in s["items"])
newest = sorted(stories.values(), key=lambda s: s["last_at"], reverse=True)
transfers = [s for s in newest if s["kind"] == "transfer" and outlets(s) >= 3]
pick = [next((s for s in transfers if official(s)), transfers[0] if transfers else None),
        next((s for s in newest if s["kind"] == "other" and outlets(s) >= 2), None),
        next((s for s in newest if s["kind"] in ("injury", "statement", "presser") and outlets(s) == 1), None)]
if None in pick:
    sys.exit(f"the live journal has no story of every shape: {[bool(p) for p in pick]}")
keep = {i for s in pick for i in s["items"] if i in items}
named = {str(e[1]) for s in pick for e in s["anchor"] if e[0] == "player"}
pteam = {k: v for k, v in (st.get("pteam") or {}).items() if k in named}
OUT.write_text(json.dumps({"stories": {s["id"]: s for s in pick}, "items": {i: items[i] for i in keep}, "pteam": pteam},
                          ensure_ascii=False), encoding="utf-8", newline="\n")
print([(s["id"], s["kind"], outlets(s), official(s)) for s in pick])
