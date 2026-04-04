@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM =========================================================
REM  MacMarket-Trader - deploy_windows.bat
REM
REM  - Mirrors repo from SRC (folder containing this repo/script) -> DST
REM  - Supports in-place deploy when SRC == DST
REM  - Preserves runtime artifacts in DST (.env, .env.local, venv, DB, logs, uploads)
REM  - Stops existing backend/frontend listeners with hard-kill fallback
REM  - Rebuilds backend/frontend and restarts services
REM  - Optional tests: set RUN_TESTS=1 and/or RUN_E2E=1
REM  - ALWAYS pauses so you can read output
REM =========================================================

set "DST=C:\Dashboard\MacMarket-Trader"
set "BACKEND_PORT=9510"
set "FRONTEND_PORT=9500"
set "BACKEND_HOST=127.0.0.1"
set "FRONTEND_HOST=127.0.0.1"
set "EXPECTED_NODE=v20.19.6"
set "RUN_TESTS=0"
set "RUN_E2E=0"
set "STRICT_NODE=0"

if not "%~1"=="" set "DST=%~1"

REM Repo root = parent of scripts folder
for %%I in ("%~dp0..") do set "SRC=%%~fI"

set "LOG_DIR=%DST%\logs"
set "DATA_DIR=%DST%\data"
set "STORAGE_DIR=%DST%\storage"
set "UPLOAD_DIR=%DST%\uploads"
set "WEB_DIR=%DST%\apps\web"

set "RC=0"

set "KILLPAT_API=*%DST%\.venv\Scripts\python.exe*-m uvicorn*macmarket_trader.api.main:app*"
set "KILLPAT_WEB=*%DST%\apps\web*next*start*"

echo.
echo =========================================================
echo Deploying MacMarket-Trader
echo   SRC: %SRC%
echo   DST: %DST%
echo   RUN_TESTS: %RUN_TESTS%
echo   RUN_E2E : %RUN_E2E%
echo =========================================================
echo.

REM ----- Admin check (warn, do not hard fail) -----
net session >nul 2>&1
if errorlevel 1 (
  echo [WARN] Not running as Administrator. Continuing, but port/process cleanup may be limited.
) else (
  echo [INFO] Running with Administrator privileges.
)

REM ----- Sanity check repo -----
if not exist "%SRC%\README.md" (
  echo [ERROR] Source path does not look like the MacMarket repo:
  echo         %SRC%
  set "RC=1"
  goto :END
)
if not exist "%SRC%\pyproject.toml" (
  echo [ERROR] Missing pyproject.toml in source path:
  echo         %SRC%
  set "RC=1"
  goto :END
)
if not exist "%SRC%\apps\web\package.json" (
  echo [WARN] apps\web\package.json not found in source. Frontend steps will be skipped.
)

REM ----- Ensure destination folders -----
if not exist "%DST%" mkdir "%DST%" >nul 2>&1
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%" >nul 2>&1
if not exist "%STORAGE_DIR%" mkdir "%STORAGE_DIR%" >nul 2>&1
if not exist "%UPLOAD_DIR%" mkdir "%UPLOAD_DIR%" >nul 2>&1

REM ----- Node version guidance -----
call :CheckNode
if errorlevel 1 (
  set "RC=1"
  goto :END
)

REM ----- Stop listeners and stray processes -----
echo [INFO] Stopping listeners on %FRONTEND_PORT% / %BACKEND_PORT%...
call :StopPort "%FRONTEND_PORT%"
call :StopPort "%BACKEND_PORT%"
call :KillByCmdLine "%KILLPAT_API%"
call :KillByCmdLine "%KILLPAT_WEB%"

