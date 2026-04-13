@echo off
REM ============================================================
REM  MacMarket-Trader — Windows Task Scheduler setup
REM
REM  Tasks registered:
REM    MacMarket-Strategy-Reports  — weekdays 08:30, runs CLI report job
REM    MacMarket-Backend-Startup   — on system startup, starts uvicorn API
REM    MacMarket-Frontend-Startup  — on system startup, starts Next.js frontend
REM
REM  Run as Administrator. Verify afterwards:
REM    schtasks /query /tn "MacMarket-Strategy-Reports" /v /fo LIST
REM    schtasks /query /tn "MacMarket-Backend-Startup"  /v /fo LIST
REM    schtasks /query /tn "MacMarket-Frontend-Startup" /v /fo LIST
REM ============================================================

setlocal

set BASE_DIR=C:\Dashboard\MacMarket-Trader
set PYTHON_EXE=%BASE_DIR%\.venv\Scripts\python.exe

REM ============================================================
REM  TASK 1 — MacMarket-Strategy-Reports
REM  Schedule: weekdays (Mon-Fri) at 08:30
REM ============================================================

set TASK_NAME=MacMarket-Strategy-Reports

echo.
echo [1/3] Checking for existing task "%TASK_NAME%"...
schtasks /query /tn "%TASK_NAME%" >nul 2>&1

if %ERRORLEVEL% == 0 (
    echo       Task already exists — updating schedule...
    schtasks /change /tn "%TASK_NAME%" ^
        /tr "\"%PYTHON_EXE%\" -m macmarket_trader.cli run-due-strategy-schedules" ^
        /st 08:30
    if %ERRORLEVEL% neq 0 (
        echo ERROR: Failed to update "%TASK_NAME%". Run this script as Administrator.
        exit /b 1
    )
    echo       Updated.
) else (
    echo       Creating "%TASK_NAME%"...
    schtasks /create /tn "%TASK_NAME%" ^
        /tr "\"%PYTHON_EXE%\" -m macmarket_trader.cli run-due-strategy-schedules" ^
        /sc WEEKLY ^
        /d MON,TUE,WED,THU,FRI ^
        /st 08:30 ^
        /ru SYSTEM ^
        /rl HIGHEST ^
        /sd 01/01/2025 ^
        /f
    if %ERRORLEVEL% neq 0 (
        echo ERROR: Failed to create "%TASK_NAME%". Run this script as Administrator.
        exit /b 1
    )
    echo       Created.
)

REM schtasks /change does not support /wd; use PowerShell to set WorkingDirectory.
powershell -NoProfile -Command ^
    "$t = Get-ScheduledTask -TaskName '%TASK_NAME%'; ^
     $t.Actions[0].WorkingDirectory = '%BASE_DIR%'; ^
     Set-ScheduledTask -InputObject $t" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo WARNING: Could not set working directory for "%TASK_NAME%" via PowerShell.
    echo          Ensure DATABASE_URL is an absolute path in the system environment.
)

REM ============================================================
REM  TASK 2 — MacMarket-Backend-Startup
REM  Trigger: ONSTART (system boot)
REM  Only created if it does not already exist.
REM ============================================================

set TASK_NAME=MacMarket-Backend-Startup
set BACKEND_CMD="%PYTHON_EXE%" -m uvicorn macmarket_trader.api.main:app --host 127.0.0.1 --port 9510

echo.
echo [2/3] Checking for existing task "%TASK_NAME%"...
schtasks /query /tn "%TASK_NAME%" >nul 2>&1

if %ERRORLEVEL% == 0 (
    echo       Task already exists — skipping creation.
) else (
    echo       Creating "%TASK_NAME%"...
    schtasks /create /tn "%TASK_NAME%" ^
        /tr %BACKEND_CMD% ^
        /sc ONSTART ^
        /ru SYSTEM ^
        /rl HIGHEST ^
        /f
    if %ERRORLEVEL% neq 0 (
        echo ERROR: Failed to create "%TASK_NAME%". Run this script as Administrator.
        exit /b 1
    )
    echo       Created.

    REM Set working directory via PowerShell.
    powershell -NoProfile -Command ^
        "$t = Get-ScheduledTask -TaskName '%TASK_NAME%'; ^
         $t.Actions[0].WorkingDirectory = '%BASE_DIR%'; ^
         Set-ScheduledTask -InputObject $t" >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo WARNING: Could not set working directory for "%TASK_NAME%" via PowerShell.
    )
)

REM ============================================================
REM  TASK 3 — MacMarket-Frontend-Startup
REM  Trigger: ONSTART (system boot)
REM  Only created if it does not already exist.
REM ============================================================

set TASK_NAME=MacMarket-Frontend-Startup
set FRONTEND_DIR=%BASE_DIR%\apps\web
REM npm.cmd must be on PATH for SYSTEM; wrap in cmd /c to ensure PATH resolution.
set FRONTEND_CMD=cmd /c "npm.cmd run start -- --hostname 0.0.0.0 --port 9500"

echo.
echo [3/3] Checking for existing task "%TASK_NAME%"...
schtasks /query /tn "%TASK_NAME%" >nul 2>&1

if %ERRORLEVEL% == 0 (
    echo       Task already exists — skipping creation.
) else (
    echo       Creating "%TASK_NAME%"...
    schtasks /create /tn "%TASK_NAME%" ^
        /tr "%FRONTEND_CMD%" ^
        /sc ONSTART ^
        /ru SYSTEM ^
        /rl HIGHEST ^
        /f
    if %ERRORLEVEL% neq 0 (
        echo ERROR: Failed to create "%TASK_NAME%". Run this script as Administrator.
        exit /b 1
    )
    echo       Created.

    REM Set working directory via PowerShell.
    powershell -NoProfile -Command ^
        "$t = Get-ScheduledTask -TaskName '%TASK_NAME%'; ^
         $t.Actions[0].WorkingDirectory = '%FRONTEND_DIR%'; ^
         Set-ScheduledTask -InputObject $t" >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo WARNING: Could not set working directory for "%TASK_NAME%" via PowerShell.
    )
)

REM ============================================================

echo.
echo ============================================================
echo  All tasks configured. Summary:
echo.
echo  MacMarket-Strategy-Reports  — weekdays 08:30 (SYSTEM)
echo  MacMarket-Backend-Startup   — on boot, port 9510 (SYSTEM)
echo  MacMarket-Frontend-Startup  — on boot, port 9500 (SYSTEM)
echo.
echo  Verify with:
echo    schtasks /query /tn "MacMarket-Strategy-Reports" /v /fo LIST
echo    schtasks /query /tn "MacMarket-Backend-Startup"  /v /fo LIST
echo    schtasks /query /tn "MacMarket-Frontend-Startup" /v /fo LIST
echo ============================================================
echo.

endlocal
