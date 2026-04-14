@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM =========================================================
REM  MacMarket-Trader - deploy_windows.bat
REM =========================================================

set "DST=C:\Dashboard\MacMarket-Trader"
set "BACKEND_PORT=9510"
set "FRONTEND_PORT=9500"
set "BACKEND_HOST=localhost"
set "FRONTEND_HOST=localhost"
set "EXPECTED_NODE_MAJOR=v20"
set "EXPECTED_NODE_DISPLAY=any supported v20.x release"
set "RUN_TESTS=1"
set "RUN_E2E=0"
set "STRICT_NODE=0"

if not "%~1"=="" set "DST=%~1"

for %%I in ("%~dp0..") do set "SRC=%%~fI"

set "LOG_DIR=%DST%\logs"
set "DATA_DIR=%DST%\data"
set "STORAGE_DIR=%DST%\storage"
set "UPLOAD_DIR=%DST%\uploads"
set "WEB_DIR=%DST%\apps\web"
set "BACKEND_LOG=%LOG_DIR%\backend.log"
set "FRONTEND_LOG=%LOG_DIR%\frontend.log"

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

net session >nul 2>&1
if errorlevel 1 (
  echo [WARN] Not running as Administrator. Continuing, but port/process cleanup may be limited.
) else (
  echo [INFO] Running with Administrator privileges.
)

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

if not exist "%DST%" mkdir "%DST%" >nul 2>&1
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%" >nul 2>&1
if not exist "%STORAGE_DIR%" mkdir "%STORAGE_DIR%" >nul 2>&1
if not exist "%UPLOAD_DIR%" mkdir "%UPLOAD_DIR%" >nul 2>&1

call :CheckNode
if errorlevel 1 (
  set "RC=1"
  goto :END
)

echo [INFO] Stopping listeners on %FRONTEND_PORT% / %BACKEND_PORT%...
call :StopPort "%FRONTEND_PORT%"
call :StopPort "%BACKEND_PORT%"
call :KillByCmdLine "%KILLPAT_API%"
call :KillByCmdLine "%KILLPAT_WEB%"

echo.
if /I "%SRC%"=="%DST%" goto :SKIP_MIRROR

echo [INFO] Mirroring repo to deployment folder (preserving runtime artifacts)...
robocopy "%SRC%" "%DST%" /MIR /R:2 /W:2 /FFT /Z /NP ^
  /XD ".git" ".venv" "__pycache__" ".pytest_cache" ".mypy_cache" ".ruff_cache" ^
      "logs" "uploads" "backups" ^
      "node_modules" ".next" "dist" "build" "playwright-report" "test-results" ^
      ".clerk" "apps\web\node_modules" "apps\web\.next" ^
  /XF ".env" ".env.local" "*.log" "*.pyc" "*.pyo" "*.sqlite" "*.sqlite3" "*.db"

set "ROBO=%ERRORLEVEL%"
if %ROBO% GEQ 8 (
  echo [ERROR] Robocopy failed with code %ROBO%.
  set "RC=%ROBO%"
  goto :END
)
goto :AFTER_MIRROR

:SKIP_MIRROR
echo [INFO] Source and destination are the same. Skipping mirror step.

:AFTER_MIRROR

echo.
if not exist "%DST%\.env" (
  echo [WARN] %DST%\.env not found. Backend may fail until runtime env is created.
)
if exist "%WEB_DIR%\package.json" if not exist "%WEB_DIR%\.env.local" (
  echo [WARN] %WEB_DIR%\.env.local not found. Frontend may fail until runtime env is created.
)

echo [INFO] Creating or reusing Python virtual environment...
if not exist "%DST%\.venv\Scripts\python.exe" (
  py -3.13 -m venv "%DST%\.venv"
  if errorlevel 1 (
    echo [ERROR] Failed to create Python 3.13 venv.
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

echo [INFO] Checking database state...
if not exist "%DST%\macmarket_trader.db" (
  echo [INFO] No existing database found. Initializing fresh schema...
  python -c "from macmarket_trader.storage.db import init_db; init_db()"
  if errorlevel 1 (
    echo [ERROR] Database initialization failed.
    set "RC=1"
    goto :FAIL_POP
  )
) else (
  echo [INFO] Existing database found. Applying schema updates...
  python -c "from macmarket_trader.storage.db import apply_schema_updates; added = apply_schema_updates(); print('[INFO] Schema columns added:', added) if added else print('[INFO] Schema already current.')"
  if errorlevel 1 (
    echo [ERROR] Schema update failed.
    set "RC=1"
    goto :FAIL_POP
  )
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
    echo [WARN] Clean frontend install failed. Retrying with legacy peer dependency resolution...
    call npm install --legacy-peer-deps
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
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
start "MacMarket-Trader API" /MIN /D "%DST%" cmd /c ""%DST%\.venv\Scripts\python.exe" -m uvicorn macmarket_trader.api.main:app --host %BACKEND_HOST% --port %BACKEND_PORT% >> "%BACKEND_LOG%" 2>&1"

if exist "%WEB_DIR%\package.json" (
  echo [INFO] Starting frontend...
  timeout /t 5 /nobreak >nul
  start "MacMarket-Trader WEB" /MIN /D "%WEB_DIR%" cmd /c "npm.cmd run start -- --hostname 0.0.0.0 --port %FRONTEND_PORT% >> "%FRONTEND_LOG%" 2>&1"
)

echo [INFO] Waiting for backend health...
timeout /t 10 /nobreak >nul
call :WaitForHttp "http://%BACKEND_HOST%:%BACKEND_PORT%/health" "backend /health" "180"
if errorlevel 1 (
  echo [ERROR] Backend health check did not pass in time.
  call :ShowLogTail "%BACKEND_LOG%" "backend"
  set "RC=1"
  goto :END
)

if exist "%WEB_DIR%\package.json" (
  echo [INFO] Waiting for frontend root...
  call :WaitForHttp "http://127.0.0.1:%FRONTEND_PORT%/sign-in" "frontend sign-in" "300"
  if errorlevel 1 (
    echo [ERROR] Frontend did not respond in time.
    call :ShowLogTail "%FRONTEND_LOG%" "frontend"
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
if /I "!NODE_VER:~0,3!"=="%EXPECTED_NODE_MAJOR%" (
  echo [INFO] Node version OK: !NODE_VER!
  exit /b 0
)

echo [WARN] Node version mismatch: found !NODE_VER!, expected %EXPECTED_NODE_DISPLAY%.
if "%STRICT_NODE%"=="1" (
  echo [ERROR] STRICT_NODE=1, refusing to continue.
  exit /b 1
)
echo [WARN] Continuing because STRICT_NODE=0. For reliable verification, use a supported Node 20.x version.
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
powershell -NoProfile -Command "$pat='%PAT%'; $procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -like $pat }); foreach($p in $procs){ Write-Host ('[INFO] taskkill /PID ' + $p.ProcessId); Start-Process -FilePath taskkill.exe -ArgumentList '/PID', $p.ProcessId, '/F', '/T' -NoNewWindow -Wait }"
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

:ShowLogTail
set "LOG_FILE=%~1"
set "LOG_LABEL=%~2"
if exist "%LOG_FILE%" (
  echo [INFO] Last %LOG_LABEL% log lines:
  powershell -NoProfile -Command "Get-Content -Path '%LOG_FILE%' -Tail 50"
) else (
  echo [WARN] %LOG_LABEL% log file not found: %LOG_FILE%
)
exit /b 0

:END
echo.
echo Deployment exit code: %RC%
pause
exit /b %RC%
