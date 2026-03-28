@echo off
echo ========================================
echo   RIDGE-LINK ADMIN UPDATE
echo ========================================
echo.
echo [1/3] Pulling latest code...
git pull
echo.
echo [2/3] Killing Python processes...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul
echo.
echo [3/3] Starting admin orchestrator...
call .\START_ADMIN.bat
