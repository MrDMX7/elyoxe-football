"""Build news/nations.json: what national teams are called in the titles of official videos, in the seven languages of the
channels news/media.py reads (Arabic, English, Spanish, French, German, Italian, Portuguese).

   python news/tools/nations.py        # needs `babel` (CLDR); run on the laptop, the output is committed

CLDR gives the formal names («المملكة العربية السعودية», «Congo - Kinshasa»); FOOTBALL adds the forms the channels actually
write («السعودية», «DR Congo», «USMNT», «Czech Republic») and the nicknames that name only one team («النشامى», «Socceroos»).
A nickname that two teams share («الأخضر»: Saudi Arabia and Cape Verde's «الرأس الأخضر»; «La Roja»: Spain and Chile) is left out.
FotMob's own English names map to a code in `fotmob` (teams.json has no country for some national teams: Czechia, Ivory Coast)."""
import json, os, re, sys
from babel import Locale

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANGS = ["en", "ar", "es", "fr", "de", "it", "pt"]

# the forms football titles use, beyond CLDR (checked against beIN / tod / AD Sports / federation uploads, 2026-09-30)
FOOTBALL = {
    "AE": ["UAE", "Emirates", "الإمارات", "الامارات", "المنتخب الإماراتي", "منتخب الإمارات", "EAU", "Emiratos"],
    "SA": ["Saudi Arabia", "KSA", "Saudi", "السعودية", "المنتخب السعودي", "منتخب السعودية", "Arabia Saudita", "Arabie Saoudite"],
    "QA": ["Qatar", "قطر", "المنتخب القطري", "العنابي", "Catar"],
    "KW": ["Kuwait", "الكويت", "المنتخب الكويتي", "Koweït"],
    "BH": ["Bahrain", "البحرين", "المنتخب البحريني", "Bahreïn", "Baréin"],
    "OM": ["Oman", "عمان", "عُمان", "المنتخب العماني", "سلطنة عمان"],
    "IQ": ["Iraq", "العراق", "المنتخب العراقي", "أسود الرافدين", "اسود الرافدين", "Irak"],
    "YE": ["Yemen", "اليمن", "المنتخب اليمني", "Yémen"],
    "JO": ["Jordan", "الأردن", "الاردن", "المنتخب الأردني", "المنتخب الاردني", "النشامى", "Jordania", "Jordanie"],
    "SY": ["Syria", "سوريا", "سورية", "المنتخب السوري", "نسور قاسيون", "Siria", "Syrie"],
    "LB": ["Lebanon", "لبنان", "المنتخب اللبناني", "رجال الأرز", "Líbano", "Liban"],
    "PS": ["Palestine", "Palestina", "فلسطين", "المنتخب الفلسطيني", "الفدائي"],
    "EG": ["Egypt", "مصر", "المنتخب المصري", "منتخب مصر", "الفراعنة", "Pharaohs", "Egipto", "Égypte"],
    "LY": ["Libya", "ليبيا", "المنتخب الليبي", "Libia", "Libye"],
    "TN": ["Tunisia", "تونس", "المنتخب التونسي", "نسور قرطاج", "Eagles of Carthage", "Túnez", "Tunisie"],
    "DZ": ["Algeria", "الجزائر", "المنتخب الجزائري", "محاربو الصحراء", "محاربي الصحراء", "Desert Warriors", "Fennecs", "Argelia", "Algérie"],
    "MA": ["Morocco", "المغرب", "المنتخب المغربي", "أسود الأطلس", "اسود الاطلس", "Atlas Lions", "Marruecos", "Maroc"],
    "MR": ["Mauritania", "موريتانيا", "المنتخب الموريتاني", "Mauritanie"],
    "SD": ["Sudan", "السودان", "المنتخب السوداني", "صقور الجديان", "Soudan"],
    "SO": ["Somalia", "الصومال", "Somalie"],
    "DJ": ["Djibouti", "جيبوتي", "Yibuti"],
    "KM": ["Comoros", "جزر القمر", "Comores", "Comoras"],
    "US": ["USA", "USMNT", "United States", "U.S.", "EEUU", "EE.UU.", "Estados Unidos", "أمريكا", "امريكا", "الولايات المتحدة", "المنتخب الأمريكي", "États-Unis"],
    "GB-ENG": ["England", "Inglaterra", "Angleterre", "Inghilterra", "إنجلترا", "انجلترا", "إنكلترا", "Three Lions"],
    "GB-SCT": ["Scotland", "Escocia", "Écosse", "Schottland", "Scozia", "اسكتلندا", "إسكتلندا"],
    "GB-WLS": ["Wales", "Gales", "Pays de Galles", "Galles", "ويلز"],
    "GB-NIR": ["Northern Ireland", "Irlanda del Norte", "Irlande du Nord", "Nordirland", "أيرلندا الشمالية", "ايرلندا الشمالية"],
    "IE": ["Republic of Ireland", "Ireland", "Irlanda", "Irlande", "أيرلندا", "ايرلندا"],
    "KR": ["South Korea", "Korea Republic", "Korea", "كوريا الجنوبية", "كوريا", "Taeguk Warriors", "Corea del Sur"],
    "KP": ["North Korea", "Korea DPR", "كوريا الشمالية"],
    "JP": ["Japan", "اليابان", "Samurai Blue", "Japón", "Japon"],
    "CN": ["China PR", "China", "الصين"],
    "AU": ["Australia", "أستراليا", "استراليا", "Socceroos", "Australie"],
    "CI": ["Ivory Coast", "Côte d'Ivoire", "Cote d'Ivoire", "ساحل العاج", "كوت ديفوار", "Costa de Marfil"],
    "CD": ["DR Congo", "Congo DR", "RD Congo", "RDC", "الكونغو الديمقراطية", "الكونغو الديموقراطية"],
    "CG": ["Congo", "Congo Brazzaville", "الكونغو", "الكونغو برازافيل"],
    "CZ": ["Czech Republic", "Czechia", "جمهورية التشيك", "التشيك", "Česko", "República Checa", "République tchèque"],
    "CV": ["Cape Verde", "Cabo Verde", "Cap-Vert", "الرأس الأخضر"],
    "ZA": ["South Africa", "Bafana Bafana", "جنوب أفريقيا", "جنوب افريقيا", "Sudáfrica", "Afrique du Sud"],
    "NG": ["Nigeria", "نيجيريا", "Super Eagles"],
    "GH": ["Ghana", "غانا", "Black Stars"],
    "SN": ["Senegal", "السنغال", "Sénégal", "Lions of Teranga"],
    "CM": ["Cameroon", "الكاميرون", "Cameroun", "Camerún", "Indomitable Lions"],
    "SS": ["South Sudan", "جنوب السودان", "Soudan du Sud", "Sudán del Sur"],
    "CF": ["Central African Republic", "CAR", "جمهورية أفريقيا الوسطى", "أفريقيا الوسطى", "Centrafrique"],
    "GQ": ["Equatorial Guinea", "غينيا الاستوائية", "Guinea Ecuatorial", "Guinée équatoriale"],
    "GW": ["Guinea-Bissau", "Guinea Bissau", "غينيا بيساو", "Guinée-Bissau"],
    "SZ": ["Eswatini", "Swaziland", "إسواتيني", "سوازيلاند"],
    "TR": ["Türkiye", "Turkey", "تركيا", "Turquía", "Turquie", "Türkei"],
    "IR": ["Iran", "IR Iran", "إيران", "ايران", "Irán"],
    "BA": ["Bosnia and Herzegovina", "Bosnia-Herzegovina", "Bosnia", "البوسنة والهرسك", "البوسنة"],
    "MK": ["North Macedonia", "Macedonia", "مقدونيا الشمالية"],
    "XK": ["Kosovo", "كوسوفو"],
    "NL": ["Netherlands", "Holland", "هولندا", "Países Bajos", "Pays-Bas", "Niederlande", "Paesi Bassi", "Oranje"],
    "DE": ["Germany", "ألمانيا", "المانيا", "Alemania", "Allemagne", "Deutschland", "Germania", "DFB-Team"],
    "ES": ["Spain", "إسبانيا", "اسبانيا", "España", "Espagne", "Spanien", "Spagna"],
    "FR": ["France", "فرنسا", "Francia", "Frankreich", "Les Bleus"],
    "IT": ["Italy", "إيطاليا", "ايطاليا", "Italia", "Italie", "Italien", "Azzurri"],
    "PT": ["Portugal", "البرتغال", "Portogallo"],
    "BR": ["Brazil", "البرازيل", "Brasil", "Brésil", "Brasilien", "Brasile", "Seleção", "Selecao"],
    "AR": ["Argentina", "الأرجنتين", "الارجنتين", "Argentine", "Argentinien", "Albiceleste"],
    "MX": ["Mexico", "México", "المكسيك", "Mexique", "Messico", "El Tri"],
    "HR": ["Croatia", "كرواتيا", "Croacia", "Croatie", "Kroatien", "Croazia"],
    "RU": ["Russia", "روسيا", "Rusia", "Russie", "Russland"],
    "NZ": ["New Zealand", "نيوزيلندا", "All Whites", "Nueva Zelanda"],
    "NC": ["New Caledonia", "كاليدونيا الجديدة", "Nouvelle-Calédonie"],
    "HK": ["Hong Kong", "هونغ كونغ", "Hong Kong, China"],
    "TW": ["Chinese Taipei", "تايبيه الصينية", "تايوان"],
    "VN": ["Vietnam", "Viet Nam", "فيتنام"],
    "TL": ["Timor-Leste", "East Timor", "تيمور الشرقية"],
    "BN": ["Brunei", "Brunei Darussalam", "بروناي"],
    "KG": ["Kyrgyzstan", "Kyrgyz Republic", "قيرغيزستان"],
}
# FotMob's English name when it is not CLDR's (teams.json national teams without a country block)
FOTMOB = {"USA": "US", "England": "GB-ENG", "Scotland": "GB-SCT", "Wales": "GB-WLS", "Northern Ireland": "GB-NIR", "Czechia": "CZ",
          "Ivory Coast": "CI", "DR Congo": "CD", "Congo": "CG", "South Korea": "KR", "North Korea": "KP", "Cape Verde": "CV",
          "Republic of Ireland": "IE", "Türkiye": "TR", "Turkey": "TR", "Palestine": "PS", "Eswatini": "SZ", "Chinese Taipei": "TW",
          "Hong Kong": "HK", "China": "CN", "UAE": "AE", "Bosnia and Herzegovina": "BA", "North Macedonia": "MK", "Kosovo": "XK",
          "Curacao": "CW", "St. Kitts and Nevis": "KN", "St. Lucia": "LC", "St. Vincent / Grenadines": "VC", "Timor-Leste": "TL",
          "Brunei": "BN", "Gambia": "GM", "Guinea-Bissau": "GW", "Central African Republic": "CF", "Macau": "MO", "Kyrgyzstan": "KG"}


