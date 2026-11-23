// A name the build left in Latin letters (<span class="lat">…</span>), in Arabic where exactly one Arabic spelling is known for
// it (23 Nov 2026, the integrity check: the transfers, Arabs abroad, World Cup Arabs and memorable matches pages read 90 %
// in Latin letters — «Sami Al-Jaber», «Al Ain», «United Arab Emirates» — from data files that carry the English names).
// The dictionary: the site's clubs, FotMob's players, the archive's men, the clubs named in names/, the countries and the
// competitions. A name two men share with two spellings stays as it is; so does the Latin subtitle under a name
// (<p class="muted"><span class="lat">…</span></p>) and anything the dictionary does not know (a brand: Kooora, BBC Sport).
"use strict";

const AR = /[؀-ۿ]/;
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const unesc = s => String(s).replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">");

// pairs [latin, arabic] -> {latin: arabic}, only where the Latin name has one Arabic spelling
function dictionary(pairs) {
  const seen = new Map();
  for (const [la, ar] of pairs) {
    if (!la || !ar || !AR.test(ar) || AR.test(la)) continue;
    const k = String(la).trim();
    if (!seen.has(k)) seen.set(k, new Set());
    seen.get(k).add(String(ar).trim());
  }
  const out = {};
  for (const [k, s] of seen) if (s.size === 1) out[k] = [...s][0];
  return out;
}

function arabize(html, d) {
  let n = 0;
  const out = html.replace(/(<p class="muted">)?<span class="lat">([^<]{2,80})<\/span>/g, (m, sub, la) => {
    if (sub) return m;                                   // the Latin original under an Arabic name
    const ar = d[unesc(la).trim()];
    if (!ar) return m;
    n++;
    return esc(ar);
  });
  return { html: out, n };
}

module.exports = { dictionary, arabize };
