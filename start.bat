@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting Local Civitai Video Wall v2...
echo.
python app.py
pause
