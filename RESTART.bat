@echo off
title Ridge-Link Restart
REM ═══════════════════════════════════════════════════
REM  RIDGE-LINK UNIVERSAL RESTART
REM  One script to rule them all.
REM  Kills everything, pulls latest code, restarts.
REM  Works for both Admin and Rig machines.
REM ═══════════════════════════════════════════════════

cd /d "%~dp0"

REM --- Guard: Check bootstrap has been run ---
if not exist "ridge_role" (
    echo.
    echo  ERROR: Bootstrap has not been run yet!
    echo  Run "python bootstrap.py" first.
    echo.
    pause
    exit /b 1
)
for /f %%i in (ridge_role) do set ROLE=%%i

color 0E
echo.
echo  ╔═══════════════════════════════════════════╗
echo  ║          RIDGE-LINK RESTART               ║
echo  ║   Role: %ROLE%                               ║
echo  ╚═══════════════════════════════════════════╝
echo.

REM ──────────────────────────────────────────────
REM  STEP 1: Kill everything
REM ──────────────────────────────────────────────
echo  [1/3] Stopping all processes...
taskkill /F /IM python.exe 2>nul
taskkill /F /IM pythonw.exe 2>nul
taskkill /F /IM node.exe 2>nul
taskkill /F /IM mumble-server.exe 2>nul
taskkill /F /IM murmur.exe 2>nul
taskkill /F /IM mumble.exe 2>nul
timeout /t 2 /nobreak >nul
echo        Done.
echo.

REM ──────────────────────────────────────────────
REM  STEP 2: Pull latest code
REM ──────────────────────────────────────────────
echo  [2/3] Pulling latest code...
git stash --include-untracked 2>nul
git pull --ff-only
if errorlevel 1 (
    echo        WARNING: git pull failed — forcing reset...
    git fetch origin
    git reset --hard origin/main
)
echo        Done.
echo.

REM ──────────────────────────────────────────────
REM  STEP 3: Restart based on role
REM ──────────────────────────────────────────────
echo  [3/3] Starting Ridge-Link as %ROLE%...

if "%ROLE%"=="admin" (
    start "" "%~dp0START_ADMIN.bat"
) else (
    start "" "%~dp0START_RIG.bat"
)

color 0A
echo.
echo  ╔═══════════════════════════════════════════╗
echo  ║          RIDGE-LINK RESTARTED!            ║
echo  ╚═══════════════════════════════════════════╝
echo.
timeout /t 3 /nobreak >nul
exit
