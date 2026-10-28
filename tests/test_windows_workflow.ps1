$ErrorActionPreference='Stop'
$root=Join-Path ([IO.Path]::GetTempPath()) ('myDuck-workflow-'+[guid]::NewGuid().ToString('N'))
$oldPath=$env:PATH
New-Item -ItemType Directory -Path (Join-Path $root 'scripts') -Force | Out-Null
try {
 Copy-Item -LiteralPath (Join-Path $PSScriptRoot '..\XgoDuck.ps1') -Destination $root
 Copy-Item -LiteralPath (Join-Path $PSScriptRoot '..\scripts\windows-worker.ps1') -Destination (Join-Path $root 'scripts')
 # A fixture executable exercises Windows native-stream behavior without requiring WSL/CUDA on CI.
 Add-Type -TypeDefinition @'
using System;
public class FakeWsl {
 public static int Main(string[] args) {
  string joined=String.Join(" ",args);
  if(joined.Contains("--list")){Console.WriteLine("Ubuntu");return 0;}
  if(joined.Contains("wslpath")){Console.WriteLine("/mnt/c/fixture");return 0;}
  if(joined.Contains("--version")){Console.WriteLine("Python 3.12.3");return 0;}
  if(joined.Contains("tensorboard")){
   Console.Error.WriteLine("ordinary native stderr progress");
   Console.WriteLine("TensorBoard URL: http://localhost:6007");
   return Environment.GetEnvironmentVariable("DUCK_TEST_FAIL")=="1" ? 7 : 0;
  }
  return 0;
 }
}
'@ -OutputAssembly (Join-Path $root 'wsl.exe') -OutputType ConsoleApplication
 $env:PATH=$root+';'+$oldPath
 foreach ($fail in @('0','1')) {
  $env:DUCK_TEST_FAIL=$fail
  $stdout=Join-Path $root "stdout-$fail.txt";$stderr=Join-Path $root "stderr-$fail.txt"
  $args='-NoProfile -ExecutionPolicy RemoteSigned -File "'+(Join-Path $root 'XgoDuck.ps1')+'" -Task tensorboard -Distro Ubuntu'
  $p=Start-Process (Join-Path $PSHOME 'powershell.exe') -ArgumentList $args -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  $expected=0;if($fail -eq '1'){$expected=1}
  if ($p.ExitCode -ne $expected) {throw "Expected exit $expected, got $($p.ExitCode): $(Get-Content $stdout -Raw) $(Get-Content $stderr -Raw)"}
  $text=(Get-Content $stdout -Raw)+(Get-Content $stderr -Raw)
  if ($text -notmatch 'ordinary native stderr progress' -or $text -match 'NativeCommandError|RemoteException') {throw "Native stderr was lost or misformatted: $text"}
 }
 if (-not (Get-ChildItem (Join-Path $root 'launcher-logs') -Filter '*.log')) {throw 'No persisted launcher logs'}
 Write-Host 'Full launcher success/failure workflow tests passed.'
} finally {
 $env:PATH=$oldPath
 Remove-Item Env:DUCK_TEST_FAIL -ErrorAction SilentlyContinue
 Remove-Item -LiteralPath $root -Recurse -Force
}
