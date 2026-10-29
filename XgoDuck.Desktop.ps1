[CmdletBinding()]
param([switch]$SelfTest)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
. (Join-Path $PSScriptRoot 'scripts\windows-worker.ps1')
$script:Root=$PSScriptRoot
$script:Workers=@{}
$script:LastLog=''
$script:LastLogText=''
$form=New-Object Windows.Forms.Form
$form.Text='myDuck | Training studio'
$form.AutoScaleMode=[Windows.Forms.AutoScaleMode]::None
$form.Size=New-Object Drawing.Size(1080,820)
$form.MinimumSize=New-Object Drawing.Size(1080,820)
$form.StartPosition='CenterScreen'
$form.BackColor=[Drawing.ColorTranslator]::FromHtml('#10151F')
$form.Font=New-Object Drawing.Font('Segoe UI',10)
$form.ClientSize=New-Object Drawing.Size(1066,790)
$form.MinimumSize=$form.Size
function LabelAt($text,$x,$y,$w,$h,$size=10,$bold=$false) {
 $label=New-Object Windows.Forms.Label
 $label.Text=$text;$label.SetBounds($x,$y,$w,$h)
 $style=[Drawing.FontStyle]::Regular
 if ($bold) {$style=[Drawing.FontStyle]::Bold}
 $label.Font=New-Object Drawing.Font('Segoe UI',$size,$style)
 $label.ForeColor=[Drawing.ColorTranslator]::FromHtml('#E5EAF3')
 $form.Controls.Add($label)
 return $label
}
$null=LabelAt 'myDuck' 28 20 320 50 28 $true
$null=LabelAt 'TRAINING STUDIO  /  2.3.0' 30 74 600 25 10 $true
$null=LabelAt 'Setup, train, evaluate and inspect your duck from one place.' 30 104 960 28 12
$null=LabelAt 'Ubuntu distribution' 30 154 180 24 10 $true
$distro=New-Object Windows.Forms.TextBox
$distro.BackColor=[Drawing.ColorTranslator]::FromHtml('#1B2433')
$distro.ForeColor=[Drawing.ColorTranslator]::FromHtml('#E5EAF3')
$distro.BorderStyle='FixedSingle'
$distro.Text='Ubuntu';$distro.SetBounds(215,150,220,30);$form.Controls.Add($distro)
$null=LabelAt 'Use the installed name, such as Ubuntu or Ubuntu-24.04.' 450 154 570 24
function StartAction([string]$action) {
 try {
  if ($action -eq 'logs') {
   $folder=Join-Path $script:Root 'launcher-logs'
   New-Item -ItemType Directory -Force -Path $folder | Out-Null
   Start-Process explorer.exe -ArgumentList ('"'+$folder+'"') | Out-Null
   return
  }
  if ($script:Workers.ContainsKey('reset') -and -not $script:Workers['reset'].HasExited) {
   $status.Text='Reset is in progress. Please wait for completion.';return
  }
  if ($script:Workers.ContainsKey($action) -and -not $script:Workers[$action].HasExited) {
   $status.Text="$action is already running in the background.";return
  }
  if ($action -eq 'reset') {
   $answer=[Windows.Forms.MessageBox]::Show('Stop project processes and permanently delete all training models, history and installed dependencies in ~/xgoduck_oneclick? Your Windows launcher folder stays. There is no archive.','Start fresh','YesNo','Warning')
   if ($answer -ne [Windows.Forms.DialogResult]::Yes) {return}
  }
  $arguments=Get-XgoWorkerArguments -ScriptPath (Join-Path $script:Root 'XgoDuck.ps1') -Action $action -Distribution $distro.Text.Trim() -Background
  if ($action -eq 'reset') {$arguments+=' -ConfirmedReset'}
  $folder=Join-Path $script:Root 'launcher-logs'
  New-Item -ItemType Directory -Force -Path $folder | Out-Null
  $prefix=Join-Path $folder ((Get-Date -Format 'yyyyMMdd-HHmmss-fff')+'-'+$action)
  $script:Workers[$action]=Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -WorkingDirectory $script:Root -ArgumentList $arguments -WindowStyle Hidden -RedirectStandardOutput ($prefix+'.stdout.log') -RedirectStandardError ($prefix+'.stderr.log') -PassThru
  $script:Reported.Remove($action)
  $script:TaskStates[$action]='Running'
  $status.Text="$action started in the background. You can keep using this window."
 } catch {
  $status.Text='Could not launch: '+$_.Exception.Message
  $folder=Join-Path $script:Root 'launcher-logs'
  New-Item -ItemType Directory -Force -Path $folder | Out-Null
  ($_ | Out-String) | Add-Content -LiteralPath (Join-Path $folder 'desktop-errors.log')
 }
}
function ButtonAt($text,$x,$y,$w,$action,$primary=$false) {
 $button=New-Object Windows.Forms.Button
 $button.Text=$text;$button.SetBounds($x,$y,$w,44)
 $button.FlatStyle='Flat';$button.FlatAppearance.BorderSize=0
 $button.BackColor=[Drawing.ColorTranslator]::FromHtml('#243044')
 $button.ForeColor=[Drawing.ColorTranslator]::FromHtml('#E5EAF3')
 if ($primary) {$button.BackColor=[Drawing.ColorTranslator]::FromHtml('#2459D3');$button.ForeColor=[Drawing.Color]::White}
 $button.UseVisualStyleBackColor=$false
 $button.FlatAppearance.MouseOverBackColor=[Drawing.ColorTranslator]::FromHtml('#354761')
 $button.FlatAppearance.MouseDownBackColor=[Drawing.ColorTranslator]::FromHtml('#405675')
 if ($primary) {
  $button.FlatAppearance.MouseOverBackColor=[Drawing.ColorTranslator]::FromHtml('#326AE8')
  $button.FlatAppearance.MouseDownBackColor=[Drawing.ColorTranslator]::FromHtml('#1D47AA')
 }
 $button.Tag=$action
 $button.Add_Click({param($sender,$event) StartAction ([string]$sender.Tag)})
 $form.Controls.Add($button)
 return $button
}
$null=ButtonAt 'Start / resume training' 30 198 250 'run' $true
$null=ButtonAt 'Stop training' 294 198 170 'stop'
$null=ButtonAt 'Setup / verify' 478 198 170 'setup'
$null=ButtonAt 'Export training data' 662 198 190 'training-export'
$null=ButtonAt 'Reset project' 866 198 170 'reset'
$null=ButtonAt 'Open TensorBoard' 30 258 250 'tensorboard'
$null=LabelAt 'http://localhost:6007' 294 267 300 26 12 $true
$null=LabelAt 'Starts independently; charts fill in once training writes events.' 580 266 460 42
$null=ButtonAt 'Watch checkpoint' 30 314 250 'viewer'
$null=LabelAt 'http://localhost:8080' 294 323 300 26 12 $true
$null=LabelAt 'Waits for a saved model. No page is served while waiting.' 580 322 460 42
$status=LabelAt 'Ready. Start training handles installation and runs a GPU preflight before the long campaign.' 30 376 1006 46 11 $true
$null=LabelAt 'WORKSPACE' 30 440 200 28 10 $true
$null=LabelAt 'Training and tools run quietly in the background.' 30 478 960 30 15 $true
$null=LabelAt 'Open TensorBoard for charts. Open the viewer to inspect a saved checkpoint.' 30 522 960 30 11
$tasks=LabelAt 'No tasks started in this session.' 30 566 1006 70 11
$null=ButtonAt 'Open saved logs' 30 660 250 'logs'
$null=ButtonAt 'Export diagnostics' 294 660 220 'diagnostics'
$null=LabelAt 'Detailed logs are saved automatically. Export diagnostics when an action fails.' 540 666 496 48 10
$foot=LabelAt 'Closing this panel leaves background tasks running. Reset stops project processes before deleting training data.' 30 745 1006 27 9
$foot.Anchor='Bottom,Left,Right'
$script:Reported=@{}
$script:TaskStates=@{}
$timer=New-Object Windows.Forms.Timer
$timer.Interval=1000
$timer.Add_Tick({
 try {
  foreach ($action in @($script:Workers.Keys)) {
   $worker=$script:Workers[$action]
   if ($worker.HasExited -and -not $script:Reported.ContainsKey($action)) {
    $script:Reported[$action]=$true
    $resultFile=Join-Path $script:Root ('launcher-logs/result-'+$worker.Id+'.json')
    if (Test-Path -LiteralPath $resultFile) {
     $result=Get-Content -Raw -LiteralPath $resultFile | ConvertFrom-Json
     $script:TaskStates[$action]=$result.status
     $status.Text=$action+': '+$result.message
    } else {
     $script:TaskStates[$action]='Ended (exit '+$worker.ExitCode+')'
     $status.Text=$action+' ended. Open saved logs for stdout and stderr, or export diagnostics.'
    }
   }
  }
  if ($script:TaskStates.Count) {$tasks.Text=(@($script:TaskStates.Keys | Sort-Object | ForEach-Object {$_+': '+$script:TaskStates[$_]}) -join '    |    ')}
 } catch {
  ($_ | Out-String) | Add-Content -LiteralPath (Join-Path $script:Root 'launcher-logs/desktop-errors.log')
 }
})
$form.Add_FormClosed({$timer.Stop();$timer.Dispose()})
if ($SelfTest) {
 if ($form.Controls.Count -lt 20) {throw 'Dashboard controls missing'}
 foreach ($control in $form.Controls) {
  if ($control.Right -gt $form.ClientSize.Width -or $control.Bottom -gt $form.ClientSize.Height) {throw ('Control clipped: '+$control.Text)}
 }
 $form.Dispose()
 Write-Host 'Desktop construction and layout checks passed.'
} else {
 $timer.Start()
 [void]$form.ShowDialog()
 $form.Dispose()
}