echo.
if /I "%SRC%"=="%DST%" (
  echo [INFO] Source and destination are the same. Skipping mirror step.
) else (
  echo [INFO] Mirroring repo to deployment folder (preserving runtime artifacts)...
  robocopy "%SRC%" "%DST%" /MIR /R:2 /W:2 /FFT /Z /NP ^
    /XD ".git" ".venv" "__pycache__" ".pytest_cache" ".mypy_cache" ".ruff_cache" ^
        "logs" "data" "storage" "uploads" ^
        "node_modules" ".next" "dist" "build" "playwright-report" "test-results" ^
        "apps\web\node_modules" "apps\web\.next" ^
    /XF ".env" ".env.local" "*.log" "*.pyc" "*.pyo" "*.sqlite" "*.sqlite3" "*.db"
  set "ROBO=%ERRORLEVEL%"
  if %ROBO% GEQ 8 (
    echo [ERROR] Robocopy failed with code %ROBO%.
    set "RC=%ROBO%"
    goto :END
  )
)

echo.
if not exist "%DST%\.env" (
  echo [WARN] %DST%\.env not found. Backend may fail until runtime env is created.
)
if exist "%WEB_DIR%\package.json" if not exist "%WEB_DIR%\.env.local" (
  echo [WARN] %WEB_DIR%\.env.local not found. Frontend may fail until runtime env is created.
)

echo [INFO] Creating or reusing Python virtual environment...
if not exist "%DST%\.venv\Scripts\python.exe" (
  py -3.12 -m venv "%DST%\.venv"
  if errorlevel 1 (
    echo [ERROR] Failed to create Python 3.12 venv.
    set "RC=1"
    goto :END
  )
)
call "%DST%\.venv\Scripts\activate.bat"
if errorlevel 1 (
  echo [ERROR] Failed to activate venv.
  set "RC=1"
  goto :END
)

pushd "%DST%"
echo [INFO] Installing backend dependencies...
python -m pip install --upgrade pip
if errorlevel 1 (
  set "RC=1"
  goto :FAIL_POP
)
pip install -e ".[dev]"
if errorlevel 1 (
  echo [ERROR] Backend dependency install failed.
  set "RC=1"
  goto :FAIL_POP
)

echo [INFO] Initializing database...
python -c "from macmarket_trader.storage.db import init_db; init_db()"
if errorlevel 1 (
  echo [ERROR] Database initialization failed.
  set "RC=1"
  goto :FAIL_POP
)

if "%RUN_TESTS%"=="1" (
  echo [INFO] Running backend tests...
  pytest -q
  if errorlevel 1 (
    echo [ERROR] Backend tests failed.
    set "RC=1"
    goto :FAIL_POP
  )
) else (
  echo [INFO] Backend tests skipped. Set RUN_TESTS=1 to enable them.
)

if exist "%WEB_DIR%\package.json" (
  echo.
  echo [INFO] Installing frontend dependencies...
  pushd "%WEB_DIR%"
  if exist "package-lock.json" (
    call npm ci
  ) else (
    call npm install
  )
  if errorlevel 1 (
    echo [ERROR] Frontend dependency install failed.
    set "RC=1"
    goto :FAIL_POP_WEB
  )

  echo [INFO] Building frontend...
  call npm run build
  if errorlevel 1 (
    echo [ERROR] Frontend build failed.
    set "RC=1"
    goto :FAIL_POP_WEB
  )

  if "%RUN_TESTS%"=="1" (
    echo [INFO] Running frontend unit tests...
    call npm test
    if errorlevel 1 (
      echo [ERROR] Frontend unit tests failed.
      set "RC=1"
      goto :FAIL_POP_WEB
    )
  ) else (
    echo [INFO] Frontend unit tests skipped. Set RUN_TESTS=1 to enable them.
  )

  if "%RUN_E2E%"=="1" (
    echo [INFO] Installing Playwright browsers...
    call npx playwright install
    if errorlevel 1 (
      echo [ERROR] Playwright browser install failed.
      set "RC=1"
      goto :FAIL_POP_WEB
    )

    echo [INFO] Running Playwright E2E...
    call npm run test:e2e
    if errorlevel 1 (
      echo [ERROR] Playwright E2E failed.
      set "RC=1"
      goto :FAIL_POP_WEB
    )
  ) else (
    echo [INFO] Playwright E2E skipped. Set RUN_E2E=1 to enable them.
  )

  popd
)

