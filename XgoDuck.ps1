[CmdletBinding()]
param(
 [ValidateSet('menu','run','status','viewer','tensorboard','log','stop','benchmark','reset','setup','selftest','diagnostics')]
 [string]$Task='menu',
 [string]$Distro='',
 [switch]$Hold
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$script:Root=$PSScriptRoot
$script:Code=0
$script:Transcript=$false

function Native([string[]]$Arguments) {
 # Send process output to the host, NEVER into a function's numeric return value.
 $previous=$ErrorActionPreference
 try {
  # Windows PowerShell 5.1 wraps native stderr as ErrorRecords; exit code is authoritative.
  $ErrorActionPreference='Continue'
  & wsl.exe @Arguments 2>&1 | ForEach-Object { Write-Host ($_.ToString().TrimEnd("`r")) }
  $script:Code=$LASTEXITCODE
 } finally {$ErrorActionPreference=$previous}
}
function NeedSuccess([string]$Label) {
 if ($script:Code -ne 0) {throw "$Label failed (exit $script:Code). See this window and launcher-logs."}
}
function InitializeWsl {
 if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {throw 'WSL is not installed. In an administrator terminal run: wsl --install -d Ubuntu. Reboot, finish Ubuntu user setup, then launch again.'}
 $names=@(& wsl.exe --list --quiet 2>&1 | ForEach-Object {("$_" -replace "`0",'').Trim()} | Where-Object {$_})
 if ($LASTEXITCODE -ne 0) {throw ('Cannot list WSL distributions: '+($names -join ' '))}
 if (-not $script:Distro) {
   $ubuntu=@($names | Where-Object {$_ -match '^Ubuntu'})
   if ($ubuntu.Count -eq 1) {$script:Distro=$ubuntu[0]}
   elseif ($names -contains 'Ubuntu') {$script:Distro='Ubuntu'}
   else {throw ('Specify Ubuntu with -Distro. Installed: '+($names -join ', '))}
 }
 if ($names -notcontains $script:Distro) {throw "Distribution '$script:Distro' not installed. Installed: $($names -join ', ')"}
 Write-Host "Starting/checking WSL distribution: $script:Distro"
 Native @('-d',$script:Distro,'--exec','/bin/true'); NeedSuccess 'WSL startup'
 # Ask WSL itself to map the path; supports spaces and custom mount locations.
 $mapped=@(& wsl.exe -d $script:Distro --exec wslpath -a -u $script:Root 2>&1)
 if ($LASTEXITCODE -ne 0) {throw "Cannot map extracted folder into WSL: $mapped"}
 $script:LinuxRoot=($mapped -join '').Trim()
 Native @('-d',$script:Distro,'--exec','python3','--version'); NeedSuccess 'Ubuntu Python'
}
function Engine([string]$Command,[string[]]$Extra=@()) {
 Native (@('-d',$script:Distro,'--exec','python3',($script:LinuxRoot+'/scripts/xgoduck_engine.py'),$Command)+$Extra)
}
function Setup {
 Native @('-d',$script:Distro,'--exec','bash',($script:LinuxRoot+'/scripts/bootstrap.sh'))
 NeedSuccess 'Dependency setup'
}
function Spawn([string]$Action) {
 $file=Join-Path $script:Root 'XgoDuck.ps1'
 $arguments=Get-XgoWorkerArguments -ScriptPath $file -Action $Action -Distribution $script:Distro
 Write-Host ('Launching: powershell.exe '+$arguments)
 $worker=Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -WorkingDirectory $script:Root -ArgumentList $arguments -PassThru
 if ($worker.WaitForExit(1500)) {
  throw "Worker exited immediately (exit $($worker.ExitCode)). Check launcher-logs and Norton Security History. No exclusions are added automatically."
 }
}
function DeleteProject {
 Write-Host 'Delete ALL installed source, models, logs and state in ~/xgoduck_oneclick. NO archive.' -ForegroundColor Red
 Write-Host 'Close viewer/TensorBoard and stop training first. Separate legacy ~/xgoduck_rl and this launcher folder are outside this reset.'
 if ((Read-Host 'Type DELETE to confirm').Trim() -ieq 'DELETE') {Engine 'reset' @('--confirm','DELETE'); NeedSuccess 'Reset'}
}
function ExportDiagnostics {
 $directory=Join-Path $script:Root 'diagnostics'
 New-Item -ItemType Directory -Force -Path $directory | Out-Null
 $report=Join-Path $directory ('myDuck-diagnostics-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.txt')
 @('myDuck diagnostics - review before sharing (includes usernames and local paths)',('Created: '+(Get-Date)),('Windows: '+[Environment]::OSVersion.VersionString),('PowerShell: '+$PSVersionTable.PSVersion.ToString())) | Set-Content -LiteralPath $report -Encoding UTF8
 Get-ChildItem -LiteralPath (Join-Path $script:Root 'launcher-logs') -Filter '*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 12 | ForEach-Object {
  Add-Content -LiteralPath $report -Encoding UTF8 -Value ("`n=== "+$_.Name+' (last 300 lines) ===')
  Get-Content -LiteralPath $_.FullName -Tail 300 -ErrorAction SilentlyContinue | Add-Content -LiteralPath $report -Encoding UTF8
 }
 try {
  InitializeWsl
  $name=[IO.Path]::GetFileName($report)
  Engine 'diagnostics' @('--output',($script:LinuxRoot+'/diagnostics/'+$name))
  if ($script:Code -ne 0) {Add-Content -LiteralPath $report -Encoding UTF8 -Value 'WSL diagnostics failed; Windows logs retained.'}
 } catch {Add-Content -LiteralPath $report -Encoding UTF8 -Value ('WSL unavailable: '+$_)}
 $script:Code=0
 Write-Host "DIAGNOSTICS READY: $report" -ForegroundColor Green
 Write-Host 'Send this single text file. No checkpoint weights are included.'
 Start-Process explorer.exe -ArgumentList ('/select,"'+$report+'"') | Out-Null
}
function Execute([string]$Action) {
 switch ($Action) {
  'setup' {Setup}
  'run' {
   Engine 'active'
   if ($script:Code -eq 0) {Write-Host 'Training already running.'; return}
   if ($script:Code -ne 2) {NeedSuccess 'Controller check'}
   Setup
   Add-Type -Namespace Xgo -Name Power -MemberDefinition '[System.Runtime.InteropServices.DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags);'
   [void][Xgo.Power]::SetThreadExecutionState([uint32]2147483649)
   try {
    Spawn 'tensorboard'
    Spawn 'viewer'
    Engine 'run' @('--environments','4096','--block-iterations','2000','--save-every','250','--forever')
    NeedSuccess 'Training'
   } finally {[void][Xgo.Power]::SetThreadExecutionState([uint32]2147483648)}
  }
  'tensorboard' {Engine 'tensorboard'; NeedSuccess 'TensorBoard'}
  'viewer' {Engine 'viewer' @('--device','cpu','--latest','--wait','7200'); NeedSuccess 'Viewer'}
  'benchmark' {Engine 'benchmark'; NeedSuccess 'Evaluation'}
  'selftest' {Engine 'unit'; NeedSuccess 'Self-test'}
  'reset' {DeleteProject}
  'diagnostics' {ExportDiagnostics}
  default {Engine $Action; NeedSuccess $Action}
 }
}
try {
 . (Join-Path $script:Root 'scripts\windows-worker.ps1')
 $logDir=Join-Path $script:Root 'launcher-logs'
 New-Item -ItemType Directory -Force -Path $logDir | Out-Null
 $log=Join-Path $logDir ((Get-Date -Format 'yyyyMMdd-HHmmss')+"-$Task-$PID.log")
 Start-Transcript -Path $log | Out-Null
 $script:Transcript=$true
 Write-Host "Launcher log: $log"
 if ($Task -ne 'diagnostics') {InitializeWsl}
 if ($Task -ne 'menu') {Execute $Task}
 else {
  $done=$false
  while (-not $done) {
   Write-Host "`nXGO DUCK | Fresh-start training control center" -ForegroundColor Cyan
   Write-Host '1 Start/resume (also starts TensorBoard and waiting viewer)'
   Write-Host '2 Status   3 Viewer   4 TensorBoard   5 Logs   6 Evaluate'
   Write-Host 'TensorBoard: http://localhost:6007 | Viewer: http://localhost:8080'
   Write-Host '8 Export diagnostics to one shareable text file'
   Write-Host '7 Stop training   9 Delete project   10 Setup/repair   0 Exit menu'
   try {
    switch ((Read-Host 'Select').Trim()) {
     '1' {Spawn 'run'}
     '2' {Execute 'status'}
     '3' {Spawn 'viewer'}
     '4' {Spawn 'tensorboard'}
     '5' {Execute 'log'}
     '6' {Spawn 'benchmark'}
     '7' {Execute 'stop'}
     '8' {ExportDiagnostics}
     '9' {DeleteProject}
     '10' {Spawn 'setup'}
     '0' {$done=$true}
     default {Write-Host 'Select a listed number.'}
    }
   } catch {Write-Host "ERROR: $_" -ForegroundColor Red; $script:Code=0}
  }
 }
} catch {
 $script:Code=1
 Write-Host "ERROR: $_" -ForegroundColor Red
 Write-Host $_.ScriptStackTrace
} finally {
 if ($script:Transcript) {Stop-Transcript | Out-Null}
 if ($Hold) {[void](Read-Host 'Task ended. Press Enter to close this window')}
}
exit $script:Code
