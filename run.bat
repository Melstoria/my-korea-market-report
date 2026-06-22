@echo off
set INPUT_DIR=C:\Users\User\Desktop\project\find_leader_csv\korea
cd /d "%~dp0"
python korea_market\run_local.py
if %errorlevel% neq 0 (
    pause
    exit /b 1
)
git add docs\reports\
git commit -m "daily report"
git push origin main
pause