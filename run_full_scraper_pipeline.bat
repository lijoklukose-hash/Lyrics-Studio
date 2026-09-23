@echo off
setlocal enabledelayedexpansion

title VerseView Song Lyrics Scraper and Updater
color 0A

echo ======================================================================
echo           VERSEVIEW SONG LYRICS SCRAPER & UPDATER PIPELINE
echo ======================================================================
echo.

:: 1. Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your system PATH!
    echo Please install Python 3.9+ and try again.
    pause
    exit /b 1
)

echo [1/3] Checking and installing required Python libraries...
pip install openpyxl httpx beautifulsoup4 indic-transliteration anyascii regex --quiet --upgrade

if %errorlevel% neq 0 (
    echo [WARNING] Some dependencies had warnings during install, proceeding...
)

echo.
echo [2/3] Running master scraper, deduplicator and transliteration engine...
echo.

python "%~dp0pipeline_master.py"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Pipeline encountered an error!
    pause
    exit /b %errorlevel%
)

echo.
echo [3/3] Process completed successfully!
echo.
echo ======================================================================
echo Updated file: verseview_selected_6_languages.xlsx
echo Backup file : verseview_selected_6_languages_backup.xlsx
echo ======================================================================
echo.

pause
