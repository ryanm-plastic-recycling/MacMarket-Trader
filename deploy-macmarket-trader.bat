@echo off
setlocal
call "%~dp0scripts\deploy_windows.bat" %*
pause
exit /b %errorlevel%
