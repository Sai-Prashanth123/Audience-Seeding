@echo off
rem Scheduled 1D live forward test: every 4 hours (Task Scheduler "AudienceSeeding-Live").
rem Reads xplatform's stored posts only (no scrape quota), scores new pilot posts, checks 48h-old ones.
cd /d D:\Audience_seeding
set HF_HUB_OFFLINE=1
set PYTHONIOENCODING=utf-8
for /L %%i in (1,1,3) do (
  echo ==== %DATE% %TIME% attempt %%i >> logs\live.log
  "C:\Users\saip0\.local\bin\uv.exe" run --no-sync seeding live >> logs\live.log 2>&1 && goto :done
  rem database busy (dashboard mid-read) or network blip: wait and retry
  timeout /t 60 /nobreak > nul
)
echo ==== %DATE% %TIME% FAILED after 3 attempts >> logs\live.log
exit /b 1
:done
"C:\Users\saip0\.local\bin\uv.exe" run --no-sync seeding export-dashboard >> logs\live.log 2>&1
exit /b 0
