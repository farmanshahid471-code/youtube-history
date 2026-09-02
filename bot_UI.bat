@echo off
setlocal
title YouTube History Bot - Control Panel
cd /d "%~dp0"

:: ====================================================================
::  YouTube History Bot - Web UI Control Panel Launcher
::  Double-click this file to start the bot.
::  If it closes, run it from a terminal so you can READ the error:
::      Win+R -> type  cmd  -> press Enter
::      cd /d "F:\youtube-history-arena-01a06359-youtube-history"
::      bot_UI.bat
:: ====================================================================

echo ======================================================================
echo          YouTube History Bot - Control Panel Launcher
echo ======================================================================
echo.

:: ---------------------------------------------------------------
:: 1. Find a working Python interpreter
::    We use a FUNCTIONAL test (not just "where python") so the
::    Microsoft Store stub or a broken install is caught.
::    IMPORTANT: use "if not errorlevel 1" (runtime check) instead of
::    "%errorlevel% equ 0" inside parenthesised blocks.  "%errorlevel%"
::    is expanded at PARSE time, so the inner "py" probe would wrongly
::    reuse the outer result and never find the "py" launcher.
:: ---------------------------------------------------------------
set "PYTHON_CMD="
where python >nul 2>nul
if not errorlevel 1 (
    python -c "import sys; sys.exit(0)" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
    )
)
if not defined PYTHON_CMD (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=py"
    )
)

if not defined PYTHON_CMD (
    echo [ERROR] Python is not installed or not in PATH!
    echo.
    echo Please install Python 3.10+ from: https://www.python.org/downloads/
    echo IMPORTANT: tick "Add python.exe to PATH" during installation.
    echo After installing, RE-OPEN this window and try again.
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

echo [1/4] Found Python: %PYTHON_CMD%
%PYTHON_CMD% --version

:: ---------------------------------------------------------------
:: 2. Set up the virtual environment
:: ---------------------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [2/4] Creating virtual environment (.venv)... this happens once.
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        echo.
        echo Press any key to close...
        pause >nul
        exit /b 1
    )
) else (
    echo [2/4] Virtual environment ready.
)

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] The virtual environment was not created. Is Python a real install
    echo         (not the Microsoft Store shortcut)? Reinstall from python.org.
    echo.
    echo Press any key to close...
    pause >nul
    exit /b 1
)

:: ---------------------------------------------------------------
:: 3. Install / verify dependencies
:: ---------------------------------------------------------------
echo [3/4] Checking dependencies...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo [WARNING] Pip install had issues, retrying with verbose output...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install requirements. Check your internet connection.
        echo.
        echo Press any key to close...
        pause >nul
        exit /b 1
    )
)

:: ---------------------------------------------------------------
:: 4. Install Playwright's Chromium browser
:: ---------------------------------------------------------------
echo [4/4] Checking browser engine...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (
    echo [WARNING] Playwright Chromium install may have failed. The bot may still
    echo          work if you enable "Use my real Chrome profile" in the dashboard.
    echo.
)

:: ---------------------------------------------------------------
:: Sanity check that the UI script exists
:: ---------------------------------------------------------------
if not exist "bot_ui.py" (
    echo [ERROR] bot_ui.py was not found in this folder.
    echo         Make sure you extracted the whole project, not just one file.
    echo.
    echo Press any key to close...
    pause >nul
    exit /b 1
)

echo.
echo ======================================================================
echo   Starting YouTube History Bot Web UI Control Panel...
echo   Dashboard: http://localhost:5000
echo.
echo   Keep THIS window open while you use the bot.
echo   To stop, click STOP BOT in the dashboard, or press Ctrl+C here.
echo ======================================================================
echo.

:: Open the dashboard in your default browser after 2 seconds
start "" /b cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:5000"

:: Run the UI server in the foreground of this window
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
