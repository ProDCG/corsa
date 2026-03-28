@echo off
echo ========================================
echo   RIDGE-LINK RIG UPDATE
echo ========================================
echo.
echo [1/3] Pulling latest code...
git pull
echo.
echo [2/3] Killing Python processes...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul
echo.
echo [3/3] Starting rig agent...
call .\START_RIG.bat
