param(
  [ValidateSet('Parse', 'Inventory', 'ImportQueries', 'ImportModel', 'Refresh', 'RefreshTable', 'Dax')]
  [string]$Operation = 'Parse',
  [string]$QueryFile,
  [string]$TableName
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$app = Get-AppxPackage '*PowerBI*' | Select-Object -First 1
$bin = Join-Path $app.InstallLocation 'bin'
foreach ($dll in @('Microsoft.PowerBI.Tabular.dll', 'Microsoft.PowerBI.Tabular.Json.dll')) {
  [Reflection.Assembly]::LoadFrom((Join-Path $bin $dll)) | Out-Null
}
$definition = Join-Path $projectRoot 'PBI_JobWant.SemanticModel\definition'
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
  $legacyTableNames = @{
    FactJob = '目前職缺'
    FactJobSnapshot = '職缺快照'
    FactSalaryObservation = '薪資觀測'
    FactAcquisitionCategory = '職類擷取進度'
    DimCompany = 'dim_公司'
    DimArea = 'dim_地區'
    DimDate = 'dim_日期'
    DimJobCategory = 'dim_職類'
    DimSkill = 'dim_技能'
    BridgeJobCategory = '職缺職類對照'
    BridgeJobSkill = '職缺技能對照'
  }
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
  } elseif ($Operation -eq 'ImportModel') {
    $disk = [Microsoft.AnalysisServices.Tabular.TmdlSerializer]::DeserializeDatabaseFromFolder($definition)
    foreach ($legacyName in $legacyTableNames.Keys) {
      $localizedName = $legacyTableNames[$legacyName]
      if ($model.Tables.Contains($legacyName) -and $disk.Model.Tables.Contains($localizedName)) {
        throw 'The open Desktop model uses the previous table names. Close and reopen the project before importing localized names; no changes were saved.'
      }
    }
    foreach ($expression in $disk.Model.Expressions) {
      if ($model.Expressions.Contains($expression.Name)) { $model.Expressions[$expression.Name].Expression = $expression.Expression }
      else { $model.Expressions.Add($expression.Clone()) }
    }
    $addedTables = [System.Collections.Generic.List[string]]::new()
    $addedColumns = [System.Collections.Generic.List[string]]::new()
    foreach ($sourceTable in $disk.Model.Tables) {
      if (-not $model.Tables.Contains($sourceTable.Name)) {
        $model.Tables.Add($sourceTable.Clone()) | Out-Null
        $addedTables.Add($sourceTable.Name)
        continue
      }
      $targetTable = $model.Tables[$sourceTable.Name]
      foreach ($sourceColumn in $sourceTable.Columns) {
        if (-not $targetTable.Columns.Contains($sourceColumn.Name)) {
          $targetTable.Columns.Add($sourceColumn.Clone()) | Out-Null
          $addedColumns.Add("$($sourceTable.Name).$($sourceColumn.Name)")
        }
      }
    }
    $addedRelationships = [System.Collections.Generic.List[string]]::new()
    foreach ($sourceRelationship in $disk.Model.Relationships) {
      if (-not $model.Relationships.Contains($sourceRelationship.Name)) {
        $model.Relationships.Add($sourceRelationship.Clone()) | Out-Null
        $addedRelationships.Add($sourceRelationship.Name)
      }
    }
    $model.SaveChanges() | Out-Null
    [pscustomobject]@{Result='IMPORTED';AddedTables=$addedTables;AddedColumns=$addedColumns;AddedRelationships=$addedRelationships;Expressions=$model.Expressions.Count;Relationships=$model.Relationships.Count} | ConvertTo-Json -Depth 5 -Compress
  }
  if ($Operation -eq 'Refresh') {
    $model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
    $model.SaveChanges() | Out-Null
    Write-Output 'Full model refresh completed.'
  }
  if ($Operation -eq 'RefreshTable') {
    if ([string]::IsNullOrWhiteSpace($TableName)) {
      throw 'RefreshTable requires an existing model table name.'
    }
    if (-not $model.Tables.Contains($TableName) -and $legacyTableNames.ContainsKey($TableName) -and $model.Tables.Contains($legacyTableNames[$TableName])) {
      $TableName = $legacyTableNames[$TableName]
    }
    if (-not $model.Tables.Contains($TableName)) {
      throw 'RefreshTable requires an existing model table name or its previous English name.'
    }
    $model.Tables[$TableName].RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
    $model.SaveChanges() | Out-Null
    Write-Output "Full refresh completed for $TableName."
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
