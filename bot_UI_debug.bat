@echo off
setlocal
title YouTube History Bot - DEBUG Launcher
cd /d "%~dp0"

echo ============================================================
echo   DEBUG launcher - logs everything to ui_log.txt
echo   This window stays open so you can read any error.
echo ============================================================
echo.

rem Find any Python interpreter (system OR venv)
set "PY="
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
    goto have_py
)
where python >nul 2>nul
if errorlevel 1 goto try_py
set "PY=python"
goto have_py

:try_py
where py >nul 2>nul
if errorlevel 1 goto no_py
set "PY=py"
goto have_py

:no_py
echo [ERROR] Python not found. Install from https://www.python.org/downloads/
echo         and tick "Add python.exe to PATH". Then run this again.
echo.
pause
exit /b 1

:have_py
echo Using Python: %PY%
%PY% --version
echo.
echo Launching bot_ui.py ... (all output captured to ui_log.txt)
echo A browser tab should open at http://localhost:5000 in ~2 seconds.
echo.
%PY% bot_ui.py %* > ui_log.txt 2>&1
set "EC=%errorlevel%"

echo.
echo ============================================================
echo bot_ui.py exited with code %EC%.
echo If it did not start, read the file ui_log.txt in this folder.
echo ============================================================
echo.
echo Press any key to close...
pause >nul
exit /b %EC%
