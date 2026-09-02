@echo off
setlocal
title YouTube History Bot - Player
cd /d "%~dp0"

echo ======================================================================
echo          YouTube History Bot - Player Launcher
echo ======================================================================
echo.

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
    echo (Make sure to check "Add python.exe to PATH" during install)
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Setting up environment (first run only)...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
)

echo Checking dependencies...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
".venv\Scripts\python.exe" -m playwright install chromium

echo.
".venv\Scripts\python.exe" auto_player.py %*
echo.
echo ======================================================================
echo Player finished.
echo ======================================================================
pause
