CREATE TABLE team(tid INTEGER PRIMARY KEY, name TEXT, name_ar TEXT, kind TEXT, country TEXT, founded INTEGER, sid INTEGER, src TEXT NOT NULL, filled TEXT);
CREATE TABLE player(pid INTEGER PRIMARY KEY, name TEXT, name_ar TEXT, name_native TEXT, born TEXT, died TEXT, birthplace TEXT, nationality TEXT, nationality2 TEXT, position TEXT, height INTEGER, foot TEXT, src TEXT NOT NULL, filled TEXT);
CREATE TABLE coach(kid INTEGER PRIMARY KEY, name TEXT, name_ar TEXT, born TEXT, nationality TEXT, pid INTEGER, src TEXT NOT NULL, filled TEXT);
CREATE TABLE referee(rid INTEGER PRIMARY KEY, name TEXT, name_ar TEXT, country TEXT, src TEXT NOT NULL, filled TEXT);
CREATE TABLE stadium(sid INTEGER PRIMARY KEY, name TEXT, name_ar TEXT, city TEXT, country TEXT, lat REAL, lon REAL, capacity INTEGER, src TEXT NOT NULL, filled TEXT);
CREATE TABLE competition(cid INTEGER PRIMARY KEY, name TEXT, name_ar TEXT, kind TEXT, scope TEXT, country TEXT, tier INTEGER, src TEXT NOT NULL, filled TEXT);
CREATE TABLE edition(eid INTEGER PRIMARY KEY, cid INTEGER NOT NULL, season TEXT NOT NULL, start TEXT, end TEXT, src TEXT NOT NULL, filled TEXT);
CREATE INDEX edition_cid ON edition(cid, season);
CREATE TABLE match(mid INTEGER PRIMARY KEY, eid INTEGER, round TEXT, date TEXT, home INTEGER, away INTEGER, hs INTEGER, as_ INTEGER,
  ht_h INTEGER, ht_a INTEGER, et INTEGER, pen_h INTEGER, pen_a INTEGER, status TEXT, sid INTEGER, rid INTEGER, attendance INTEGER, src TEXT NOT NULL, filled TEXT);
CREATE INDEX match_date ON match(date);
CREATE INDEX match_home ON match(home, date);
CREATE INDEX match_away ON match(away, date);
CREATE INDEX match_eid ON match(eid);
CREATE TABLE appearance(mid INTEGER, pid INTEGER, tid INTEGER, played INTEGER, started INTEGER, minutes INTEGER, position INTEGER, shirt TEXT,
  captain INTEGER, rating REAL, goals INTEGER, assists INTEGER, yellow INTEGER, red INTEGER, stats TEXT, src TEXT NOT NULL, PRIMARY KEY(mid, pid));
CREATE INDEX appearance_pid ON appearance(pid);
CREATE TABLE event(mid INTEGER, seq INTEGER, minute INTEGER, added INTEGER, type TEXT, side TEXT, tid INTEGER, pid INTEGER, pid2 INTEGER,
  detail TEXT, src TEXT NOT NULL, PRIMARY KEY(mid, seq));
CREATE INDEX event_pid ON event(pid);
CREATE TABLE match_coach(mid INTEGER, side TEXT, kid INTEGER, src TEXT NOT NULL, PRIMARY KEY(mid, side));
CREATE TABLE standing(eid INTEGER, grp TEXT, rank INTEGER, tid INTEGER, played INTEGER, won INTEGER, drawn INTEGER, lost INTEGER,
  gf INTEGER, ga INTEGER, pts REAL, src TEXT NOT NULL, PRIMARY KEY(eid, grp, rank));
CREATE TABLE honour(eid INTEGER, kind TEXT, rank INTEGER, tid INTEGER, pid INTEGER, kid INTEGER, value TEXT, src TEXT NOT NULL, PRIMARY KEY(eid, kind, rank));
CREATE TABLE transfer(pid INTEGER, from_tid INTEGER, to_tid INTEGER, date TEXT, season TEXT, fee INTEGER, type TEXT, src TEXT NOT NULL, PRIMARY KEY(pid, date, to_tid));
CREATE TABLE spell(pid INTEGER, tid INTEGER, start TEXT, end TEXT, apps INTEGER, goals INTEGER, assists INTEGER, loan INTEGER, national INTEGER, youth INTEGER,
  src TEXT NOT NULL, PRIMARY KEY(pid, tid, start, src));
CREATE TABLE player_season(pid INTEGER, season TEXT, comp TEXT, cid INTEGER, tid INTEGER, apps INTEGER, minutes INTEGER, goals INTEGER, assists INTEGER,
  yellow INTEGER, red INTEGER, clean_sheets INTEGER, conceded INTEGER, src TEXT NOT NULL);
CREATE INDEX player_season_pid ON player_season(pid);
CREATE TABLE injury(pid INTEGER, season TEXT, kind TEXT, start TEXT, end TEXT, days INTEGER, games INTEGER, src TEXT NOT NULL);
CREATE TABLE xref(type TEXT, tifo_id INTEGER, source TEXT, source_id TEXT, method TEXT, confidence REAL, PRIMARY KEY(type, source, source_id));
CREATE INDEX xref_tifo ON xref(type, tifo_id);
CREATE TABLE conflict(type TEXT, tifo_id INTEGER, field TEXT, kept TEXT, kept_src TEXT, other TEXT, other_src TEXT);
CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
