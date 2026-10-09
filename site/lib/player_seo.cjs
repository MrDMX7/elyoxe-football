/* The /p/ player pages Google sends visitors to (owner item 11, 2026-10-09). What a crawler reads before any script runs:
     title()          promises «إحصائياته وأهدافه هذا الموسم» only when the page carries this season's numbers
     intro()          one or two plain sentences from the data (no model): who he is, then this season or his career
     person()         schema.org Person, the same shape /db/player/ pages carry (lib/world_stage.cjs)
     seasonRow()      this season's row from his FotMob career, for the «هالموسم» tiles when the league file has no card
   and the career cache behind them: v1/player/<id>/profile.json for every /p/ player, read once per data generation (the
   FotMob profiles' `generated`), BUDGET per run, trimmed into cache/pcareer/careers.json. The page draws the career from it;
   the browser still refreshes the pane from the live file. tests/test_player_seo.py. */
"use strict";
const fs = require("fs"), path = require("path");

const CURRENT = /^(2026\/2027|2026)$/;   // the season under way (October 2026): a European season or a calendar one

// [season, team id, team name, apps, goals, assists, rating]: the columns P.playerCareer and the /db/player/ table read
const cols = s => (s || []).map(x => x.slice(0, 7));
function trimProfile(p){
  if (!p) return null;
  const C = p.career || {};
  // m: his clubs [id, name, start, end, apps, FotMob's transfer type] for U.careerMoves (spec 2026-10-09 transfers, phase 2)
  const tk = t => t && typeof t === "object" ? t.localizationKey || null : t || null;
  return { s:cols((C.senior || {}).seasons), n:cols((C["national team"] || C.national || {}).seasons), m:((C.senior || {}).teams || []).map(r => [r[0], r[1], r[2], r[3], r[4], tk(r[7])]),
    t:(p.trophies || []).filter(t => (t[4] || []).length).map(t => [t[0], t[1], t[3], t[4]]) };
}
// back into the shape P.playerCareer draws ({career:{senior:{seasons}}, trophies}); a trophy keeps its 5-slot layout
const asProfile = t => t ? { career:{ senior:{ seasons:t.s, teams:t.m || [] }, "national team":{ seasons:t.n } }, trophies:t.t.map(x => [x[0], x[1], 0, x[2], x[3]]) } : null;

function seasonRow(t){
  const s = t && t.s && t.s[0];
  if (!s || !CURRENT.test(String(s[0]))) return null;
  return { season:String(s[0]), apps:+s[3] || 0, g:+s[4] || 0, a:+s[5] || 0, team:s[1] };
}
function careerTotals(t){
  const played = ((t && t.s) || []).filter(s => +s[3] > 0);
  return played.length ? { apps:played.reduce((a, s) => a + (+s[3] || 0), 0), g:played.reduce((a, s) => a + (+s[4] || 0), 0), seasons:played.length } : null;
}

// the <title>: in the Arabic people type in a search box («هذا الموسم», «إحصائياته»), not the page's Emirati (owner 2026-10-09)
const title = o => `${o.name}: ${o.nums ? "إحصائياته وأهدافه هذا الموسم" : "مسيرته وبطاقته"}${o.team ? " مع " + o.team : ""} | تيفو`;

// Arabic counting: 1 «مباراة وحدة» · 2 «مباراتين» · 3-10 plural · 11+ singular (the same rule as lib/world_stage.cjs)
const count = (k, w) => k === 1 ? `${w[0]} ${w[3]}` : k === 2 ? w[1] : `${k} ${k <= 10 ? w[2] : w[0]}`;
const GAMES = ["مباراة", "مباراتين", "مباريات", "وحدة"], GOALS = ["هدف", "هدفين", "أهداف", "واحد"], SEASONS = ["موسم", "موسمين", "مواسم", "واحد"],
  MINUTES = ["دقيقة", "دقيقتين", "دقايق", "وحدة"];
const scored = (g, a) => [g ? "سجّل " + count(g, GOALS) : "", a ? "صنع " + count(a, GOALS) : ""].filter(Boolean).join(" و");

