@echo off
setlocal
title YouTube History Bot - Launch Chrome (debug port)
cd /d "%~dp0"

echo ======================================================================
echo  Launching YOUR Chrome with remote-debugging enabled
echo  (so the bot can attach to the SAME profile you use)
echo ======================================================================
echo.
echo  To use a specific Chrome profile, pass --profile "Profile 5"
echo  Example:  launch-chrome-debug.bat --profile "Profile 5"
echo  (default is read from config.json -> "chrome_profile_dir")
echo.

set "PY="
if exist ".venv\Scripts\python.exe" ( set "PY=.venv\Scripts\python.exe" ) else ( set "PY=python" )

"%PY%" launch_chrome_debug.py %*
if errorlevel 1 (
    echo.
    echo [ERROR] Could not launch Chrome. See message above.
)
echo.
echo Done. Keep this Chrome window open, then press START BOT in the dashboard
echo and turn ON "Attach to running Chrome (CDP)".
echo.
pause
