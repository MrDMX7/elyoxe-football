// The paths the archive job owns (site/archive/build.cjs publishes them, with their sitemaps and noindex rule): every season
// page and season list, every old match, and the archive's profiles, referees and old clubs. The same list as tools/runner.py
// ARCHIVE_OWNED (what the hourly publish never uploads or deletes); the site build writes some of them for its link check only,
// so its sitemap leaves them out (23 Nov 2026: it listed 11,801 old matches and 3,957 profiles the archive's sitemaps carry).
"use strict";

const OWNED = [/^\/c\/[^/]+\/s\//, /^\/c\/[^/]+\/seasons\//, /^\/m\/k/, /^\/p\/k/, /^\/r\/k/, /^\/t\/k/, /^\/coach\/k/];

const owned = u => OWNED.some(r => r.test(u));

module.exports = { owned };
