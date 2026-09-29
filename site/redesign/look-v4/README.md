# Look v4 preview (2026-09-29)

The owner asked «فيه أحلى؟» about the fonts and design, then said «صلح وسو اللي تشوفه مناسب». This folder holds two proposals as a layer over the live CSS. Nothing here is in the live build.

- **Preview:** https://tifo.elyoxe.com/next/ (noindex; robots.txt disallows /next/; deploy.sh never deletes next/*).
  - 11 real pages: home, today, two matches, two leagues, a club, the UAE, a player, /country/sa/, /week/.
  - A switcher at the bottom: «الحالي · أ · ب». `?look=a|b|cur` works too.
- **A «ليل الملعب»** (recommended):
  - Alexandria 700/800 for headings (Readex stays for body text, Barlow Condensed for digits).
  - Near-black ground `#0B0F0E`. Green only for live and your team.
- **B «أخضر أعمق»:**
  - IBM Plex Sans Arabic for everything.
  - The brand green with more depth (`#061A15`) and one warm accent `#D9A05B`.
- **Shared by A and B:**
  - The mosaic becomes a faint band at the top of the hero. The static PNG is off, and the canvas has opacity .32 and fades out by 62%.
  - The home hero drops from 78svh to 56svh.
  - Blocks are a hairline instead of a filled box.
- **Rebuilding the preview:** run a local build, then `python make_next.py <build out dir>`, then upload the `site/` folder with `aws s3 sync … s3://elyoxe-tifo-site-574771023173/next/` and invalidate `/next/*`.
  - Fonts: Google Fonts (OFL). The Arabic and Latin woff2 subsets are self-hosted (see fonts.css).
- **Rollout, after the owner picks one:**
  1. Move the chosen variant's tokens into v3.css `:root`, and its scrim colours into the hardcoded `#0A2620` scrims.
  2. Add the fonts to site/fonts and `FONTS` in build.cjs, and preload them.
  3. Run the gates: inventory, no horizontal scroll at 390/880/1440, FCP.
