@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "APP_NAME=LocalCivitaiVideoWall"
set "APP_URL=http://127.0.0.1:8787"
set "APP_PORT=8787"
set "SCRIPT_DIR=%~dp0"
set "HELPER_DIR=%APPDATA%\LocalCivitaiVideoWall"
set "VBS_PATH=%HELPER_DIR%\start_hidden.vbs"

:menu
cls
echo Local Civitai Video Wall Service
echo.
call :status_line
echo.
echo App directory: %SCRIPT_DIR%
echo URL: %APP_URL%
echo Helper script: %VBS_PATH%
echo.
echo 1. Start in background
echo 2. Stop background service
echo 3. Install startup
echo 4. Uninstall startup
echo 5. Open browser
echo 6. Check status
echo 7. Restart background service
echo 8. Start in background and open browser
echo 0. Exit
echo.
set /p "choice=Choose: "

if "%choice%"=="1" goto start_background
if "%choice%"=="2" goto stop_service
if "%choice%"=="3" goto install_startup
if "%choice%"=="4" goto uninstall_startup
if "%choice%"=="5" goto open_browser
if "%choice%"=="6" goto check_status
if "%choice%"=="7" goto restart_service
if "%choice%"=="8" goto start_and_open
if "%choice%"=="0" goto end
goto menu

:status_line
call :is_running
if "%RUNNING%"=="1" (
  echo Service status: running ^(PID %SERVICE_PID%^)
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
set "SERVICE_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%APP_PORT% .*LISTENING"') do (
  set "RUNNING=1"
  set "SERVICE_PID=%%P"
)
exit /b

:has_python
set "PYTHON_OK=0"
where py >nul 2>nul && set "PYTHON_OK=1"
if not "%PYTHON_OK%"=="1" (
  where python >nul 2>nul && set "PYTHON_OK=1"
)
exit /b

:ensure_helper_dir
if not exist "%HELPER_DIR%" (
  mkdir "%HELPER_DIR%" >nul 2>nul
)
if not exist "%HELPER_DIR%" (
  echo Could not create helper directory:
  echo %HELPER_DIR%
  exit /b 1
)
exit /b 0

:write_vbs
call :ensure_helper_dir
if not "%errorlevel%"=="0" exit /b 1
> "%VBS_PATH%" echo Set shell = CreateObject("WScript.Shell")
>> "%VBS_PATH%" echo shell.CurrentDirectory = "%SCRIPT_DIR%"
>> "%VBS_PATH%" echo shell.Run "cmd.exe /d /c " ^& Chr(34) ^& "py -3 app.py ^|^| python app.py" ^& Chr(34), 0, False
exit /b 0

:launch_background
call :has_python
if not "%PYTHON_OK%"=="1" (
  echo Python was not found. Install Python 3.10 or later, then try again.
  exit /b 1
)
call :write_vbs
if not "%errorlevel%"=="0" exit /b 1
wscript.exe "%VBS_PATH%"
timeout /t 2 /nobreak >nul
call :is_running
if "%RUNNING%"=="1" (
  exit /b 0
)
exit /b 1

:start_background
call :is_running
if "%RUNNING%"=="1" (
  echo Service is already running ^(PID %SERVICE_PID%^).
  pause
  goto menu
)
call :launch_background
if "%errorlevel%"=="0" (
  echo Service started in background.
) else (
  echo Service did not start. Check that Python is installed and port %APP_PORT% is available.
)
pause
goto menu

:stop_service
call :stop_service_once
pause
goto menu

:stop_service_once
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
exit /b 0

:install_startup
call :write_vbs
if not "%errorlevel%"=="0" (
  echo Failed to write helper script.
  pause
  goto menu
)
schtasks /Create /TN "%APP_NAME%" /TR "wscript.exe ""%VBS_PATH%""" /SC ONLOGON /RL LIMITED /F >nul
if "%errorlevel%"=="0" (
  echo Startup entry installed.
  echo It uses the helper script under APPDATA, not TEMP.
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
call :has_python
if "%PYTHON_OK%"=="1" (
  echo Python status: available
) else (
  echo Python status: not found
)
if exist "%VBS_PATH%" (
  echo Helper status: exists
) else (
  echo Helper status: not created yet
)
echo.
pause
goto menu

:restart_service
call :stop_service_once
timeout /t 1 /nobreak >nul
call :launch_background
if "%errorlevel%"=="0" (
  echo Service restarted in background.
) else (
  echo Service did not restart. Check that Python is installed and port %APP_PORT% is available.
)
pause
goto menu

:start_and_open
call :is_running
if "%RUNNING%"=="1" (
  echo Service is already running ^(PID %SERVICE_PID%^).
) else (
  call :launch_background
  if "%errorlevel%"=="0" (
    echo Service started in background.
  ) else (
    echo Service did not start. Check that Python is installed and port %APP_PORT% is available.
    pause
    goto menu
  )
)
start "" "%APP_URL%"
pause
goto menu

:end
endlocal
