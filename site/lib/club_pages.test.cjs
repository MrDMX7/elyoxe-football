// node --test site/lib/club_pages.test.cjs — the encyclopedia's club page (/db/club/<id>/), its archive history with it
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), CP = require("./club_pages.cjs");

const TRT = { forClub: () => ({ in: [], out: [] }), rumoursOf: () => [], clubSection: () => "" };
const card = { id: 4678, name_ar: "ألانيا سبور", name: "Alanyaspor", country_ar: "تركيا", squad: [] };

test("one page per club: the archive's history on the encyclopedia's page, which a club with only history now gets", () => {
  const P = CP.clubPage(card, { TRT, site: "https://tifo.elyoxe.com", history: id => (id === 4678 ? { ss: [] } : null), historyHtml: () => '<section id="hist"></section>' });
  assert.ok(P);
  assert.match(P.html, /id="hist"/);
  assert.equal(CP.clubPage(card, { TRT, site: "https://tifo.elyoxe.com" }), null);          // nothing to show: no page
});
