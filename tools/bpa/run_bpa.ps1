param(
  [string]$RulesFile = 'tools\bpa\rules.json',
  [string]$DefinitionPath = 'PBI_JobWant.SemanticModel\definition'
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$rulesFull = Join-Path $projectRoot $RulesFile
$defFull = Join-Path $projectRoot $DefinitionPath

if (-not (Test-Path $rulesFull)) {
  throw "BPA rules file not found: $rulesFull"
}
if (-not (Test-Path $defFull)) {
  throw "TMDL definition folder not found: $defFull"
}

# 1. Check if TabularEditor CLI exists
$te = Get-Command 'TabularEditor.exe' -ErrorAction SilentlyContinue
if ($te) {
  Write-Output "Running TabularEditor.exe CLI with rules: $RulesFile"
  $proc = Start-Process -FilePath $te.Source -ArgumentList "`"$defFull`"", "-A", "`"$rulesFull`"", "-G" -Wait -PassThru -WindowStyle Hidden
  if ($proc.ExitCode -ne 0) {
    throw "TabularEditor BPA exited with non-zero code: $($proc.ExitCode)"
  }
  [pscustomobject]@{Engine='TabularEditor'; Status='PASS'; ExitCode=$proc.ExitCode} | ConvertTo-Json
  exit 0
}

# 2. Fallback to native TOM assembly deserializer from Power BI Desktop
$app = Get-AppxPackage '*PowerBI*' | Select-Object -First 1
if (-not $app) {
  [pscustomobject]@{Engine='NONE'; Status='SKIPPED'; Reason='Neither TabularEditor nor Power BI Desktop found.'} | ConvertTo-Json
  exit 0
}
$bin = Join-Path $app.InstallLocation 'bin'
foreach ($dll in @('Microsoft.PowerBI.Tabular.dll', 'Microsoft.PowerBI.Tabular.Json.dll')) {
  $dllPath = Join-Path $bin $dll
  if (Test-Path $dllPath) {
    [Reflection.Assembly]::LoadFrom($dllPath) | Out-Null
  }
}

$database = [Microsoft.AnalysisServices.Tabular.TmdlSerializer]::DeserializeDatabaseFromFolder($defFull)
$model = $database.Model
$rules = Get-Content $rulesFull -Raw | ConvertFrom-Json

$violations = @()
foreach ($rel in $model.Relationships) {
  if ($rel.IsActive -and ($null -eq $rel.FromColumn -or $null -eq $rel.ToColumn)) {
    $violations += [pscustomobject]@{RuleID='BPA-INTEG-01'; Object=$rel.Name; Severity='Error'; Message='Relationship has missing column'}
  }
}

foreach ($table in $model.Tables) {
  foreach ($part in $table.Partitions) {
    if ($part.Mode.ToString() -ne 'Import') {
      $violations += [pscustomobject]@{RuleID='BPA-INTEG-02'; Object="$($table.Name):$($part.Name)"; Severity='Error'; Message="Partition mode is not Import"}
    }
  }
}

$errors = @($violations | Where-Object { $_.Severity -eq 'Error' })
$resultStatus = if ($errors.Count -eq 0) { 'PASS' } else { 'FAIL' }

[pscustomobject]@{
  Engine = 'NativeTOM'
  Status = $resultStatus
  TablesEvaluated = $model.Tables.Count
  RelationshipsEvaluated = $model.Relationships.Count
  ViolationsCount = $violations.Count
  Violations = $violations
} | ConvertTo-Json -Depth 4
