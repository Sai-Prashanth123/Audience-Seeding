@echo off
rem Phase 2 daily job (Task Scheduler "AudienceSeeding-Engage", 06:00):
rem   1. scrape watched seeds' fresh posts + Phase 2 clients' replies and engagers (spends X quota,
rem      ~270 timeline reads: about two 15-minute windows of the pool), build today's Engage lists
rem   2. weekly tracking (treatment vs control), 3. refresh the dashboard snapshot
cd /d D:\Audience_seeding
set HF_HUB_OFFLINE=1
set PYTHONIOENCODING=utf-8
set UV=C:\Users\saip0\.local\bin\uv.exe
echo ==== %DATE% %TIME% engage >> logs\engage.log
"%UV%" run --no-sync seeding engage >> logs\engage.log 2>&1 && goto :track
rem scrape done but the database was busy (dashboard / live task): rebuild from stored posts
for /L %%i in (1,1,3) do (
  timeout /t 90 /nobreak > nul
  echo ==== %DATE% %TIME% engage --no-scrape retry %%i >> logs\engage.log
  "%UV%" run --no-sync seeding engage --no-scrape >> logs\engage.log 2>&1 && goto :track
)
echo ==== %DATE% %TIME% FAILED >> logs\engage.log
exit /b 1
:track
"%UV%" run --no-sync seeding track >> logs\engage.log 2>&1
"%UV%" run --no-sync seeding export-dashboard >> logs\engage.log 2>&1
exit /b 0
