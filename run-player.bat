@echo off
setlocal
title YouTube History Bot - Player
cd /d "%~dp0"

echo ======================================================================
echo          YouTube History Bot - Player Launcher
echo ======================================================================
echo.

rem Find a working Python interpreter (goto-based flow = reliable)
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
echo (Make sure to check "Add python.exe to PATH" during install)
echo.
pause
exit /b 1

:have_python
if exist ".venv\Scripts\python.exe" goto venv_ready
echo Setting up environment (first run only)...
%PYTHON_CMD% -m venv .venv
if errorlevel 1 goto venv_failed

:venv_ready
echo Checking dependencies...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
".venv\Scripts\python.exe" -m playwright install chromium
echo.
".venv\Scripts\python.exe" auto_player.py %*
set "EXIT_CODE=%errorlevel%"
echo.
echo ======================================================================
echo Player finished (exit code: %EXIT_CODE%).
echo ======================================================================
pause
exit /b %EXIT_CODE%

:venv_failed
echo [ERROR] Failed to create virtual environment!
echo.
pause
exit /b 1
