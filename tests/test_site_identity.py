"""Who Tifo is, for search engines (owner 2026-10-09): WebSite + Organization JSON-LD on the home page, so results show
«تيفو» and its logo instead of a guessed «tifo.elyoxe.com» (and are not confused with the English «Tifo Football»)."""
import json, os, shutil, subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_site_ld():
    js = "console.log(JSON.stringify(require(process.argv[1] + '/site/lib/site_ld.cjs').siteLd('https://tifo.elyoxe.com')))"
    ld = json.loads(subprocess.run(["node", "-e", js, ROOT], capture_output=True, text=True, encoding="utf-8").stdout)
    web = next(x for x in ld if x["@type"] == "WebSite")
    org = next(x for x in ld if x["@type"] == "Organization")
    assert web["name"] == "تيفو" and "Tifo" in web["alternateName"] and web["url"] == "https://tifo.elyoxe.com/"
    assert web["inLanguage"] == "ar" and web["publisher"]["@id"] == org["@id"]
    assert org["name"] == "Elyoxe" and org["logo"]["url"].endswith(".png") and org["url"] == "https://elyoxe.com/"
    assert set(org["sameAs"]) == {"https://x.com/Elyoxe", "https://www.instagram.com/elyo.xe/", "https://www.tiktok.com/@elyoxe"}
