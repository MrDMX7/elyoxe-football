// An old season (v1/editions/<comp>.json + v1/matches/<comp>/<season>.json) in the shapes the current competition page takes
// (src/v5/pages.js P.comp: st, fx, stats), so a past season looks like this one (owner 2026-11-22: «الجداول والمباريات والهدافين
// التاريخية نفس تصميم البطولات الحالية»). A club or a man FotMob never had: no crest, his archive page or none.
"use strict";

const MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];

function team(id, name, i) {
  return id ? { id, name_ar: name } : { id: "n" + i + "-" + String(name || "").replace(/\s+/g, "-"), name_ar: name, nocrest: true };
}

// the final table: [rank, FotMob id, name, played, won, drawn, lost, for, against, points] -> one group of the current rows
function standings(s) {
  const rows = (s.table || []).map((r, i) => ({ rank: r[0], team: team(r[1], r[2], i), played: r[3], won: r[4], drawn: r[5], lost: r[6], gf: r[7], ga: r[8],
    gd: r[7] != null && r[8] != null ? r[7] - r[8] : null, pts: r[9] }));
  return rows.length ? { groups: [{ rows }] } : null;
}

// the season's matches, finished, by round; a season the archive holds no rounds for, by month (أكتوبر 2002)
function fixtures(ms) {
  const month = d => (d && d.length >= 7 ? MONTHS[+d.slice(5, 7) - 1] + " " + d.slice(0, 4) : "—");
  return { matches: (ms || []).map((m, i) => ({ id: m.id, href: "/m/" + m.id + "/", round: m.round != null && m.round !== "" ? String(m.round) : month(m.date), status: "finished",
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
