@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "APP_NAME=LocalCivitaiVideoWall"
set "APP_URL=http://127.0.0.1:8787"
set "APP_PORT=8787"
set "SCRIPT_DIR=%~dp0"
set "VBS_PATH=%TEMP%\local_civitai_video_wall_start_hidden.vbs"

:menu
cls
echo Local Civitai Video Wall Service
echo.
call :status_line
echo.
echo 1. Start in background
echo 2. Stop background service
echo 3. Install startup
echo 4. Uninstall startup
echo 5. Open browser
echo 6. Check status
echo 0. Exit
echo.
set /p "choice=Choose: "

if "%choice%"=="1" goto start_background
if "%choice%"=="2" goto stop_service
if "%choice%"=="3" goto install_startup
if "%choice%"=="4" goto uninstall_startup
if "%choice%"=="5" goto open_browser
if "%choice%"=="6" goto check_status
if "%choice%"=="0" goto end
goto menu

:status_line
call :is_running
if "%RUNNING%"=="1" (
  echo Service status: running
) else (
  echo Service status: stopped
)
schtasks /Query /TN "%APP_NAME%" >nul 2>nul
if "%errorlevel%"=="0" (
  echo Startup status: installed
) else (
  echo Startup status: not installed
)
exit /b

:is_running
set "RUNNING=0"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%APP_PORT% .*LISTENING"') do (
  set "RUNNING=1"
)
exit /b

:write_vbs
> "%VBS_PATH%" echo Set shell = CreateObject("WScript.Shell")
>> "%VBS_PATH%" echo shell.CurrentDirectory = "%SCRIPT_DIR%"
>> "%VBS_PATH%" echo shell.Run "cmd /c cd /d " ^& Chr(34) ^& "%SCRIPT_DIR%" ^& Chr(34) ^& " && where py ^>nul 2^>nul && py -3 app.py ^|^| python app.py", 0, False
exit /b

:start_background
call :is_running
if "%RUNNING%"=="1" (
  echo Service is already running.
  pause
  goto menu
)
call :write_vbs
wscript "%VBS_PATH%"
timeout /t 2 /nobreak >nul
call :is_running
if "%RUNNING%"=="1" (
  echo Service started in background.
) else (
  echo Service did not start. Check that Python is installed.
)
pause
goto menu

:stop_service
set "FOUND=0"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%APP_PORT% .*LISTENING"') do (
  set "FOUND=1"
  taskkill /PID %%P /F >nul 2>nul
)
if "%FOUND%"=="1" (
  echo Service stopped.
) else (
  echo Service is not running.
)
pause
goto menu

:install_startup
call :write_vbs
schtasks /Create /TN "%APP_NAME%" /TR "wscript.exe ""%VBS_PATH%""" /SC ONLOGON /RL LIMITED /F >nul
if "%errorlevel%"=="0" (
  echo Startup entry installed.
) else (
  echo Failed to install startup entry.
)
pause
goto menu

:uninstall_startup
schtasks /Delete /TN "%APP_NAME%" /F >nul 2>nul
if "%errorlevel%"=="0" (
  echo Startup entry removed.
) else (
  echo Startup entry was not installed.
)
pause
goto menu

:open_browser
start "" "%APP_URL%"
goto menu

:check_status
echo.
call :status_line
echo.
pause
goto menu

:end
endlocal
