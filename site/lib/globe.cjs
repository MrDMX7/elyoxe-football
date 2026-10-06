/* «الكرة الحين» (owner bold idea 3, 2026-10-06): what the home page's globe needs, built with the site.
   - land: Natural Earth's 110 m land (public domain) sampled as dots spread evenly over the sphere (a Fibonacci lattice), the
     browser projects them; computed once and kept in site/cache/geo/
   - places: a point per competition of the days the poller lists (v1/all/<ymd>.json), its country's label point (Natural
     Earth's LABEL_Y/X) found through FotMob's country code (its English name, from FotMob's league list) or the competition's
     Arabic country name; for an international competition the national teams instead, by their Arabic name (a national
     team is named after its country), or the site's own country codes for them (teams.json)
   Out: {d: [[lat×10, lon×10]…], lg: {competition: [lat, lon]}, nt: {team: [lat, lon]}, intl: [competition…], ours: [competition…]}
   for src/globe.js. Natural Earth's files and FotMob's list are fetched once and kept in site/cache/geo/ (the list a week). */
"use strict";
const NE = "https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@master/geojson/";
const HOME = { ENG:[52.6, -1.5], SCO:[56.6, -4.2], WAL:[52.3, -3.7], NIR:[54.6, -6.7] };   // FotMob's home nations: inside the UK's shape
const ALIAS = { "turkiye":"turkey", "korea republic":"south korea", "ivory coast":"cote d'ivoire", "dr congo":"democratic republic of the congo",
  "congo dr":"democratic republic of the congo", "czech republic":"czechia", "usa":"united states of america", "united states":"united states of america",
  "bosnia-herzegovina":"bosnia and herzegovina", "north macedonia":"macedonia", "eswatini":"swaziland", "cape verde islands":"cape verde" };

module.exports = async function (X){
  const { fs, path, CACHE, get, teams } = X;
  const D = path.join(CACHE, "geo"); fs.mkdirSync(D, { recursive:true });
  const fetchJson = async (url, file, maxAge) => {
    const f = path.join(D, file);
    if (fs.existsSync(f) && Date.now() - fs.statSync(f).mtimeMs < maxAge) try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch (e){}
    try {
      const r = await fetch(url, { headers:{ "User-Agent":"Mozilla/5.0 (tifo.elyoxe.com)" }, signal:AbortSignal.timeout(30000) });
      if (!r.ok) throw new Error(r.status);
      const j = await r.json(); fs.writeFileSync(f, JSON.stringify(j)); return j;
    } catch (e){ try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch (x){ return null; } }   // a stale copy beats none
  };
  const countries = await fetchJson(NE + "ne_110m_admin_0_countries.geojson", "ne_countries.json", 90 * 864e5);
  const fmList = await fetchJson("https://www.fotmob.com/api/data/allLeagues", "fotmob_all_leagues.json", 7 * 864e5);
  if (!countries) return null;

  // ------------------------------------------------------------------ land dots (once)
  const dotsFile = path.join(D, "land_dots.json");
  let dots = null; try { dots = JSON.parse(fs.readFileSync(dotsFile, "utf8")); } catch (e){}
  if (!dots){
    const land = await fetchJson(NE + "ne_110m_land.geojson", "ne_land.json", 365 * 864e5);
    if (!land) return null;
    const rings = [];
    for (const f of land.features){ const g = f.geometry; const polys = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
      for (const poly of polys){ const r = poly[0]; let a = 180, b = -180, c = 90, d = -90; for (const [x, y] of r){ a = Math.min(a, x); b = Math.max(b, x); c = Math.min(c, y); d = Math.max(d, y); } rings.push({ r, box:[a, b, c, d] }); } }
    const inside = (x, y) => { for (const { r, box } of rings){ if (x < box[0] || x > box[1] || y < box[2] || y > box[3]) continue; let o = false;
      for (let i = 0, j = r.length - 1; i < r.length; j = i++){ const [xi, yi] = r[i], [xj, yj] = r[j]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) o = !o; } if (o) return true; } return false; };
    const N = 16000, G = Math.PI * (3 - Math.sqrt(5)); dots = [];
    for (let i = 0; i < N; i++){ const y = 1 - 2 * (i + 0.5) / N, lat = Math.asin(y) * 180 / Math.PI; let lon = ((i * G) % (2 * Math.PI)) * 180 / Math.PI; if (lon > 180) lon -= 360;
      if (lat > -60 && inside(lon, lat)) dots.push([Math.round(lat * 10), Math.round(lon * 10)]); }
    fs.writeFileSync(dotsFile, JSON.stringify(dots));
  }

  // ------------------------------------------------------------------ places
  const norm = s => String(s || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/[^a-z' ]+/g, " ").replace(/\s+/g, " ").trim();
  const arN = s => String(s || "").replace(/[ً-ٟـ]/g, "").replace(/[أإآ]/g, "ا").replace(/ة/g, "ه").replace(/ى/g, "ي").replace(/\s+/g, " ").trim();
  const byEn = {}, byAr = [], byIso2 = {};
  for (const f of countries.features){ const p = f.properties, pt = [+(+p.LABEL_Y).toFixed(2), +(+p.LABEL_X).toFixed(2)];
    [p.NAME_EN, p.ADMIN, p.NAME_LONG, p.FORMAL_EN, p.NAME].forEach(n => { if (n) byEn[norm(n)] = pt; });
    if (p.NAME_AR) byAr.push([arN(p.NAME_AR), pt]);
    [p.ISO_A2, p.ISO_A2_EH].forEach(c => { if (c && c !== "-99") byIso2[c] = pt; }); }
  const enOf = {}; ((fmList || {}).countries || []).forEach(c => { if (c.ccode) enOf[c.ccode] = c.name; });
  const fromEn = n => { const k = norm(n); return byEn[k] || byEn[ALIAS[k] || ""] || null; };
  const fromAr = n => { const k = arN(n); if (!k) return null; const exact = byAr.find(x => x[0] === k); if (exact) return exact[1];
    const pre = byAr.filter(x => x[0].startsWith(k + " ") || k.startsWith(x[0] + " ")); return pre.length === 1 ? pre[0][1] : null; };   // «الإمارات» → «الإمارات العربية المتحدة»
  const natIso = {}; Object.entries(teams || {}).forEach(([id, t]) => { const c = t && t.country; if (c && c.national && c.iso2) natIso[id] = c.iso2; });

  const days = [-1, 0, 1].map(k => new Date(Date.now() + 4 * 36e5 + k * 864e5).toISOString().slice(0, 10).replace(/-/g, ""));
  const lg = {}, nt = {}, intl = new Set(), ours = new Set(); let placed = 0, missed = 0;
  for (const ymd of days){ const doc = await get(`all/${ymd}.json`, 2); if (!doc) continue;
    for (const L of doc.leagues || []){
      if (L.ours) ours.add(L.id);
      if (L.cc === "INT" || !L.cc){ intl.add(L.id);
        for (const m of L.matches || []) for (const t of [m.home, m.away]){ if (!t || nt[t[0]]) continue;
          const p = (natIso[t[0]] && byIso2[natIso[t[0]]]) || fromAr(t[1]); if (p) nt[t[0]] = p; }
        continue; }
      if (lg[L.id]) continue;
      const p = HOME[L.cc] || fromEn(enOf[L.cc]) || fromAr(L.country_ar);
      if (p){ lg[L.id] = p; placed++; } else missed++;
    } }
  return { d:dots, lg, nt, intl:[...intl], ours:[...ours], stats:{ dots:dots.length, leagues:placed, unplaced:missed, nations:Object.keys(nt).length } };
};
