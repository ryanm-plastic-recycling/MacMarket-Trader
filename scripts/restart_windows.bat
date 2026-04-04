@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "DST=C:\Dashboard\MacMarket-Trader"
set "BACKEND_PORT=9510"
set "FRONTEND_PORT=9500"
set "BACKEND_HOST=127.0.0.1"
set "FRONTEND_HOST=127.0.0.1"

if not "%~1"=="" set "DST=%~1"

set "LOG_DIR=%DST%\logs"
set "WEB_DIR=%DST%\apps\web"

echo.
echo =========================================================
echo Restarting MacMarket-Trader
echo   DST: %DST%
echo =========================================================
echo.

if not exist "%DST%" (
  echo [ERROR] Deployment directory not found:
  echo         %DST%
  pause
  exit /b 1
)

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1

for %%P in (%FRONTEND_PORT% %BACKEND_PORT%) do (
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":%%P .*LISTENING"') do (
    echo [INFO] taskkill /PID %%a on port %%P
    taskkill /F /PID %%a >nul 2>nul
  )
)

echo [INFO] Starting backend...
start "MacMarket-Trader API" /MIN cmd /c "cd /d \"%DST%\" && call .venv\Scripts\activate.bat && python -m uvicorn macmarket_trader.api.main:app --host %BACKEND_HOST% --port %BACKEND_PORT% > \"%LOG_DIR%\backend.log\" 2>&1"

if exist "%WEB_DIR%\package.json" (
  echo [INFO] Starting frontend...
  start "MacMarket-Trader WEB" /MIN cmd /c "cd /d \"%WEB_DIR%\" && npm run start -- --hostname %FRONTEND_HOST% --port %FRONTEND_PORT% > \"%LOG_DIR%\frontend.log\" 2>&1"
)

echo [OK] Restart issued.
pause
exit /b 0
