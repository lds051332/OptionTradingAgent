@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\desk.ps1" %*
set EXITCODE=%ERRORLEVEL%
if %EXITCODE%==2 (
  echo.
  echo 启动失败，退出码 2。
  pause
)
exit /b %EXITCODE%
