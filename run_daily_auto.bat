@echo off
rem Daily Korea market report (weekdays 09:00 via Task Scheduler). KRX Open API data arrives the next day.
rem run_auto.py: fetch -> build DB -> analyze -> HTML -> hub index. publish_daily.py only when PUBLISH=1.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY=..\krx_market_bottom\market-bottom\market-bottom\.venv\Scripts\python.exe
echo ==== %date% %time% ==== >> data\daily_auto.log
%PY% korea_market\run_auto.py >> data\daily_auto.log 2>&1 || goto :fail
if "%PUBLISH%"=="1" (
  %PY% korea_market\publish_daily.py >> data\daily_auto.log 2>&1 || goto :fail
)
echo OK >> data\daily_auto.log
exit /b 0
:fail
echo FAILED >> data\daily_auto.log
exit /b 1