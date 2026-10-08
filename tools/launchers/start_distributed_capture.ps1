$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $projectRoot

$settings = @{}
$envPath = Join-Path $projectRoot '.env'
if (Test-Path -LiteralPath $envPath) {
    foreach ($line in Get-Content -LiteralPath $envPath -Encoding utf8) {
        if ($line -match '^\s*([^#=]+?)\s*=\s*(.*?)\s*$') {
            $settings[$matches[1].Trim()] = $matches[2].Trim().Trim('"').Trim("'")
        }
    }
}

$workerCount = 3
if ($settings.ContainsKey('PBI104_CAPTURE_WORKERS')) {
    $workerCount = [int]$settings['PBI104_CAPTURE_WORKERS']
}
if ($workerCount -lt 1 -or $workerCount -gt 4) {
    throw 'PBI104_CAPTURE_WORKERS must be between 1 and 4.'
}

$delay = '0.8'
if ($settings.ContainsKey('PBI104_CAPTURE_DELAY_SECONDS')) {
    $delay = $settings['PBI104_CAPTURE_DELAY_SECONDS']
}
$null = [double]::Parse($delay, [Globalization.CultureInfo]::InvariantCulture)
$workerRuntime = 'host'
if ($settings.ContainsKey('PBI104_CAPTURE_RUNTIME')) {
    $workerRuntime = $settings['PBI104_CAPTURE_RUNTIME'].ToLowerInvariant()
}
if ($workerRuntime -notin @('host', 'container')) {
    throw 'PBI104_CAPTURE_RUNTIME must be host or container.'
}
$env:PBI104_CAPTURE_WORKERS = [string]$workerCount
$env:PBI104_CAPTURE_DELAY_SECONDS = $delay

if ($workerRuntime -eq 'host') {
    & python -X utf8 -c "import cloudscraper, pandas, psycopg"
    if ($LASTEXITCODE -ne 0) { throw 'Host ETL dependencies are unavailable.' }
    & python -X utf8 -m tools.acquisition.distributed_coordinator `
        --depth 2 --pagesize 30 --delay $delay --workers $workerCount
} else {
    docker compose --profile acquisition run --build --rm etl-coordinator
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($workerRuntime -eq 'container') {
    docker compose --profile acquisition up --build --detach `
        --scale "etl-worker=$workerCount" etl-worker
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    docker compose --profile acquisition run --rm etl-coordinator `
        python -m tools.acquisition.distributed_coordinator --status
    exit $LASTEXITCODE
}

$logDirectory = Join-Path $projectRoot 'data/104/category-runs'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$runStamp = (Get-Date -Format 'yyyyMMddTHHmmss') + '-' +
    [guid]::NewGuid().ToString('N').Substring(0, 8)
$pythonPath = (Get-Command python -ErrorAction Stop).Source
for ($worker = 1; $worker -le $workerCount; $worker++) {
    $stdout = Join-Path $logDirectory "host-worker-$runStamp-$worker.stdout.log"
    $stderr = Join-Path $logDirectory "host-worker-$runStamp-$worker.stderr.log"
    $arguments = @('-X', 'utf8', '-m', 'tools.acquisition.distributed_worker',
                   '--delay', $delay, '--poll-seconds', '5',
                   '--idle-exit-seconds', '20')
    $process = Start-Process -FilePath $pythonPath -ArgumentList $arguments `
        -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    Write-Output "Started host ETL worker PID $($process.Id); log: $stdout"
}
& python -X utf8 -m tools.acquisition.distributed_coordinator --status
exit $LASTEXITCODE
