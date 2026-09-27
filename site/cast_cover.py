"""Tifo Cast cover art (354): 3000x3000 JPEG for Apple Podcasts / Spotify, in the Tifo identity (night pitch, the 3x3
card mark, Kufi signage). Written once to cache/cast_cover.jpg; build.cjs copies it to out/cast/cover.jpg."""
import os, random
from PIL import Image, ImageDraw
import og   # fonts, colours and the mark live there

S = 3000
def main():
    out = os.path.join(og.CACHE, "cast_cover.jpg")
    if os.path.exists(out): return out
    im = Image.new("RGB", (S, S), og.NIGHT); d = ImageDraw.Draw(im)
    og.stand(d, 0, 0, S, 900, 75, [og.NIGHT2, og.DUNE], None, "tifo-cast")   # the stand of fan cards across the top
    d.rectangle([0, 900, S, S], fill=og.NIGHT)
    og.mark(d, S / 2 - 330, 1150, 170)
    d.text((S / 2, 2020), "تيفو كاست", font=og.KUFI(380), fill=og.CHALK, anchor="mm", direction="rtl", language="ar")
    d.text((S / 2, 2420), "حامد ومها يسولفون عن الكورة", font=og.TXT(150), fill=(185, 199, 192), anchor="mm", direction="rtl", language="ar")
    d.text((S / 2, 2800), "tifo.elyoxe.com", font=og.DIG(130), fill=og.DUNE, anchor="mm")
    im.save(out, quality=90, optimize=True); return out

if __name__ == "__main__":
    print(main())
