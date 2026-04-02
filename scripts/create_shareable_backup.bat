@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "REPO_NAME=%%~nI"
set "STAMP=%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "STAMP=%STAMP: =0%"
set "OUT=%ROOT%\..\%REPO_NAME%_shareable_%STAMP%.zip"

echo Creating shareable backup: %OUT%
powershell -NoProfile -Command "Compress-Archive -Path '%ROOT%\*' -DestinationPath '%OUT%' -Force -CompressionLevel Optimal -Exclude @('*.pyc','*.pyo','*.db','*.sqlite3','.env','apps\web\.env.local','.git\*','.venv\*','node_modules\*','.next\*','dist\*','coverage\*','htmlcov\*','__pycache__\*','.pytest_cache\*','.mypy_cache\*','.ruff_cache\*','*.log','tmp\*','temp\*')"
if errorlevel 1 (
  echo Backup failed.
  exit /b 1
)

echo Backup created successfully.
