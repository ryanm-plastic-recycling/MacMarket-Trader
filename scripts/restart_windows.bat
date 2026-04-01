@echo off
setlocal

set APP_ROOT=C:\Dashboard\MacMarket-Trader
set LIVE_DIR=%APP_ROOT%\live
set LOG_DIR=%LIVE_DIR%\logs
set FRONTEND_PORT=9500
set BACKEND_PORT=9510

for %%P in (%FRONTEND_PORT% %BACKEND_PORT%) do (
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%%P') do taskkill /F /PID %%a >nul 2>nul
)

if not exist "%LIVE_DIR%" (
  echo [FAIL] Live directory not found: %LIVE_DIR%
  exit /b 1
)
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

cd /d %LIVE_DIR%
start "macmarket-api" cmd /c "call .venv\Scripts\activate.bat && uvicorn macmarket_trader.api.main:app --host 127.0.0.1 --port %BACKEND_PORT% >> %LOG_DIR%\backend.log 2>&1"
if exist apps\web\package.json start "macmarket-web" cmd /c "cd /d %LIVE_DIR%\apps\web && npm run start -- --hostname 127.0.0.1 --port %FRONTEND_PORT% >> %LOG_DIR%\frontend.log 2>&1"

echo Restart completed.