def clean(n):
    """«Congo - Kinshasa» -> «Congo - Kinshasa», «Congo»; «Myanmar (Burma)» -> both; «Côte d’Ivoire» -> with a plain apostrophe."""
    n = n.replace("’", "'").strip()
    out = {n}
    for sep in (" - ", " (", ", "):
        if sep in n:
            out.add(n.split(sep)[0].strip())
    return {re.sub(r"\s+", " ", x) for x in out if len(x) >= 3}


def main():
    names = {}
    for lang in LANGS:
        for code, n in Locale.parse(lang).territories.items():
            if not re.fullmatch(r"[A-Z]{2}", code) or code in ("EU", "EZ", "UN", "QO", "ZZ"):
                continue
            names.setdefault(code, set()).update(clean(n))
    for code, extra in FOOTBALL.items():
        names.setdefault(code, set()).update(x.replace("’", "'") for x in extra)
    # the UK as a whole never plays; its four nations do (above)
    names.pop("GB", None)
    en = {}
    for code, n in Locale.parse("en").territories.items():
        if re.fullmatch(r"[A-Z]{2}", code):
            for x in clean(n):
                en.setdefault(x, code)
    fotmob = dict(FOTMOB)
    teams = os.path.join(HERE, "..", "site", "cache", "teams.json")
    if len(sys.argv) > 1:
        teams = sys.argv[1]
    if os.path.exists(teams):      # every national team FotMob names: code from its country block, else from the name
        for t in (json.load(open(teams, encoding="utf-8")).get("teams") or {}).values():
            c = t.get("country") or {}
            if c.get("national") and c.get("iso2"):
                fotmob.setdefault(t["name"], c["iso2"])
            elif t.get("name") in en and not c:
                fotmob.setdefault(t["name"], en[t["name"]])
    out = {"about": "news/tools/nations.py: CLDR + football forms; FotMob English name -> code", "fotmob": dict(sorted(fotmob.items())),
           "en": {k: v for k, v in sorted(en.items())}, "names": {k: sorted(v) for k, v in sorted(names.items())}}
    with open(os.path.join(HERE, "nations.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=0, sort_keys=False)
        f.write("\n")
    print(f"{len(out['names'])} codes, {len(out['fotmob'])} FotMob names")


if __name__ == "__main__":
    main()
