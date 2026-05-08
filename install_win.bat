@echo off
setlocal
echo === MetaKill installer (Windows) ===

REM Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Install from: https://www.python.org/downloads/
    pause & exit /b 1
)

REM Check Chocolatey
where choco >nul 2>&1
if errorlevel 1 (
    echo.
    echo Chocolatey not found. Install manually:
    echo   exiftool: https://exiftool.org
    echo   ffmpeg:   https://ffmpeg.org/download.html
    echo   Add both to PATH, then rerun this script.
    echo.
    echo OR install Chocolatey from https://chocolatey.org then rerun.
    pause & exit /b 1
)

echo [1/3] Installing exiftool...
choco install exiftool -y

echo [2/3] Installing ffmpeg...
choco install ffmpeg -y

echo [3/3] Installing Pillow...
python -m pip install --upgrade Pillow

echo.
echo Done! Run:
echo   python metakill.py
pause
