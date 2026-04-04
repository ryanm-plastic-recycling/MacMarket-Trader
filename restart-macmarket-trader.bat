@echo off
setlocal
call "%~dp0scripts\restart_windows.bat" %*
exit /b %errorlevel%
