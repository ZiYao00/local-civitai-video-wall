@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Starting Local Civitai Video Wall v2...
echo.
echo Browser will open automatically:
echo http://127.0.0.1:8787
echo.

REM Open browser after a short delay, without using PowerShell.
start "" /min cmd /c "timeout /t 2 /nobreak >nul & start "" http://127.0.0.1:8787"

REM Prefer the Windows Python launcher if available, otherwise use python.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 app.py
) else (
    python app.py
)

pause
