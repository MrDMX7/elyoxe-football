// Reference prayer times from the SAME library and parameters as elyoxe.com/tools (saas/tools/src/assets/prayer.js):
// adhan Dubai method (18.2/18.2, sunrise -3, dhuhr +3, asr +3, maghrib +3) plus asr -1, maghrib +1, isha +1.
// Output feeds tests/test_prayer.py.   node tools/adhan_reference.js > tests/fixtures/prayer_adhan.json
const path = require("path");

const A = require(path.resolve(__dirname, "../../tools/src/assets/vendor/adhan.umd.min.js"));

function params() { const p = A.CalculationMethod.Dubai(); p.adjustments.asr = -1; p.adjustments.maghrib = 1; p.adjustments.isha = 1; return p; }
const places = [["abu-dhabi-zayed-sports-city", 24.416052749, 54.453703165], ["dubai-al-maktoum", 25.23995537, 55.312830806],
  ["al-ain-hazza", 24.2446, 55.7179], ["ajman-stadium", 25.392458678, 55.450626612], ["kalba", 25.0689, 56.3504], ["ruwais", 24.1103, 52.7306]];
const dates = ["2026-01-15", "2026-03-21", "2026-06-21", "2026-09-26", "2026-10-16", "2026-12-21"];
const out = [];
for (const [id, lat, lon] of places) for (const d of dates) {
  const [y, m, dd] = d.split("-").map(Number);
  const t = new A.PrayerTimes(new A.Coordinates(lat, lon), new Date(y, m - 1, dd), params());
  out.push({ id, lat, lon, date: d, fajr: t.fajr.toISOString(), sunrise: t.sunrise.toISOString(), dhuhr: t.dhuhr.toISOString(),
             asr: t.asr.toISOString(), maghrib: t.maghrib.toISOString(), isha: t.isha.toISOString() });
}
console.log(JSON.stringify(out, null, 1));
