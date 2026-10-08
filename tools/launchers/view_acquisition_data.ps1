param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Port must be between 1024 and 65535.' }
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $projectRoot
$uri = "http://127.0.0.1:$Port/"
function Open-ViewerPage {
    try { Start-Process -FilePath $uri | Out-Null }
    catch { Write-Warning "Open the viewer manually: $uri" }
}
try {
    $null = Invoke-RestMethod -Uri "${uri}api/status" -TimeoutSec 2
    Write-Output "Viewer already running: $uri"
    Open-ViewerPage
    return
} catch { }
$logDirectory = Join-Path $projectRoot 'data/104/category-runs'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$stdout = Join-Path $logDirectory 'browser-viewer.stdout.log'
$stderr = Join-Path $logDirectory 'browser-viewer.stderr.log'
$venvPython = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (Test-Path -LiteralPath $venvPython) {
    $pythonPath = $venvPython
} else {
    $pythonPath = (Get-Command python -ErrorAction Stop).Source
}
$arguments = @('-X', 'utf8', '-m', 'tools.acquisition.browser_data_viewer', '--port', [string]$Port)
$process = Start-Process -FilePath $pythonPath -ArgumentList $arguments `
    -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 500
    try {
        $null = Invoke-RestMethod -Uri "${uri}api/status" -TimeoutSec 2
        Write-Output "Viewer: $uri"
        Write-Output "PID: $($process.Id)"
        Open-ViewerPage
        return
    } catch { }
}
Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
throw "Viewer did not start. Check $stderr"
