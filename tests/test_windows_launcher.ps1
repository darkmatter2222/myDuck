$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '..\scripts\windows-worker.ps1')
$folder=Join-Path ([IO.Path]::GetTempPath()) ("duck space O'Brien & test-"+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $folder | Out-Null
try {
 $file=Join-Path $folder 'worker.ps1'
 @'
param([string]$Task,[string]$Distro,[switch]$Hold,[switch]$Background)
@{Task=$Task;Distro=$Distro;Hold=[bool]$Hold;Background=[bool]$Background;Root=$PSScriptRoot} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'result.json')
'@ | Set-Content -LiteralPath $file
 foreach ($action in @('run','tensorboard','viewer','benchmark','setup')) {
  $arguments=Get-XgoWorkerArguments -ScriptPath $file -Action $action -Distribution 'Ubuntu-24.04'
  if ($arguments -match 'EncodedCommand|Bypass') {throw 'Unexpected invocation flags'}
  $child=Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -ArgumentList $arguments -Wait -PassThru
  if ($child.ExitCode -ne 0) {throw "Child failed: $($child.ExitCode)"}
  $result=Get-Content -LiteralPath (Join-Path $folder 'result.json') -Raw | ConvertFrom-Json
  if ($result.Task -ne $action -or $result.Distro -ne 'Ubuntu-24.04' -or -not $result.Hold -or $result.Root -ne $folder) {throw 'Arguments did not round trip'}
 }
 $arguments=Get-XgoWorkerArguments -ScriptPath $file -Action 'reset' -Distribution 'Ubuntu' -Background
 $child=Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
 $result=Get-Content -LiteralPath (Join-Path $folder 'result.json') -Raw | ConvertFrom-Json
 if ($child.ExitCode -ne 0 -or $result.Hold -or -not $result.Background) {throw 'Background task unexpectedly holds a console'}
 $rejected=$false
 try {Get-XgoWorkerArguments -ScriptPath $file -Action 'run' -Distribution 'Ubuntu" -Command evil' | Out-Null} catch {$rejected=$true}
 if (-not $rejected) {throw 'Invalid distro accepted'}
 Write-Host 'Windows worker round-trip tests passed.'
} finally {Remove-Item -LiteralPath $folder -Recurse -Force}
