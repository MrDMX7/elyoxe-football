# Build the /next/ look preview from a local build: the same pages, the live CSS, plus look.css and a switcher.
import os, re, shutil, sys
OUT = sys.argv[1]                      # the local build (tifo-out)
HERE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(HERE, "site")       # uploaded to s3://…/next/
PAGES = ["", "today/", "m/1000020522/", "m/4283863/", "c/uae-pro-league/", "c/saudi-pro-league/", "t/102124/", "t/5789/",
         "p/1134206/", "country/sa/", "week/"]
if os.path.exists(DST): shutil.rmtree(DST)
os.makedirs(DST)
shutil.copytree(os.path.join(OUT, "assets"), os.path.join(DST, "assets"))
shutil.copytree(os.path.join(HERE, "fonts"), os.path.join(DST, "fonts"), ignore=shutil.ignore_patterns("*.css"))
os.makedirs(os.path.join(DST, "look"))
shutil.copy(os.path.join(HERE, "fonts", "fonts.css"), os.path.join(DST, "look", "fonts.css"))
shutil.copy(os.path.join(HERE, "look", "look.css"), os.path.join(DST, "look", "look.css"))
HEAD = ('<link rel="stylesheet" href="/next/look/fonts.css"><link rel="stylesheet" href="/next/look/look.css">'
        '<script>(function(){var q=new URLSearchParams(location.search).get("look"),v=q;try{v=v||localStorage.getItem("tifo.look")}catch(e){}v=v||"a";if(v!=="cur")document.documentElement.dataset.look=v})()</script>')
PICK = ('<div id="lookpick"><div role="group" aria-label="اختار الشكل"><button type="button" data-l="cur">الحالي</button>'
        '<button type="button" data-l="a">أ · ليل الملعب</button><button type="button" data-l="b">ب · أخضر أعمق</button></div></div>'
        '<script>(function(){var h=document.documentElement,bs=document.querySelectorAll("#lookpick button");'
        'function set(v){if(v==="cur")delete h.dataset.look;else h.dataset.look=v;try{localStorage.setItem("tifo.look",v)}catch(e){}'
        'bs.forEach(function(b){b.setAttribute("aria-pressed",String(b.dataset.l===v))})}'
        'bs.forEach(function(b){b.onclick=function(){set(b.dataset.l)}});set(h.dataset.look||"cur")})()</script>')
for p in PAGES:
    src = os.path.join(OUT, p, "index.html")
    h = open(src, encoding="utf-8").read()
    h = h.replace('"/assets/', '"/next/assets/')
    h = re.sub(r'<link rel="canonical" href="[^"]*">', '<meta name="robots" content="noindex">', h, count=1)
    if 'name="robots" content="noindex"' not in h:
        h = h.replace("<title>", '<meta name="robots" content="noindex"><title>', 1)
    for q in PAGES:                    # the preview pages link to each other
        h = h.replace(f'href="/{q}"', f'href="/next/{q}"')
    h = h.replace("</head>", HEAD + "</head>", 1).replace("</body>", PICK + "</body>", 1)
    d = os.path.join(DST, p); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8", newline="\n").write(h)
print("pages", len(PAGES), "->", DST)
