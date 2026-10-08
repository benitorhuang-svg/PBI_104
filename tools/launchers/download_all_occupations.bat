@echo off
setlocal
set "PROJECT_ROOT=%~dp0..\.."
cd /d "%PROJECT_ROOT%"
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$active = Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*.exe' -and $_.CommandLine -match 'capture_category_matrix\.py|pbi104_resume_incomplete_categories\.py' }; if ($active) { Write-Output 'A 104 occupation capture is already running.'; exit 1 }"
if errorlevel 1 goto already_running

python -c "import pandas, cloudscraper, psycopg; print('Python dependencies OK')"
if errorlevel 1 goto missing_dependencies

echo Starting full occupation-category capture to PostgreSQL.
echo Existing batches committed today will be skipped; progress is shown below.
python -u tools\capture_category_matrix.py --output data\104 --depth 2 --capture --direct-postgres --resume --pagesize 30 --delay 3.2 --workers 1 --category-workers 2
set "RESULT=%ERRORLEVEL%"
if "%RESULT%"=="0" (
  echo.
  echo Capture completed successfully.
) else (
  echo.
  echo Capture stopped with exit code %RESULT%. Rerun this file to resume today's committed categories.
)
pause
exit /b %RESULT%

:already_running
echo Another 104 occupation capture is already running. This run was not started.
pause
exit /b 2

:missing_dependencies
echo Required Python packages are missing. Install tools\requirements-dev.txt, then rerun this file.
pause
exit /b 3
