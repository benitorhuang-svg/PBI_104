$ErrorActionPreference = 'Stop'
$instances = @(Get-Process msmdsrv -ErrorAction SilentlyContinue)
if ($instances.Count -ne 1) { throw 'Expected exactly one msmdsrv process' }
$ports = @(Get-NetTCPConnection -OwningProcess $instances[0].Id -State Listen | Select-Object -ExpandProperty LocalPort -Unique)

$app = Get-AppxPackage '*PowerBI*' | Select-Object -First 1
$bin = Join-Path $app.InstallLocation 'bin'

foreach ($dll in @('Microsoft.PowerBI.Tabular.dll', 'Microsoft.PowerBI.Tabular.Json.dll', 'Microsoft.PowerBI.AdomdClient.dll')) {
    [Reflection.Assembly]::LoadFrom((Join-Path $bin $dll)) | Out-Null
}

$server = [Microsoft.AnalysisServices.Tabular.Server]::new()
$server.Connect("localhost:$($ports[0])")
$db = $server.Databases[0]

$conn = [Microsoft.AnalysisServices.AdomdClient.AdomdConnection]::new("Data Source=localhost:$($ports[0]);Initial Catalog=$($db.ID)")
$conn.Open()
try {
    # 1. Table row counts
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = "SELECT TABLE_ID, ROWS_COUNT, RIVIOLATION_COUNT FROM `$SYSTEM.DISCOVER_STORAGE_TABLES"
    $adapter = [Microsoft.AnalysisServices.AdomdClient.AdomdDataAdapter]::new($cmd)
    $dsTables = [System.Data.DataSet]::new()
    $adapter.Fill($dsTables) | Out-Null
    
    $tablesMap = @{}
    foreach ($row in $dsTables.Tables[0].Rows) {
        if ($row.TABLE_ID -like 'R$*' -or $row.TABLE_ID -like 'H$*') { continue }
        $tablesMap[$row.TABLE_ID] = [pscustomobject]@{
            Table = $row.TABLE_ID
            Rows = [int64]$row.ROWS_COUNT
            DictBytes = 0L
        }
    }

    # 2. Columns Dictionary Size
    $cmdCol = $conn.CreateCommand()
    $cmdCol.CommandText = "SELECT TABLE_ID, COLUMN_ID, DATATYPE, COLUMN_ENCODING, DICTIONARY_SIZE FROM `$SYSTEM.DISCOVER_STORAGE_TABLE_COLUMNS"
    $dsCols = [System.Data.DataSet]::new()
    $adapterCol = [Microsoft.AnalysisServices.AdomdClient.AdomdDataAdapter]::new($cmdCol)
    $adapterCol.Fill($dsCols) | Out-Null
    
    $colList = [System.Collections.Generic.List[object]]::new()
    foreach ($row in $dsCols.Tables[0].Rows) {
        $tbl = $row.TABLE_ID
        $dictBytes = if ($row.DICTIONARY_SIZE -is [DBNull]) { 0L } else { [int64]$row.DICTIONARY_SIZE }
        if ($tablesMap.ContainsKey($tbl)) {
            $tablesMap[$tbl].DictBytes += $dictBytes
        }
        if ($tbl -notlike 'R$*' -and $tbl -notlike 'H$*' -and $dictBytes -gt 0) {
            $colList.Add([pscustomobject]@{
                Table = $tbl
                Column = $row.COLUMN_ID
                DataType = $row.DATATYPE
                Encoding = $row.COLUMN_ENCODING
                DictKB = [math]::Round($dictBytes / 1KB, 1)
                DictMB = [math]::Round($dictBytes / 1MB, 2)
            })
        }
    }

    Write-Output "=== VERTIPAQ STORAGE TABLES (ROWS & DICTIONARY SIZE) ==="
    $tablesMap.Values | Sort-Object Rows -Descending | ForEach-Object {
        [pscustomobject]@{
            Table = $_.Table
            Rows = $_.Rows
            DictMB = [math]::Round($_.DictBytes / 1MB, 2)
        }
    } | Format-Table -AutoSize | Out-String | Write-Output

    Write-Output "=== TOP 25 VERTIPAQ COLUMNS BY DICTIONARY SIZE ==="
    $colList | Sort-Object DictKB -Descending | Select-Object -First 25 | Format-Table -AutoSize | Out-String | Write-Output

} finally {
    $conn.Close()
    $server.Disconnect()
}
