@echo off
REM ============================================================
REM  MacMarket-Trader — Cloudflare Tunnel startup script
REM
REM  Kills any existing cloudflared process, then runs the
REM  named tunnel in the foreground.
REM
REM  Designed to be launched by Windows Task Scheduler at
REM  user logon (not as SYSTEM) so cloudflared can read the
REM  user credentials stored at:
REM    C:\Users\ryanm\.cloudflared\
REM
REM  Task Scheduler keeps the process alive; terminating the
REM  task also terminates the tunnel.
REM
REM  Usage:
REM    Run scripts\setup_task_scheduler.bat as Administrator
REM    to register the MacMarket-Cloudflare-Tunnel task, then
REM    reboot or trigger it manually via Task Scheduler.
REM ============================================================

setlocal

REM Kill any stale cloudflared processes before starting a new one.
taskkill /IM cloudflared.exe /F >nul 2>&1

REM Short pause to let the old process fully exit.
timeout /t 2 /nobreak >nul

REM Run the named tunnel in the foreground.
REM cloudflared reads credentials from %USERPROFILE%\.cloudflared\
"C:\cloudflared\cloudflared.exe" tunnel run macmarket-trader

endlocal
