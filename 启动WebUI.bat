@echo off
cd /d "%~dp0"
echo ================================
echo   CxKitty Web UI Starting...
echo ================================
echo.
D:\python\python.exe -m web.app
pause
