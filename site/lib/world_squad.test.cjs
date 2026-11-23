// node --test site/lib/world_squad.test.cjs — where the site's post-build link check sends a link to a page it did not write
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), W = require("./world_squad.cjs");

test("an old match the archive has goes to its archive page, the same match page as today's; the rest to the match card", () => {
  const has = { written: new Set(), clubs: new Set(), fm2k: { 4813470: 86169 } };
  assert.equal(W.relink("/m/4813470/", has), "/m/k86169/");
  assert.equal(W.relink("/m/5000000/", has), "/db/match/?id=5000000");
  assert.equal(W.relink("/m/5000000/", { written: new Set(), clubs: new Set() }), "/db/match/?id=5000000");
});
