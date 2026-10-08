param(
  [ValidateSet('Parse', 'Inventory', 'ImportQueries', 'Dax')]
  [string]$Operation = 'Parse',
  [string]$QueryFile
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$app = Get-AppxPackage '*PowerBI*' | Select-Object -First 1
$bin = Join-Path $app.InstallLocation 'bin'
foreach ($dll in @('Microsoft.PowerBI.Tabular.dll', 'Microsoft.PowerBI.Tabular.Json.dll')) {
  [Reflection.Assembly]::LoadFrom((Join-Path $bin $dll)) | Out-Null
}
$definition = Join-Path $projectRoot 'PBI_104.SemanticModel\definition'
if ($Operation -eq 'Parse') {
  $database = [Microsoft.AnalysisServices.Tabular.TmdlSerializer]::DeserializeDatabaseFromFolder($definition)
  [pscustomobject]@{Result='PASS'; Tables=$database.Model.Tables.Count; Expressions=$database.Model.Expressions.Count; Relationships=$database.Model.Relationships.Count} | ConvertTo-Json -Compress
  exit
}
$instances = @(Get-Process msmdsrv -ErrorAction SilentlyContinue)
if ($instances.Count -ne 1) { throw 'Expected exactly one open Desktop model; no model was modified.' }
$ports = @(Get-NetTCPConnection -OwningProcess $instances[0].Id -State Listen | Select-Object -ExpandProperty LocalPort -Unique)
if ($ports.Count -ne 1) { throw 'Desktop model port is ambiguous.' }
$server = [Microsoft.AnalysisServices.Tabular.Server]::new()
$server.Connect("localhost:$($ports[0])")
try {
  $modelDatabases = @($server.Databases | Where-Object { $_.Model.Tables.Count -gt 0 })
  if ($modelDatabases.Count -ne 1) { throw 'Expected exactly one Desktop database with model tables.' }
  $database = $modelDatabases[0]
  $model = $database.Model
  if ($Operation -eq 'Inventory') {
    [pscustomobject]@{Tables=@($model.Tables | ForEach-Object { [pscustomobject]@{Name=$_.Name;Columns=$_.Columns.Count;Partitions=@($_.Partitions | ForEach-Object { [pscustomobject]@{Name=$_.Name;State=$_.State.ToString()} })} }); Expressions=$model.Expressions.Count; Relationships=$model.Relationships.Count} | ConvertTo-Json -Depth 6 -Compress
  } elseif ($Operation -eq 'ImportQueries') {
    $disk = [Microsoft.AnalysisServices.Tabular.TmdlSerializer]::DeserializeDatabaseFromFolder($definition)
    foreach ($expression in $disk.Model.Expressions) {
      if ($model.Expressions.Contains($expression.Name)) { $model.Expressions[$expression.Name].Expression = $expression.Expression }
      else { $model.Expressions.Add($expression.Clone()) }
    }
    $model.SaveChanges() | Out-Null
    Write-Output 'Imported M expressions; tables, measures and relationships unchanged.'
  }
  if ($Operation -eq 'Dax') {
    if ([string]::IsNullOrWhiteSpace($QueryFile) -or -not (Test-Path -LiteralPath $QueryFile -PathType Leaf)) {
      throw 'Dax requires an existing read-only query file.'
    }
    [Reflection.Assembly]::LoadFrom((Join-Path $bin 'Microsoft.PowerBI.AdomdClient.dll')) | Out-Null
    $connection = [Microsoft.AnalysisServices.AdomdClient.AdomdConnection]::new("Data Source=localhost:$($ports[0]);Initial Catalog=$($database.ID)")
    try {
      $connection.Open()
      $command = $connection.CreateCommand()
      $command.CommandTimeout = 120
      $command.CommandText = Get-Content -LiteralPath $QueryFile -Raw -Encoding UTF8
      $reader = $command.ExecuteReader()
      $rows = @()
      while ($reader.Read()) {
        $row = [ordered]@{}
        for ($index=0; $index -lt $reader.FieldCount; $index++) { $row[$reader.GetName($index)] = $reader.GetValue($index) }
        $rows += [pscustomobject]$row
      }
      $rows | ConvertTo-Json -Depth 5 -Compress
      $reader.Close()
    } finally { $connection.Dispose() }
  }
} finally { $server.Disconnect() }
