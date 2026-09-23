@echo off
title Lyrics Studio - Scraper, Editor & Duplicate Resolver
echo ============================================================
echo         STARTING LYRICS STUDIO (PORT 1995)
echo ============================================================
echo.
echo Launching local server...
if exist "%~dp0.env" (
    for /F "usebackq eol=# tokens=1,* delims==" %%A in ("%~dp0.env") do set "%%A=%%B"
)

where python >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python 3 is required. Install Python 3.9+ and add it to PATH.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=py -3"
)

start "" http://127.0.0.1:1995
%PYTHON_CMD% -m uvicorn app.main:app --host 127.0.0.1 --port 1995 --reload
pause
