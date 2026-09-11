@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set EXITCODE=0
rem After Ctrl+C, cmd asks Terminate batch job (Y/N).
rem CALL on the same line clears the interrupt flag so you need not press Y.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\desk.ps1" %* & call :_after & call
exit /b %EXITCODE%

:_after
set EXITCODE=%ERRORLEVEL%
if %EXITCODE%==2 (
  echo.
  echo 启动失败，退出码 2。
  pause
)
exit /b %EXITCODE%
