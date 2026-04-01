@echo off
setlocal ENABLEDELAYEDEXPANSION

set APP_ROOT=C:\Dashboard\MacMarket-Trader
set REPO_DIR=%APP_ROOT%\repo
set LIVE_DIR=%APP_ROOT%\live
set LOG_DIR=%LIVE_DIR%\logs
set BACKEND_PORT=9510
set FRONTEND_PORT=9500

if not exist "%APP_ROOT%" mkdir "%APP_ROOT%"
if not exist "%LIVE_DIR%" mkdir "%LIVE_DIR%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

if not exist "%REPO_DIR%\.git" (
  echo [FAIL] %REPO_DIR% is not a git clone.
  exit /b 1
)

echo [1/9] Stop running services on %FRONTEND_PORT%/%BACKEND_PORT%...
call :stop_port %FRONTEND_PORT% || goto :fail
call :stop_port %BACKEND_PORT% || goto :fail

echo [2/9] Fetch and reset repository...
git -C "%REPO_DIR%" fetch --all || goto :fail
git -C "%REPO_DIR%" reset --hard origin/main || goto :fail

echo [3/9] Mirror repository into live directory (preserve runtime state)...
robocopy "%REPO_DIR%" "%LIVE_DIR%" /MIR ^
  /XD .git .venv node_modules .next dist build __pycache__ .pytest_cache .mypy_cache .ruff_cache logs data storage uploads ^
  /XF *.pyc *.pyo *.log *.sqlite *.sqlite3 .env
if errorlevel 8 goto :fail

echo [4/9] Create or activate venv...
if not exist "%LIVE_DIR%\.venv\Scripts\python.exe" py -3.12 -m venv "%LIVE_DIR%\.venv" || goto :fail
call "%LIVE_DIR%\.venv\Scripts\activate.bat" || goto :fail
python -m pip install --upgrade pip || goto :fail

echo [5/9] Install backend dependencies...
pushd "%LIVE_DIR%" || goto :fail
pip install -e ".[dev]" || goto :fail

echo [6/9] Initialize database...
python -c "from macmarket_trader.storage.db import init_db; init_db()" || goto :fail

echo [7/9] Run backend tests...
pytest -q || goto :fail

if exist "%LIVE_DIR%\apps\web\package.json" (
  echo [8/9] Build frontend...
  pushd "%LIVE_DIR%\apps\web" || goto :fail
  call npm install || goto :fail
  call npm run build || goto :fail
  popd
) else (
  echo [8/9] Frontend skipped (apps/web/package.json missing).
)

popd

echo [9/9] Start services...
start "MacMarket-Trader API" /MIN cmd /c "cd /d \"%LIVE_DIR%\" && call .venv\Scripts\activate.bat && python -m uvicorn macmarket_trader.api.main:app --host 127.0.0.1 --port %BACKEND_PORT% > \"%LOG_DIR%\api.log\" 2>&1"
if exist "%LIVE_DIR%\apps\web\package.json" (
  start "MacMarket-Trader WEB" /MIN cmd /c "cd /d \"%LIVE_DIR%\apps\web\" && npm run start -- --hostname 127.0.0.1 --port %FRONTEND_PORT% > \"%LOG_DIR%\web.log\" 2>&1"
)

echo Deployment completed successfully.
exit /b 0

:stop_port
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%1 .*LISTENING"') do (
  taskkill /F /PID %%P >nul 2>nul
)
exit /b 0

:fail
echo [FAIL] Deployment stopped at stage above.
exit /b 1
