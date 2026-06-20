@echo off
chcp 65001 > nul

:: ============================================
::   [설정] 영웅문 CSV 저장 폴더 경로
::   이 줄만 본인 경로로 수정하세요
set INPUT_DIR=C:\Users\User\Desktop\project\find_leader_csv\korea
:: ============================================

echo.
echo ============================================
echo   Korea Market Report - 일일 리포트 생성
echo ============================================
echo   입력 폴더: %INPUT_DIR%
echo ============================================
echo.

cd /d "%~dp0"

python korea_market\run_local.py --input "%INPUT_DIR%"
if %errorlevel% neq 0 (
    echo.
    echo [오류] 실행 중 문제가 발생했습니다.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   완료! GitHub에 업로드합니다...
echo ============================================
echo.

git add docs\reports\
git commit -m "daily report %date:~0,4%-%date:~5,2%-%date:~8,2%"
git push origin main

echo.
echo [완료] 리포트가 GitHub Pages에 업로드됐습니다.
echo https://melstoria.github.io/my-korea-market-report/
echo.
pause