popd

echo.
echo [INFO] Starting backend...
start "MacMarket-Trader API" /MIN cmd /c "cd /d \"%DST%\" && call .venv\Scripts\activate.bat && python -m uvicorn macmarket_trader.api.main:app --host %BACKEND_HOST% --port %BACKEND_PORT% > \"%LOG_DIR%\backend.log\" 2>&1"

if exist "%WEB_DIR%\package.json" (
  echo [INFO] Starting frontend...
  start "MacMarket-Trader WEB" /MIN cmd /c "cd /d \"%WEB_DIR%\" && npm run start -- --hostname %FRONTEND_HOST% --port %FRONTEND_PORT% > \"%LOG_DIR%\frontend.log\" 2>&1"
)

echo [INFO] Waiting for backend health...
call :WaitForHttp "http://%BACKEND_HOST%:%BACKEND_PORT%/health" "backend /health" "60"
if errorlevel 1 (
  echo [ERROR] Backend health check did not pass in time.
  set "RC=1"
  goto :END
)

if exist "%WEB_DIR%\package.json" (
  echo [INFO] Waiting for frontend root...
  call :WaitForHttp "http://%FRONTEND_HOST%:%FRONTEND_PORT%/" "frontend root" "90"
  if errorlevel 1 (
    echo [ERROR] Frontend did not respond in time.
    set "RC=1"
    goto :END
  )
)

echo.
echo [OK] Deployment completed successfully.
goto :END

:FAIL_POP_WEB
popd

:FAIL_POP
popd
goto :END

:CheckNode
for /f %%V in ('node -v 2^>nul') do set "NODE_VER=%%V"
if not defined NODE_VER (
  echo [ERROR] Node was not found on PATH.
  exit /b 1
)
if /I "!NODE_VER!"=="%EXPECTED_NODE%" (
  echo [INFO] Node version OK: !NODE_VER!
  exit /b 0
)

echo [WARN] Node version mismatch: found !NODE_VER!, expected %EXPECTED_NODE%.
if "%STRICT_NODE%"=="1" (
  echo [ERROR] STRICT_NODE=1, refusing to continue.
  exit /b 1
)
echo [WARN] Continuing because STRICT_NODE=0. For reliable verification, use %EXPECTED_NODE%.
exit /b 0

:StopPort
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%~1 .*LISTENING"') do (
  echo [INFO] taskkill /PID %%P on port %~1
  taskkill /F /PID %%P >nul 2>nul
)
exit /b 0

:KillByCmdLine
set "PAT=%~1"
if "%PAT%"=="" exit /b 0
powershell -NoProfile -Command ^
  "$pat = '%PAT%';" ^
  "$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -like $pat };" ^
  "if(-not $procs){ exit 0 }" ^
  "foreach($p in $procs){ Write-Host ('[INFO] taskkill /PID ' + $p.ProcessId); & taskkill.exe /PID $p.ProcessId /F /T 2>$null | Out-Null }"
exit /b 0

:WaitForHttp
set "URL=%~1"
set "LABEL=%~2"
set "TIMEOUT=%~3"
powershell -NoProfile -Command ^
  "$url = '%URL%';" ^
  "$label = '%LABEL%';" ^
  "$deadline = (Get-Date).AddSeconds([int]'%TIMEOUT%');" ^
  "do {" ^
  "  try {" ^
  "    $resp = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 5;" ^
  "    if($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {" ^
  "      Write-Host ('[INFO] HTTP ready: ' + $label + ' -> ' + $resp.StatusCode);" ^
  "      exit 0" ^
  "    }" ^
  "  } catch { Start-Sleep -Seconds 1 }" ^
  "} while((Get-Date) -lt $deadline);" ^
  "exit 1"
exit /b %errorlevel%

:END
echo.
echo Deployment exit code: %RC%
pause
exit /b %RC%