// o: {name, pos, country, team, age, comp, league:{comp, min, g, a} | null, season:{apps, g, a} | null, career:{apps, g, seasons} | null}.
// One set of numbers per page: the league file's (the tiles show them) when he has minutes there, else this season's career row,
// else his career. Plain text: the caller escapes
function intro(o){
  if (!o.name) return "";
  const who = [o.pos, o.country && "من " + o.country].filter(Boolean).join(" ");
  const first = o.team ? `${o.name}${who ? " " + who + "،" : ""} يلعب مع ${o.team}${o.age != null ? "، عمره " + o.age + " سنة" : ""}.` : "";
  const lg = o.league && o.league.min ? o.league : null, se = !lg && o.season && o.season.apps ? o.season : null, ca = !lg && !se && o.career && o.career.apps ? o.career : null;
  let second = "";
  if (lg){ const sc = scored(lg.g, lg.a); second = `هالموسم لعب ${count(lg.min, MINUTES)}${lg.comp ? " في " + lg.comp : ""}${sc ? "، و" + sc : ""}.`; }
  else if (se){ const sc = scored(se.g, se.a); second = `هالموسم لعب ${count(se.apps, GAMES)}${o.comp ? " في " + o.comp : ""}${sc ? "، و" + sc : ""}.`; }
  else if (ca){ const sc = scored(ca.g, 0); second = `لعب ${count(ca.apps, GAMES)} مع الأندية في ${count(ca.seasons, SEASONS)}${sc ? "، و" + sc : ""}.`; }
  if (!first && !second) return "";
  return [first || `${o.name}${who ? " " + who : ""}.`, second].filter(Boolean).join(" ");
}

// o: {site, id, name, latin, born, h, country, team, image, aka: other Arabic spellings (names/aka.py)}
function person(o){
  const nm = o.name || o.latin, alt = [o.name && o.latin && o.latin !== o.name ? o.latin : null].concat(o.aka || []).filter(Boolean);
  return Object.assign({ "@context":"https://schema.org", "@type":"Person", name:nm, url:`${o.site}/p/${o.id}/`, jobTitle:"لاعب كرة قدم" },
    alt.length ? { alternateName:alt.length === 1 ? alt[0] : alt } : {}, o.born && o.born >= "1900" ? { birthDate:o.born } : {},
    o.h ? { height:{ "@type":"QuantitativeValue", value:o.h, unitCode:"CMT" } } : {}, o.country ? { nationality:{ "@type":"Country", name:o.country } } : {},
    o.team ? { affiliation:{ "@type":"SportsTeam", name:o.team } } : {}, o.image ? { image:o.site + o.image } : {});
}

// ---- the career cache: careers.json {id: trimmed} + meta.json {done:{id: gen}}; one file each (thousands of small files are
// slow to read on Windows). A profile that answers nothing (no file) is marked done too: it is retried with the next generation.
const rj = (f, d) => { try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch (e){ return d; } };
function loadCareers(dir){ return { careers:rj(path.join(dir, "careers.json"), {}), meta:Object.assign({ done:{} }, rj(path.join(dir, "meta.json"), {})) }; }
async function refreshCareers({ ids, gen, get, pool, dir, budget }){
  fs.mkdirSync(dir, { recursive:true });
  const { careers, meta } = loadCareers(dir), want = new Set(ids.map(String));
  for (const id of Object.keys(careers)) if (!want.has(id)) delete careers[id];   // left the /p/ pages
  for (const id of Object.keys(meta.done)) if (!want.has(id)) delete meta.done[id];
  // never read first, then the ones read under an older generation
  const need = [...want].filter(id => meta.done[id] !== gen).sort((a, b) => (meta.done[a] ? 1 : 0) - (meta.done[b] ? 1 : 0)).slice(0, budget);
  let fetched = 0, failed = 0;
  await pool(need, 32, async id => { const p = await get(`player/${id}/profile.json`, 2); meta.done[id] = gen;
    if (!p){ failed++; delete careers[id]; return; } fetched++; careers[id] = trimProfile(p); });
  fs.writeFileSync(path.join(dir, "careers.json"), JSON.stringify(careers)); fs.writeFileSync(path.join(dir, "meta.json"), JSON.stringify(meta));
  return { fetched, failed, waiting:[...want].filter(id => meta.done[id] !== gen).length, cached:Object.keys(careers).length };
}

module.exports = { trimProfile, asProfile, seasonRow, careerTotals, title, intro, person, loadCareers, refreshCareers, CURRENT };
