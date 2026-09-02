@echo off
setlocal enabledelayedexpansion
title YouTube History Bot - Research Scanner
cd /d "%~dp0"

echo ======================================================================
echo          YouTube History Bot - Research Scanner
echo ======================================================================
echo.

set "PYTHON_CMD="
where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set "PYTHON_CMD=py"
    )
)

if "%PYTHON_CMD%"=="" (
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

echo.
".venv\Scripts\python.exe" research_bot.py %*
echo.
echo ======================================================================
echo Research scan finished.
echo ======================================================================
pause
