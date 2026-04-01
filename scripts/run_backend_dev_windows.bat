@echo off
setlocal
set REPO_ROOT=%~dp0..
cd /d "%REPO_ROOT%"
call .venv\Scripts\activate.bat
uvicorn macmarket_trader.api.main:app --reload --port 9510
