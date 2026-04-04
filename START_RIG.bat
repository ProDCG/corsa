@echo off
title Ridge-Link Rig
cd /d "%~dp0"

REM --- Guard: bootstrap ---
if not exist "ridge_role" (
    echo  ERROR: Run "python bootstrap.py" first.
    pause & exit /b 1
)
if not exist "venv\Scripts\python.exe" (
    echo  ERROR: Run "python bootstrap.py" first.
    pause & exit /b 1
)
if not exist "apps\sled\config.json" (
    echo  ERROR: Run "python bootstrap.py" first.
    pause & exit /b 1
)

REM --- Kill previous session ---
taskkill /F /IM python.exe 2>nul
taskkill /F /IM pythonw.exe 2>nul
taskkill /F /IM mumble-server.exe 2>nul
taskkill /F /IM murmur.exe 2>nul
timeout /t 2 /nobreak >nul

REM --- Pull latest code ---
git pull --ff-only 2>nul
if errorlevel 1 (
    git stash --include-untracked 2>nul
    git fetch origin 2>nul
    git reset --hard origin/main 2>nul
)

REM --- Launch rig agent ---
start "" /B "venv\Scripts\pythonw.exe" -m apps.sled.splash 2>"ridge_crash.log"
exit
