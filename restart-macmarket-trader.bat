@echo off
setlocal ENABLEDELAYEDEXPANSION

set APP_ROOT=C:\Dashboard\MacMarket-Trader
set LIVE_DIR=%APP_ROOT%\live
set LOG_DIR=%APP_ROOT%\logs
set BACKEND_PORT=9510
set PUBLIC_PORT=9500

if not exist "%LIVE_DIR%" (
  echo ERROR: live directory does not exist: %LIVE_DIR%
  exit /b 1
)
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo Stopping running app processes...
call :stop_port %PUBLIC_PORT%
call :stop_port %BACKEND_PORT%

if /I "%~1"=="stoponly" exit /b 0

echo Restarting application...
if exist "%LIVE_DIR%\apps\web\package.json" (
  start "MacMarket-Trader API" /MIN cmd /c "cd /d \"%LIVE_DIR%\" && call .venv\Scripts\activate.bat && python -m uvicorn macmarket_trader.api.main:app --host 127.0.0.1 --port %BACKEND_PORT% > \"%LOG_DIR%\api.log\" 2>&1"
  start "MacMarket-Trader WEB" /MIN cmd /c "cd /d \"%LIVE_DIR%\apps\web\" && npm run start -- --hostname 127.0.0.1 --port %PUBLIC_PORT% > \"%LOG_DIR%\web.log\" 2>&1"
  echo Restarted frontend on port %PUBLIC_PORT% and backend on port %BACKEND_PORT%.
) else (
  start "MacMarket-Trader API" /MIN cmd /c "cd /d \"%LIVE_DIR%\" && call .venv\Scripts\activate.bat && python -m uvicorn macmarket_trader.api.main:app --host 127.0.0.1 --port %PUBLIC_PORT% > \"%LOG_DIR%\api.log\" 2>&1"
  echo Restarted backend on port %PUBLIC_PORT%.
)

exit /b 0

:stop_port
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%1 .*LISTENING"') do (
  taskkill /F /PID %%P >nul 2>nul
)
exit /b 0
