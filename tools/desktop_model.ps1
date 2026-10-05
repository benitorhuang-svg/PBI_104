param(
  [ValidateSet('Parse', 'Inventory', 'ImportQueries', 'Probe', 'Dax')]
  [string]$Operation = 'Parse',
  [string]$QueryFile,
  [string]$ProbeName = 'TASK007_Probe'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
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
  if ($server.Databases.Count -ne 1) { throw 'Expected one Desktop database.' }
  $database = $server.Databases[0]
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
  } elseif ($Operation -eq 'Probe') {
    if (-not $ProbeName.StartsWith('TASK007_')) { throw 'Only explicitly temporary TASK007_ probes are allowed.' }
    if ($model.Tables.Contains($ProbeName)) { throw 'Probe already exists; preserve it and inspect.' }
    $table = [Microsoft.AnalysisServices.Tabular.Table]::new()
    $table.Name = $ProbeName
    $column = [Microsoft.AnalysisServices.Tabular.DataColumn]::new()
    $column.Name = 'Result'
    $column.SourceColumn = 'Result'
    $column.DataType = [Microsoft.AnalysisServices.Tabular.DataType]::String
    $table.Columns.Add($column)
    $partition = [Microsoft.AnalysisServices.Tabular.Partition]::new()
    $partition.Name = $ProbeName
    $partition.Mode = [Microsoft.AnalysisServices.Tabular.ModeType]::Import
    $source = [Microsoft.AnalysisServices.Tabular.MPartitionSource]::new()
    $source.Expression = Get-Content -LiteralPath $QueryFile -Raw -Encoding UTF8
    $partition.Source = $source
    $table.Partitions.Add($partition)
    $model.Tables.Add($table)
    try {
      $model.SaveChanges() | Out-Null
      $table.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
      $model.SaveChanges() | Out-Null
      $Operation = 'Dax'
      $dax = "EVALUATE '$ProbeName'"
    } finally {
      # Query results are read below before removing this table.
    }
  }
  if ($Operation -eq 'Dax') {
    [Reflection.Assembly]::LoadFrom((Join-Path $bin 'Microsoft.PowerBI.AdomdClient.dll')) | Out-Null
    $connection = [Microsoft.AnalysisServices.AdomdClient.AdomdConnection]::new("Data Source=localhost:$($ports[0]);Initial Catalog=$($database.ID)")
    try {
      $connection.Open()
      $command = $connection.CreateCommand()
      $command.CommandTimeout = 120
      $command.CommandText = if ($dax) { $dax } else { Get-Content -LiteralPath $QueryFile -Raw -Encoding UTF8 }
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
} finally {
  if ($table -and $model.Tables.Contains($ProbeName)) {
    $model.Tables.Remove($ProbeName)
    $model.SaveChanges() | Out-Null
  }
  $server.Disconnect()
}
