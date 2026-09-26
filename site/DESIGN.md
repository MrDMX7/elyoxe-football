# تيفو — design direction (v2, 2026-09-27)

The owner gave the same brief as elyoxe.com (`~/.claude/uploads/e90232e5-*/800a92c8-elyoxefablebrief.md`), with a different goal:
"a second site with its own football identity. Be creative, give it everything, make it unique." v1 was a carbon copy of
elyoxe.com: the same paper, ink, saffron and Plex. That is the thing to fix.

## My read of the brief
- **What it is:** an Arabic football hub for fans in the UAE. It has live scores in UAE time, and a depth that FotMob and Kooora
  don't give this audience: Emirati context, prayer times, weather, and later the approved analytics.
- **Who uses it:** Emiratis and UAE residents, on a phone, often in the middle of a match or in a majlis. They glance, refresh and share.
- **The site's job:** answer "what's the score" before anyone else, then reward anyone who stays with something no other site has.
- **What overrides the old brief:** Arabic only for now (the owner's decision). The static build stays: 4,200 pages, and Next/R3F is
  not worth a migration now. Tonight's Bahrain v UAE is the first live test, so the fetch and polling logic is not touched.

## The concept: the stand, not the app
A *tifo* is a picture made by thousands of fans, each holding up one coloured card. So the smallest unit of this identity is
**one card: a flat square cell**. Everything is built from it:
- the wordmark
- the live pulse (a card flipping, not a dot)
- the form guide (cards held up: won, drawn, lost)
- the league zones
- the loading state
- the signature mosaic

No radius and no shadows, because a card is a card. Where elyoxe.com is a studio document, Tifo is a stadium at night: a
dark scoreboard over a pale concrete stand.

## Tokens
| name | value | use |
|---|---|---|
| إسمنت (concrete) | `#E9ECE7` | page ground: the stand's concrete, a cool grey-white, *not* elyoxe's warm paper |
| ليل الملعب (night pitch) | `#0A2620` | scoreboard, header, hero: a dark turf green-black |
| طباشير (chalk) | `#F6F7F2` | text and lines on night pitch; pitch markings |
| حبر (ink) | `#0E1512` | text on concrete |
| رمل (dune) | `#B07A3B` | **my team** and selected state. The Gulf note comes from the palette itself, not from pattern decoration |
| نبض (pulse) | `#10A04B` | **live, and only live**: pitch-grass green, "in play" |
| كرت أصفر / كرت أحمر | `#F2C230` / `#D8343F` | **cards only**. Never used for UI states, so a yellow card can't be mistaken for "my team" |
| stone | `#5C6660` | secondary text; chalk lines on concrete `#CDD3CC` |

- **Light only (decided):** dark surfaces are used where a stadium has them (scoreboard, header, hero). A full dark scheme would
  drift into "near-black with one neon".
- **Results:** won = pulse green, drawn = stone, lost = ink with a chalk letter. Red stays reserved for red cards.

## Type (four weights in total, `display=swap`)
- **Noto Kufi Arabic 800:** headings, the wordmark, team names on the scoreboard. Kufic is the Gulf's oldest monumental hand,
  and it reads like stadium signage.
- **Readex Pro 400/600:** body text and Latin player names. It is geometric and its Arabic and Latin match.
- **Barlow Condensed 700:** every score, minute, rank and number. Shirt numbers and scoreboard digits. Western digits always.

## Layout (mobile first, 390 px)
```
┌──────────────────────────────┐  night-pitch header: ▦ تيفو   اليوم  دوري أدنوك  المنتخب  البطولات
│ ▦ تيفو                ☰ nav │
├──────────────────────────────┤
│ ░░▓▓▓▓░░  THE STAND  ░░▒▒▒▒░ │  mosaic canvas: the day's featured match (UAE first). Home colours on the RIGHT,
│ ▓▓ 2 ▓▓   (pixel score)  ▒▒ │  away on the left; score or kickoff time in chalk pixel digits. A touch sends a wave from
│ البحرين     22:00     الإمارات │  the touch point; a goal sends one across the whole stand (right to left = forward in RTL)
├──────────────────────────────┤
│ اليوم ▸ الأحد 27 سبتمبر   ‹ › │
│ كأس الخليج — المجموعة B       │
│ ┌────┐                        │  match row: [scoreboard chip]  home ▪ | ▪ away
│ │22:00│ البحرين  ×  الإمارات  │  chip = night box with Barlow digits; live = pulse box + minute
│ └────┘                        │
└──────────────────────────────┘
Match page:
┌──────────────────────────────┐
│█ team colour   2 : 1   colour █│  scoreboard panel, the club colours as side bars
│  النصر        67'       كلباء  │
│ 90 ────●──■──────●──── 0      │  match timeline: minute 0 on the RIGHT, flowing left (forward in RTL)
├──────────────────────────────┤
│ البطولة | الجولة | الموعد | الملعب │  facts as a labelled grid, never a dotted line
│ 🕌 prayer tile   🌡 weather tile  │
│ [الأحداث] [التشكيلة] [الأرقام] [المواجهات] │
│ lineup on a chalk pitch (squares with shirt numbers), list fallback │
└──────────────────────────────┘
```

## The signature moment (one only)
**The stand.** On the home page, the featured match is a mosaic of cards, like a stand of fans:
- **Colours:** the two clubs' colours, taken from their crests at build time.
- **Load-in:** the cards flip into place once, right to left.
- **Touch:** a touch or pointer sends a "Mexican wave" out from that spot.
- **Goals:** when a goal arrives in the live data, the whole stand does a wave and the digits update.
- **Reduced motion:** the mosaic is static.
- **Performance:** it draws after the match list, so it is never the largest paint, and it is Canvas 2D (~1,500 cells at 60 fps
  on the Fold).
- **Everything else is quiet:** motion anywhere else only answers the visitor.

## Self-review against the generic tells
- **Warm cream with terracotta:** not used. The ground is a cool concrete.
- **Near-black with one neon:** dark appears only as bounded surfaces, and green means live, not decoration.
- **Rounded SaaS cards with shadows:** none. Flat squares, and chalk rules.
- **Numbered 01/02/03 eyebrows:** none. Ranks and rounds are real sequences.
- **Meta lines strung together with middle dots:** removed. v1 had them in the day label, the status and the match facts line;
  these become a labelled grid or separate elements.
- **Tracked-out ALL CAPS:** none; the site is Arabic.
- **An arrow glued to every link:** none.
- **Does it belong only to Tifo?** Compared with FotMob (white cards with rounded corners), Kooora (dense blue portal), SofaScore
  (blue-grey app) and elyoxe.com (warm paper editorial), none of them has card squares, the stand mosaic, a Kufic scoreboard, or
  a timeline that runs right to left.
