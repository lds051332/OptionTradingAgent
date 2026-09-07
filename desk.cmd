@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set EXITCODE=0
rem Ctrl+C 后 cmd.exe 会问 Terminate batch job (Y/N)？
rem 同一行接着 CALL，可清掉中断标记，直接退出、不必按 Y。
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
