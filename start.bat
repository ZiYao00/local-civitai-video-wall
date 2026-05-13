@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting Local Civitai Video Wall v2...
echo Opening http://127.0.0.1:8787 ...
echo.
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Milliseconds 900; Start-Process 'http://127.0.0.1:8787'"
python app.py
pause
