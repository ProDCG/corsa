@echo off
title Ridge-Link Recovery
color 0C
echo.
echo  ╔═══════════════════════════════════════════╗
echo  ║          RIDGE LINK RECOVERY              ║
echo  ║   Kills all running processes, pulls      ║
echo  ║   latest code, and restarts cleanly.      ║
echo  ╚═══════════════════════════════════════════╝
echo.
color 0E

cd /d "%~dp0"

echo  [1/5] Stopping all Python processes...
taskkill /F /IM python.exe 2>nul
taskkill /F /IM pythonw.exe 2>nul
timeout /t 2 /nobreak >nul
echo        Done.
echo.

echo  [2/5] Stopping Mumble...
taskkill /F /IM mumble.exe 2>nul
timeout /t 1 /nobreak >nul
echo        Done.
echo.

echo  [3/5] Closing terminal windows and dashboard...
taskkill /F /IM node.exe 2>nul
timeout /t 1 /nobreak >nul
echo        Done.
echo.

echo  [4/5] Pulling latest code...
git stash --include-untracked 2>nul
git pull --ff-only
if errorlevel 1 (
    echo        WARNING: git pull failed — forcing reset...
    git fetch origin
    git reset --hard origin/main
)
echo        Done.
echo.

echo  [5/5] Restarting Ridge Link...

REM Detect role
if not exist "ridge_role" (
    echo        ERROR: No ridge_role file found. Run bootstrap.py first.
    pause
    exit /b 1
)
for /f %%i in (ridge_role) do set ROLE=%%i

color 0A
echo.
echo  ╔═══════════════════════════════════════════╗
echo  ║          RIDGE LINK RECOVERED!            ║
echo  ║   System is restarting now...             ║
echo  ╚═══════════════════════════════════════════╝
echo.
timeout /t 2 /nobreak >nul

REM Use 'start' (not 'call') so the START script runs in its own process
if "%ROLE%"=="admin" (
    start "" "%~dp0START_ADMIN.bat"
) else (
    start "" "%~dp0START_RIG.bat"
)

REM Close this recovery window
exit
