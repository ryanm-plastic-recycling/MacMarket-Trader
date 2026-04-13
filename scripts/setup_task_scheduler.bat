@echo off
REM ============================================================
REM  MacMarket-Trader — Windows Task Scheduler setup
REM  Task name : MacMarket-Strategy-Reports
REM  Schedule  : Weekdays (Mon-Fri) at 08:30
REM  Runs as   : SYSTEM (no interactive login required)
REM
REM  To verify after running:
REM    schtasks /query /tn "MacMarket-Strategy-Reports" /v /fo LIST
REM ============================================================

setlocal

set TASK_NAME=MacMarket-Strategy-Reports
set PYTHON_EXE=C:\Dashboard\MacMarket-Trader\.venv\Scripts\python.exe
set TASK_CMD=%PYTHON_EXE% -m macmarket_trader.cli run-due-strategy-schedules
set WORKING_DIR=C:\Dashboard\MacMarket-Trader

echo.
echo Checking for existing task "%TASK_NAME%"...
schtasks /query /tn "%TASK_NAME%" >nul 2>&1

if %ERRORLEVEL% == 0 (
    echo Task already exists — updating schedule...
    schtasks /change /tn "%TASK_NAME%" ^
        /tr "\"%PYTHON_EXE%\" -m macmarket_trader.cli run-due-strategy-schedules" ^
        /st 08:30
    if %ERRORLEVEL% neq 0 (
        echo ERROR: Failed to update existing task. Run this script as Administrator.
        exit /b 1
    )
    echo Task updated successfully.
) else (
    echo Creating new task "%TASK_NAME%"...
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
        echo ERROR: Failed to create task. Run this script as Administrator.
        exit /b 1
    )
    echo Task created successfully.
)

REM schtasks /change does not support /wd on all Windows versions.
REM Set the working directory via the XML StartIn element using a PowerShell one-liner.
echo Setting working directory to: %WORKING_DIR%
powershell -NoProfile -Command ^
    "$task = Get-ScheduledTask -TaskName '%TASK_NAME%'; ^
     $task.Actions[0].WorkingDirectory = '%WORKING_DIR%'; ^
     Set-ScheduledTask -InputObject $task" >nul 2>&1

if %ERRORLEVEL% neq 0 (
    echo WARNING: Could not set working directory via PowerShell.
    echo          Ensure DATABASE_URL is an absolute path or set it in the system environment.
)

echo.
echo ============================================================
echo  Task "%TASK_NAME%" is configured.
echo  It will run weekdays at 08:30 as SYSTEM.
echo.
echo  Verify with:
echo    schtasks /query /tn "%TASK_NAME%" /v /fo LIST
echo ============================================================
echo.

endlocal
