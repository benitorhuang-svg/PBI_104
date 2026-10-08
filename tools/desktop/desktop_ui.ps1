param(
  [ValidateSet('List', 'Screenshot', 'Invoke', 'Select', 'Key', 'Click', 'Activate')]
  [string]$Operation = 'List',
  [string]$Name,
  [string]$Scope,
  [string]$OutputFile = "$env:TEMP\PBI_104\desktop.png",
  [int]$ProcessId = 0,
  [int]$X,
  [int]$Y
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class PbiUiNative {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int n);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr e);
}
'@
$processes = @(Get-Process PBIDesktop -ErrorAction SilentlyContinue)
if ($ProcessId) { $processes = @($processes | Where-Object { $_.Id -eq $ProcessId }) }
if ($processes.Count -ne 1) { throw 'Select exactly one Power BI Desktop process with -ProcessId when multiple are open.' }
$process = $processes[0]
$window = [System.Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
$nodes = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
if ($Scope) {
  $scopeWindow = $nodes | Where-Object { $_.Current.Name -eq $Scope -and $_.Current.ControlType.ProgrammaticName -eq 'ControlType.Window' } | Select-Object -First 1
  if (-not $scopeWindow) { throw "No dialog named $Scope" }
  $nodes = $scopeWindow.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
}
if ($Operation -eq 'List') {
  $nodes | Where-Object { $_.Current.Name -match $Name -and -not $_.Current.IsOffscreen } | ForEach-Object {
    [pscustomobject]@{Name=$_.Current.Name;Type=$_.Current.ControlType.ProgrammaticName;Id=$_.Current.AutomationId;Handle=$_.Current.NativeWindowHandle}
  } | Select-Object -First 80 | ConvertTo-Json -Compress
} elseif ($Operation -in @('Invoke', 'Select')) {
  $patternName = if ($Operation -eq 'Invoke') { 'InvokePatternIdentifiers.Pattern' } else { 'SelectionItemPatternIdentifiers.Pattern' }
  $target = $nodes | Where-Object { $_.Current.Name -eq $Name -and -not $_.Current.IsOffscreen -and (@($_.GetSupportedPatterns() | ForEach-Object { $_.ProgrammaticName }) -contains $patternName) } | Select-Object -First 1
  if (-not $target) { throw "No visible control named $Name" }
  if ($Operation -eq 'Invoke') { $target.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke() }
  else { $target.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select() }
} elseif ($Operation -eq 'Activate') {
  $target = $nodes | Where-Object { $_.Current.Name -eq $Name -and $_.Current.NativeWindowHandle -ne 0 } | Select-Object -First 1
  $handle = if ($target) { $target.Current.NativeWindowHandle } else { $process.MainWindowHandle }
  [PbiUiNative]::ShowWindow([IntPtr]$handle, 5) | Out-Null
  [PbiUiNative]::SetForegroundWindow([IntPtr]$handle) | Out-Null
} elseif ($Operation -eq 'Key') {
  [PbiUiNative]::SetForegroundWindow($process.MainWindowHandle) | Out-Null
  [System.Windows.Forms.SendKeys]::SendWait($Name)
} elseif ($Operation -eq 'Click') {
  [PbiUiNative]::SetCursorPos($X,$Y) | Out-Null
  [PbiUiNative]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
  [PbiUiNative]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
} elseif ($Operation -eq 'Screenshot') {
  $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
  $bitmap = [System.Drawing.Bitmap]::new($bounds.Width,$bounds.Height)
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  try {
    $graphics.CopyFromScreen($bounds.Location,[System.Drawing.Point]::Empty,$bounds.Size)
    $path = if ([IO.Path]::IsPathRooted($OutputFile)) {
      [IO.Path]::GetFullPath($OutputFile)
    } else {
      [IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputFile))
    }
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path)) | Out-Null
    $bitmap.Save($path)
    Write-Output $path
  } finally { $graphics.Dispose(); $bitmap.Dispose() }
}
