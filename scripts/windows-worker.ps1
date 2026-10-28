function Get-XgoWorkerArguments {
 [CmdletBinding()]
 param(
  [Parameter(Mandatory=$true)][string]$ScriptPath,
  [Parameter(Mandatory=$true)]
  [ValidateSet('run','viewer','tensorboard','benchmark','setup')][string]$Action,
  [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_.-]+$')][string]$Distribution
 )
 if ($ScriptPath.IndexOf('"') -ge 0 -or $ScriptPath.Contains("`r") -or $ScriptPath.Contains("`n")) {
  throw 'Unsupported characters in launcher path.'
 }
 # Literal script file and arguments, with no encoded or evaluated command text.
 return ('-NoLogo -NoProfile -ExecutionPolicy RemoteSigned -File "{0}" -Task {1} -Distro "{2}" -Hold' -f $ScriptPath,$Action,$Distribution)
}
