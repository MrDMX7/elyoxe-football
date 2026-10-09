/* «معلق مباراة X و Y» (owner 2026-10-09): what a search engine reads about a match before any script runs. The commentator
   and channel Tifo knows (news/commentators.py -> v1/tv/<ymd>.json, matched to the fixture) go into the title and the
   description; the page itself carries the same «منو يعلّق؟» block src/tv.js paints (it repaints #tvc in place).
   tests/test_match_commentator_seo.py. */
"use strict";
// tv: [{channel, commentator, commentators?}] for this match (may be empty)
const named = tv => (tv || []).filter(e => e && e.commentator);
function title(o){
  if (o.played) return `نتيجة مباراة ${o.H0} و${o.A0} ${o.score.home}-${o.score.away} في ${o.cN} | تيفو`;
  const ch = o.ww || (o.tv || []).some(e => e && e.channel), cm = named(o.tv).length > 0;
  return `موعد مباراة ${o.H0} و${o.A0} في ${o.cN}${ch ? " والقناة الناقلة" : ""}${cm ? " والمعلق" : ""} | تيفو`;
}
// the description's first words: «المعلق: X على Y. » (empty when no commentator is known)
function lead(tv){
  const e = named(tv)[0];
  if (!e) return "";
  const who = (e.commentators && e.commentators.length > 1 ? e.commentators : [e.commentator]).join(" و");
  return `المعلق: ${who}${e.channel ? " على " + e.channel : ""}. `;
}
module.exports = { title, lead };
