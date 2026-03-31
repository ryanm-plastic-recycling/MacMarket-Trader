@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ==========================================================
REM MacMarket-Trader Windows deployment script
REM Assumes:
REM   C:\Dashboard\MacMarket-Trader\repo  = local git clone
REM   C:\Dashboard\MacMarket-Trader\live  = runnable deployment copy
REM   C:\Dashboard\MacMarket-Trader\logs  = logs
REM ==========================================================

set APP_ROOT=C:\Dashboard\MacMarket-Trader
set REPO_DIR=%APP_ROOT%\repo
set LIVE_DIR=%APP_ROOT%\live
set LOG_DIR=%APP_ROOT%\logs
set BACKEND_PORT=9510
set PUBLIC_PORT=9500

if not exist "%APP_ROOT%" mkdir "%APP_ROOT%"
if not exist "%LIVE_DIR%" mkdir "%LIVE_DIR%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

if not exist "%REPO_DIR%\.git" (
  echo ERROR: %REPO_DIR% is not a valid git clone.
  echo Clone your repository into %REPO_DIR% first.
  exit /b 1
)

echo [1/8] Stopping running app processes...
call :stop_port %PUBLIC_PORT%
call :stop_port %BACKEND_PORT%

echo [2/8] Pulling latest code...
git -C "%REPO_DIR%" fetch --all || exit /b 1
git -C "%REPO_DIR%" reset --hard origin/main || exit /b 1

echo [3/8] Mirroring repo into live folder...
robocopy "%REPO_DIR%" "%LIVE_DIR%" /MIR ^
  /XD .git .venv node_modules .next dist build __pycache__ .pytest_cache .mypy_cache .ruff_cache ^
  /XF *.pyc *.pyo *.log
if errorlevel 8 exit /b 1

echo [4/8] Ensuring Python virtual environment exists...
if not exist "%LIVE_DIR%\.venv\Scripts\python.exe" (
  py -3.12 -m venv "%LIVE_DIR%\.venv" || exit /b 1
)

call "%LIVE_DIR%\.venv\Scripts\activate.bat" || exit /b 1
python -m pip install --upgrade pip || exit /b 1

pushd "%LIVE_DIR%"
echo [5/8] Installing Python dependencies...
pip install -e ".[dev]" || exit /b 1

echo [6/8] Initializing database...
python -c "from macmarket_trader.storage.db import init_db; init_db()" || exit /b 1

echo [7/8] Running backend test suite...
pytest -q || exit /b 1

if exist "%LIVE_DIR%\apps\web\package.json" (
  echo [7b/8] Installing and building frontend...
  pushd "%LIVE_DIR%\apps\web"
  call npm install || exit /b 1
  call npm run build || exit /b 1
  popd
)

popd

echo [8/8] Starting application...
if exist "%LIVE_DIR%\apps\web\package.json" (
  start "MacMarket-Trader API" /MIN cmd /c "cd /d \"%LIVE_DIR%\" && call .venv\Scripts\activate.bat && python -m uvicorn macmarket_trader.api.main:app --host 127.0.0.1 --port %BACKEND_PORT% > \"%LOG_DIR%\api.log\" 2>&1"
  start "MacMarket-Trader WEB" /MIN cmd /c "cd /d \"%LIVE_DIR%\apps\web\" && npm run start -- --hostname 127.0.0.1 --port %PUBLIC_PORT% > \"%LOG_DIR%\web.log\" 2>&1"
  echo Started frontend on port %PUBLIC_PORT% and backend on port %BACKEND_PORT%.
) else (
  start "MacMarket-Trader API" /MIN cmd /c "cd /d \"%LIVE_DIR%\" && call .venv\Scripts\activate.bat && python -m uvicorn macmarket_trader.api.main:app --host 127.0.0.1 --port %PUBLIC_PORT% > \"%LOG_DIR%\api.log\" 2>&1"
  echo Started backend on port %PUBLIC_PORT%.
)

echo Deployment complete.
exit /b 0

:stop_port
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%1 .*LISTENING"') do (
  taskkill /F /PID %%P >nul 2>nul
)
exit /b 0
