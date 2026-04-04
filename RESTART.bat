@echo off
REM Auto-detect role and call the right START script.
cd /d "%~dp0"
if not exist "ridge_role" (
    echo  ERROR: Run "python bootstrap.py" first.
    pause & exit /b 1
)
for /f %%i in (ridge_role) do set ROLE=%%i
if "%ROLE%"=="admin" (
    call "%~dp0START_ADMIN.bat"
) else (
    call "%~dp0START_RIG.bat"
)
