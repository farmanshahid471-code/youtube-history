@echo off
setlocal
title YouTube History Bot - Control Panel
cd /d "%~dp0"

echo ======================================================================
echo          YouTube History Bot - Control Panel Launcher
echo ======================================================================
echo.

:: 1. Detect Python or Py Launcher
:: NOTE: we use "if not errorlevel 1" (runtime check) instead of "%errorlevel% equ 0"
:: inside the parenthesised blocks.  "%errorlevel%" is expanded at PARSE time when the
:: whole if/else block is read, so the inner check would always use the OUTER result
:: and never detect the "py" launcher - causing "Python is not installed" and an
:: immediate, silent exit.  "if errorlevel" is always evaluated at runtime.
set "PYTHON_CMD="
where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=py"
    )
)

if not defined PYTHON_CMD (
    echo [ERROR] Python is not installed or not in PATH!
    echo.
    echo Please install Python 3.10+ from: https://www.python.org/downloads/
    echo IMPORTANT: Make sure to check "Add python.exe to PATH" during installation.
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

echo [1/4] Found Python: %PYTHON_CMD%
%PYTHON_CMD% --version

:: 2. Setup Virtual Environment
if not exist ".venv\Scripts\python.exe" (
    echo [2/4] Creating virtual environment (.venv)...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment!
        echo.
        echo Press any key to close...
        pause >nul
        exit /b 1
    )
) else (
    echo [2/4] Virtual environment ready.
)

:: 3. Install / Verify Dependencies
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

:: 4. Install Playwright Chromium (if needed)
echo [4/4] Checking browser engine...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (
    echo [WARNING] Playwright Chromium install may have failed. The bot may still work
    echo          if your system browser is available.
    echo.
)

echo.
echo ======================================================================
echo   Starting YouTube History Bot Web UI Control Panel...
echo   Local Dashboard: http://localhost:5000
echo ======================================================================
echo.

:: Launch browser in background after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:5000"

:: Start the UI Server (runs in the foreground of this window)
".venv\Scripts\python.exe" bot_ui.py %*
set "BOT_EXIT=%errorlevel%"

echo.
echo ======================================================================
echo Server stopped (exit code: %BOT_EXIT%).
echo ======================================================================
echo.
echo This window is now idle. You can close it, or run the bot again.
echo.
pause
exit /b %BOT_EXIT%
