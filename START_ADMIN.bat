@echo off
title Ridge-Link Admin
REM ═══════════════════════════════════════════════════
REM  RIDGE-LINK ADMIN LAUNCHER
REM  Double-click to start. Opens dashboard automatically.
REM ═══════════════════════════════════════════════════

cd /d "%~dp0"

REM --- Guard: Check bootstrap has been run ---
if not exist "ridge_role" (
    echo.
    echo  ERROR: Bootstrap has not been run yet!
    echo  Run "python bootstrap.py" first and select "admin".
    echo.
    pause
    exit /b 1
)

REM --- Guard: Check role is "admin" ---
for /f %%i in (ridge_role) do set ROLE=%%i
if not "%ROLE%"=="admin" (
    echo.
    echo  ERROR: This machine is configured as "%ROLE%", not "admin".
    echo  START_ADMIN.bat can only run on machines bootstrapped as admin.
    echo  If this is wrong, re-run "python bootstrap.py" and select "admin".
    echo.
    pause
    exit /b 1
)

REM --- Guard: Check venv exists ---
if not exist "venv\Scripts\python.exe" (
    echo.
    echo  ERROR: Python virtual environment not found.
    echo  Run "python bootstrap.py" first.
    echo.
    pause
    exit /b 1
)

REM --- Guard: Check frontend exists ---
if not exist "apps\orchestrator\frontend\node_modules" (
    echo.
    echo  ERROR: Frontend dependencies not installed.
    echo  Run "python bootstrap.py" first and select "admin".
    echo.
    pause
    exit /b 1
)

REM --- Launch backend (minimized — use python.exe so errors are visible in ridge_crash.log) ---
start "Ridge-Link Backend" /MIN cmd /c "venv\Scripts\python.exe apps\orchestrator\main.py 1>ridge_crash.log 2>&1"

timeout /t 3 /nobreak >nul

REM --- Launch dashboard (fully hidden via VBS) ---
start "" wscript.exe "%~dp0deploy\run_hidden.vbs" "%~dp0deploy\start_dashboard.bat"

timeout /t 5 /nobreak >nul

REM --- Open browser ---
start http://localhost:5173

REM --- Close this launcher window ---
exit
