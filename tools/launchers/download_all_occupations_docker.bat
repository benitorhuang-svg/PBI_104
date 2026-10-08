@echo off
setlocal
set "PROJECT_ROOT=%~dp0..\.."
cd /d "%PROJECT_ROOT%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\tools\launchers\start_distributed_capture.ps1" %*
exit /b %errorlevel%
