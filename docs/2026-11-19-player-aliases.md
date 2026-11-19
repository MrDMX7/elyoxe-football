# Player aliases: the graph publishes them, the goal-clip matcher reads them

Owner, 2026-11-19: «نسوي للاعبين أسامي aliases، نسق مع جلسة تطوير تيفو».

## Why

`news/media.py` matches official goal clips to goals by the scorer's name in the post's title. Broadcasters and clubs write
names differently from our single Arabic name, and those goals end up with no clip and no TikTok post. The morning report
(`news/media_missed.py`, state `news/media-missed.json`, in the 08:00 email) showed that every miss on 11-19 was a name:

| Ours | What they wrote |
|---|---|
| سيرجينيو | سيرجيو بيريرا (Abu Dhabi Sports, Dubai Sports) |
| هوغو | هوجو نيتو |
| منذر تيمين | منذر طمين |
| عبد الله زياني | عبد الله الزياني |
| ماركوس أندريه | ماركوس مايا (Al Ain, Abu Dhabi Sports) |

Already done on the matcher side (football 1f4d187 … this commit):
- `media.loose()` matches a whole name spelt another way: ط/ت, غ/ج/ق, «ال», one long vowel or a final «ه» more or less.
  That covers طمين, الزياني and عوض/عواد.
- The people aliases in `news/aliases.yaml` (by hand).

What's left needs data rather than spelling rules: a different name for the same player (سيرجيو بيريرا for Serginho,
ماركوس مايا for Marcos André), and a short single name like هوغو.

## The file (graph side)

`s3://elyoxe-football-574771023173-ap-south-1/state/graph/player_aliases_ar.json.gz`, gzip JSON, rebuilt by the nightly
`graph` stage:

```json
{"generated": "2026-11-20T00:10:00Z",
 "players": {"1572471": ["ماركوس أندريه", "ماركوس مايا"], "...": []}}
```

- Key: the **FotMob player id**, the id in match files and in `v1/media/<match>.json` goal keys.
- Value: every Arabic form held for that player, deduplicated, in any order. Leave out forms that are only a first name.
- Possible sources: `player.name_ar`; the other `name_ar` values the `conflict` table kept from other sources; Wikidata's
  Arabic label and `skos:altLabel`@ar; FotMob's Arabic map; `names/players_ar.json`; the `people:` section of
  `news/aliases.yaml`; and the learned file below.

`media.load_names()` reads it on every run when it exists (`media.PLAYER_ALIASES`). Each form is used like the dictionary's
own name: a full name names the player, and a long surname names him on its own. A missing or broken file changes nothing.

## Learned forms (matcher side, next)

Once the graph file exists, the matcher can record the names official accounts used for goals it confirmed by other
evidence: the club's own channel plus the minute, the score, or the goal number. It would write them to
`state/news/media-learned-aliases.json` as `{"<fotmob pid>": {"<form>": {"n": 3, "last": iso, "src": "x_adsportstv"}}}`,
for the graph to fold in with provenance `learned:media`.
