@echo off
setlocal enabledelayedexpansion

set REPO_DIR=C:\Dashboard\MacMarket-Trader
set LIVE_DIR=C:\Dashboard\MacMarket-Trader-live
set LOG_DIR=%LIVE_DIR%\logs
set FRONTEND_PORT=9500
set BACKEND_PORT=9510

if not exist %LIVE_DIR% mkdir %LIVE_DIR%
if not exist %LOG_DIR% mkdir %LOG_DIR%

for %%P in (%FRONTEND_PORT% %BACKEND_PORT%) do (
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%%P') do taskkill /F /PID %%a >nul 2>nul
)

cd /d %REPO_DIR%
git fetch --all
git reset --hard origin/main

robocopy %REPO_DIR% %LIVE_DIR% /MIR /XD .git .venv node_modules .next __pycache__ .pytest_cache .mypy_cache >nul

cd /d %LIVE_DIR%
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -e .[dev]

if exist apps\web\package.json (
  cd apps\web
  call npm install
  call npm run build
  cd ..\..
)

alembic upgrade head
pytest

start "macmarket-api" cmd /c "call .venv\Scripts\activate.bat && uvicorn macmarket_trader.api.main:app --host 0.0.0.0 --port %BACKEND_PORT% >> %LOG_DIR%\backend.log 2>&1"
if exist apps\web\package.json (
  start "macmarket-web" cmd /c "cd /d %LIVE_DIR%\apps\web && npm run start >> %LOG_DIR%\frontend.log 2>&1"
) else (
  start "macmarket-api-public" cmd /c "call .venv\Scripts\activate.bat && uvicorn macmarket_trader.api.main:app --host 0.0.0.0 --port %FRONTEND_PORT% >> %LOG_DIR%\backend_public.log 2>&1"
)

echo Deployment completed.
