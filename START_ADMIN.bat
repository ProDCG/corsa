@echo off
title Ridge-Link Admin
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
if not exist "apps\orchestrator\frontend\node_modules" (
    echo  ERROR: Run "python bootstrap.py" first.
    pause & exit /b 1
)

REM --- Kill previous session ---
taskkill /F /IM python.exe 2>nul
taskkill /F /IM pythonw.exe 2>nul
taskkill /F /IM node.exe 2>nul
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

REM --- Launch backend ---
start "Ridge-Link Backend" /MIN cmd /c "venv\Scripts\python.exe apps\orchestrator\main.py 1>ridge_crash.log 2>&1"
timeout /t 3 /nobreak >nul

REM --- Launch dashboard ---
start "" wscript.exe "%~dp0deploy\run_hidden.vbs" "%~dp0deploy\start_dashboard.bat"
timeout /t 5 /nobreak >nul

REM --- Open browser ---
start http://localhost:5173
exit
