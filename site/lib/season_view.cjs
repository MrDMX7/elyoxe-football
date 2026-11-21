// An old season (v1/editions/<comp>.json + v1/matches/<comp>/<season>.json) in the shapes the current competition page takes
// (src/v5/pages.js P.comp: st, fx, stats), so a past season looks like this one (owner 2026-11-22: «الجداول والمباريات والهدافين
// التاريخية نفس تصميم البطولات الحالية»). A club or a man FotMob never had: no crest, his archive page or none.
"use strict";

const MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];

function team(id, name, i) {
  return id ? { id, name_ar: name } : { id: "n" + i + "-" + String(name || "").replace(/\s+/g, "-"), name_ar: name, nocrest: true };
}

// the final table: [rank, FotMob id, name, played, won, drawn, lost, for, against, points] -> one group of the current rows; a
// tournament the archive holds no table for: its group tables counted from its group matches («Group A»), 3 points a win
function standings(s, ms) {
  const rows = (s.table || []).map((r, i) => ({ rank: r[0], team: team(r[1], r[2], i), played: r[3], won: r[4], drawn: r[5], lost: r[6], gf: r[7], ga: r[8],
    gd: r[7] != null && r[8] != null ? r[7] - r[8] : null, pts: r[9] }));
  if (rows.length) return { groups: [{ rows }] };
  const by = new Map();
  for (const m of ms || []) {
    if (!/^group\b/i.test(String(m.round || "")) || !m.s || m.s[0] == null) continue;
    if (!by.has(m.round)) by.set(m.round, new Map());
    const g = by.get(m.round);
    [[m.h, m.s[0], m.s[1]], [m.a, m.s[1], m.s[0]]].forEach(([t, f, a], k) => {
      const key = String(t[0] || t[1]);
      if (!g.has(key)) g.set(key, { team: team(t[0], t[1], "g" + key), played: 0, won: 0, drawn: 0, lost: 0, gf: 0, ga: 0, pts: 0 });
      const r = g.get(key);
      r.played++; r.gf += f; r.ga += a; if (f > a) { r.won++; r.pts += 3; } else if (f === a) { r.drawn++; r.pts++; } else r.lost++;
    });
  }
  if (!by.size) return null;
  const groups = [...by.keys()].sort().map(name => ({ name, rows: [...by.get(name).values()].map(r => Object.assign(r, { gd: r.gf - r.ga }))
    .sort((x, y) => y.pts - x.pts || y.gd - x.gd || y.gf - x.gf || y.won - x.won || String(x.team.name_ar).localeCompare(String(y.team.name_ar), "ar"))
    .map((r, i) => Object.assign({ rank: i + 1 }, r)) }));
  return { groups };
}

// a knockout round as the current rounds name it (src/v5/ui.js U.rounds orders them, U.stageAr reads them): «Round of 16» and
// «round of 16» one chip, the third place before the final
const KO = [[/^round of 32$/i, "1/16"], [/^round of 16$/i, "1/8"], [/quarter/i, "1/4"], [/semi/i, "1/2"], [/third|3rd/i, "3rd place"], [/^finals?$/i, "Final"]];
const roundKey = r => { const s = String(r).trim(), k = KO.find(x => x[0].test(s)); return k ? k[1] : s; };

// the season's matches, finished, by round; a season the archive holds no rounds for, by month (أكتوبر 2002)
function fixtures(ms) {
  const month = d => (d && d.length >= 7 ? MONTHS[+d.slice(5, 7) - 1] + " " + d.slice(0, 4) : "—");
  return { matches: (ms || []).map((m, i) => ({ id: m.id, href: "/m/" + m.id + "/", round: m.round != null && m.round !== "" ? roundKey(m.round) : month(m.date), status: "finished",
    score: { home: m.s[0], away: m.s[1] }, penalties: m.pen ? { home: m.pen[0], away: m.pen[1] } : null, kickoff_utc: (m.date || "") + "T12:00:00Z",
    home: team(m.h[0], m.h[1], "h" + i), away: team(m.a[0], m.a[1], "a" + i) })) };
}

// the top scorers: a man FotMob knows by his FotMob id, the others by k<Tifo id> (/p/k<id>/)
function stats(s) {
  const goals = (s.top_scorers || []).map(p => ({ rank: p.rank, player: { id: p.fotmob || (p.tifo ? "k" + p.tifo : null), name: p.name }, team: null, value: p.value }));
  return goals.length ? { lists: { goals } } : null;
}

// the season before and after in the competition's list (newest first)
function around(seasons, season) {
  const i = seasons.findIndex(s => s.season === season);
  return { newer: i > 0 ? seasons[i - 1].season : null, older: i >= 0 && i < seasons.length - 1 ? seasons[i + 1].season : null };
}

module.exports = { standings, fixtures, stats, around, MONTHS };
