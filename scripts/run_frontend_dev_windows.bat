@echo off
setlocal
set REPO_ROOT=%~dp0..
cd /d "%REPO_ROOT%\apps\web"
call npm install
npm run dev
