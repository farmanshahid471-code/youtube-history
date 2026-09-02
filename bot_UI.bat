@echo off
setlocal
title YouTube History Bot - Control Panel
cd /d "%~dp0"

echo ======================================================================
echo          YouTube History Bot - Control Panel Launcher
echo ======================================================================
echo.

rem ---------------------------------------------------------------
rem 1. Find a working Python interpreter (functional test, not just
rem    "where", so a broken or Microsoft Store stub is caught).
rem    Uses goto-based flow: far more reliable than nested if (...) blocks.
rem ---------------------------------------------------------------
set "PYTHON_CMD="
where python >nul 2>nul
if errorlevel 1 goto try_py
python -c "import sys; sys.exit(0)" >nul 2>nul
if errorlevel 1 goto try_py
set "PYTHON_CMD=python"
goto have_python

:try_py
where py >nul 2>nul
if errorlevel 1 goto no_python
set "PYTHON_CMD=py"
goto have_python

:no_python
echo [ERROR] Python is not installed or not in PATH!
echo.
echo Please install Python 3.10+ from: https://www.python.org/downloads/
echo IMPORTANT: tick "Add python.exe to PATH" during installation.
echo After installing, RE-OPEN this window and try again.
echo.
echo Press any key to exit...
pause >nul
exit /b 1

:have_python
echo [1/4] Found Python: %PYTHON_CMD%
%PYTHON_CMD% --version

rem ---------------------------------------------------------------
rem 2. Create / verify the virtual environment
rem ---------------------------------------------------------------
if exist ".venv\Scripts\python.exe" goto venv_ready
echo [2/4] Creating virtual environment (.venv)... this happens once.
%PYTHON_CMD% -m venv .venv
if errorlevel 1 goto venv_failed

:venv_ready
echo [2/4] Virtual environment ready.

if exist ".venv\Scripts\python.exe" goto deps
echo [ERROR] The virtual environment was not created. Is Python a real install
echo         from python.org (not the Microsoft Store shortcut)?
echo.
echo Press any key to close...
pause >nul
exit /b 1

:venv_failed
echo [ERROR] Failed to create the virtual environment.
echo.
echo Press any key to close...
pause >nul
exit /b 1

rem ---------------------------------------------------------------
rem 3. Install / verify dependencies
rem ---------------------------------------------------------------
:deps
echo [3/4] Checking dependencies...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if not errorlevel 1 goto browser
echo [WARNING] Pip install had issues, retrying with verbose output...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto pip_failed
goto browser

:pip_failed
echo [ERROR] Failed to install requirements. Check your internet connection.
echo.
echo Press any key to close...
pause >nul
exit /b 1

rem ---------------------------------------------------------------
rem 4. Install Playwright's Chromium browser
rem ---------------------------------------------------------------
:browser
echo [4/4] Checking browser engine...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (
    echo [WARNING] Playwright Chromium install may have failed. The bot may still
    echo          work if you enable "Use my real Chrome profile" in the dashboard.
    echo.
)

rem ---------------------------------------------------------------
rem Sanity check the UI script exists
rem ---------------------------------------------------------------
if exist "bot_ui.py" goto ready
echo [ERROR] bot_ui.py was not found in this folder.
echo         Make sure you extracted the whole project, not just one file.
echo.
echo Press any key to close...
pause >nul
exit /b 1

:ready
echo.
echo ======================================================================
echo   Starting YouTube History Bot Web UI Control Panel...
echo   Dashboard: http://localhost:5000
echo.
echo   Keep THIS window open while you use the bot.
echo   To stop, click STOP BOT in the dashboard, or press Ctrl+C here.
echo ======================================================================
echo.

rem Open the dashboard in the SAME Chrome profile the bot will drive.
rem We launch Chrome (Profile 5) with the debug port enabled and point it at the
rem dashboard, so the bot can ATTACH to that window (rather than trying to open a
rem second copy of the profile, which locks and hangs). This runs non-interactively.
echo Opening your Chrome profile (see config.json "chrome_profile_dir") with the debug port...
start "" /b cmd /c "timeout /t 3 /nobreak >nul & .venv\Scripts\python.exe launch_chrome_debug.py --url http://localhost:5000 --auto"

rem Run the UI server in the foreground of this window
".venv\Scripts\python.exe" bot_ui.py %*
set "BOT_EXIT=%errorlevel%"

echo.
echo ======================================================================
echo Server stopped (exit code: %BOT_EXIT%).
echo ======================================================================
echo.
echo This window is now idle. You can close it, or run the bot again.
echo.
echo Press any key to close...
pause >nul
exit /b %BOT_EXIT%
