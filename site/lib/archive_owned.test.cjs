// node --test site/lib/archive_owned.test.cjs — the paths the archive job owns (site/archive/build.cjs, its sitemaps)
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), AO = require("./archive_owned.cjs");

test("the archive's pages are its own: seasons, season lists, old matches, profiles, referees, old clubs", () => {
  for (const u of ["/c/premier-league/s/1990-1991/", "/c/laliga/seasons/", "/m/k698675/", "/p/k2480/", "/r/k12/", "/t/k22417/", "/coach/k77/"]) assert.equal(AO.owned(u), true, u);
});

test("the site's own pages are not", () => {
  for (const u of ["/", "/c/premier-league/", "/c/uae-pro-league/scorers/", "/m/4813470/", "/p/30981/", "/t/8650/", "/awards/", "/news/x/", "/coach/500/"]) assert.equal(AO.owned(u), false, u);
});
