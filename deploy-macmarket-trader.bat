@echo off
setlocal
call "%~dp0scripts\deploy_windows.bat" %*
exit /b %errorlevel%
