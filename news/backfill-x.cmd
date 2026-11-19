@echo off
rem The X half of the one-month goal clips backfill (owner 2026-11-19), run once by Task Scheduler after the evening's matches:
rem the official accounts' video posts back to a month (news/xhistory.js, X's own search page, no API), then the same checks
rem as the live finder (news/media_backfill.py, YouTube listings skipped: done by hand earlier). Log: news\.backfill-x.log
cd /d "%~dp0.."
echo %date% %time% start > news\.backfill-x.log
rem Arguments go to xhistory.js (2026-11-20: --stop-at ISO-TIME, no new account after it, before the day's matches).
node news\xhistory.js --upload %* >> news\.backfill-x.log 2>&1
python -m news.media_backfill --days 32 --no-youtube >> news\.backfill-x.log 2>&1
echo %date% %time% done %errorlevel% >> news\.backfill-x.log
