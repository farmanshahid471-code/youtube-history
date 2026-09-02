@echo off
cd /d %~dp0
where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Install Python 3.10+ from https://python.org
  echo (tick "Add python.exe to PATH" during install) and run this file again.
  pause
  exit /b 1
)
if not exist .venv (
  echo Setting up environment (first run only)...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo.
python research_bot.py
echo.
pause
