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
$form.Size=New-Object Drawing.Size(1080,820)
$form.MinimumSize=New-Object Drawing.Size(1080,820)
$form.StartPosition='CenterScreen'
$form.BackColor=[Drawing.ColorTranslator]::FromHtml('#F3F5F9')
$form.Font=New-Object Drawing.Font('Segoe UI',10)
function LabelAt($text,$x,$y,$w,$h,$size=10,$bold=$false) {
 $label=New-Object Windows.Forms.Label
 $label.Text=$text;$label.SetBounds($x,$y,$w,$h)
 $style=[Drawing.FontStyle]::Regular
 if ($bold) {$style=[Drawing.FontStyle]::Bold}
 $label.Font=New-Object Drawing.Font('Segoe UI',$size,$style)
 $label.ForeColor=[Drawing.ColorTranslator]::FromHtml('#17243B')
 $form.Controls.Add($label)
 return $label
}
$null=LabelAt 'myDuck' 28 20 320 50 28 $true
$null=LabelAt 'TRAINING STUDIO  /  2.1.0' 30 74 600 25 10 $true
$null=LabelAt 'Setup, train, evaluate and inspect your duck from one place.' 30 104 960 28 12
$null=LabelAt 'Ubuntu distribution' 30 154 180 24 10 $true
$distro=New-Object Windows.Forms.TextBox
$distro.Text='Ubuntu';$distro.SetBounds(215,150,220,30);$form.Controls.Add($distro)
$null=LabelAt 'Use the installed name, such as Ubuntu or Ubuntu-24.04.' 450 154 570 24
function StartAction([string]$action) {
 try {
  if ($script:Workers.ContainsKey($action) -and -not $script:Workers[$action].HasExited) {
   $status.Text="$action window is already active. Check its live log below."
   return
  }
  $arguments=Get-XgoWorkerArguments -ScriptPath (Join-Path $script:Root 'XgoDuck.ps1') -Action $action -Distribution $distro.Text.Trim()
  $script:Workers[$action]=Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -WorkingDirectory $script:Root -ArgumentList $arguments -PassThru
  $status.Text="Opened $action window. Progress and errors appear below; task windows remain open when finished."
  if ($selector.Items.Contains($action)) {$selector.SelectedItem=$action}
 } catch {
  $status.Text='Could not launch: '+$_.Exception.Message
  [Windows.Forms.MessageBox]::Show($_.Exception.Message,'myDuck startup problem','OK','Error') | Out-Null
 }
}
function ButtonAt($text,$x,$y,$w,$action,$primary=$false) {
 $button=New-Object Windows.Forms.Button
 $button.Text=$text;$button.SetBounds($x,$y,$w,44)
 $button.FlatStyle='Flat';$button.FlatAppearance.BorderSize=0
 $button.BackColor=[Drawing.ColorTranslator]::FromHtml('#E1E7F0')
 $button.ForeColor=[Drawing.ColorTranslator]::FromHtml('#17243B')
 if ($primary) {$button.BackColor=[Drawing.ColorTranslator]::FromHtml('#2459D3');$button.ForeColor=[Drawing.Color]::White}
 $button.Tag=$action
 $button.Add_Click({param($sender,$event) StartAction ([string]$sender.Tag)})
 $form.Controls.Add($button)
 return $button
}
$null=ButtonAt 'Start / resume training' 30 198 250 'run' $true
$null=ButtonAt 'Stop training' 294 198 170 'stop'
$null=ButtonAt 'Setup / verify' 478 198 170 'setup'
$null=ButtonAt 'Export diagnostics' 662 198 190 'diagnostics'
$null=ButtonAt 'Reset project' 866 198 170 'reset'
$null=ButtonAt 'Open TensorBoard' 30 258 250 'tensorboard'
$null=LabelAt 'http://localhost:6007' 294 267 300 26 12 $true
$null=LabelAt 'Starts independently; charts fill in once training writes events.' 580 266 460 42
$null=ButtonAt 'Watch checkpoint' 30 314 250 'viewer'
$null=LabelAt 'http://localhost:8080' 294 323 300 26 12 $true
$null=LabelAt 'Waits for a saved model. No page is served while waiting.' 580 322 460 42
$status=LabelAt 'Ready. Start training handles installation and runs a GPU preflight before the long campaign.' 30 376 1006 46 11 $true
$null=LabelAt 'LIVE LOG' 30 433 100 28 10 $true
$selector=New-Object Windows.Forms.ComboBox
$selector.DropDownStyle='DropDownList';$selector.SetBounds(140,430,195,30)
foreach ($name in @('run','setup','tensorboard','viewer','diagnostics','stop','reset')) {[void]$selector.Items.Add($name)}
$selector.SelectedIndex=0;$form.Controls.Add($selector)
$logPath=LabelAt 'No log yet. Choose an action above.' 350 435 686 30 9
$console=New-Object Windows.Forms.RichTextBox
$console.SetBounds(30,473,1006,255)
$console.Anchor='Top,Bottom,Left,Right'
$console.ReadOnly=$true;$console.WordWrap=$false
$console.BackColor=[Drawing.ColorTranslator]::FromHtml('#111B2C')
$console.ForeColor=[Drawing.ColorTranslator]::FromHtml('#DDE6F6')
$console.Font=New-Object Drawing.Font('Consolas',10)
$console.BorderStyle='None'
$console.Text="Waiting for your first action.`n`nStart / resume: setup > GPU check > short preflight > training > evaluation.`nExport diagnostics: one text file containing Windows and WSL logs."
$form.Controls.Add($console)
$foot=LabelAt 'Closing this panel leaves worker windows running. Stop training before resetting. No archives are created.' 30 745 1006 27 9
$foot.Anchor='Bottom,Left,Right'
$timer=New-Object Windows.Forms.Timer
$timer.Interval=1000
$timer.Add_Tick({
 try {
  $task=[string]$selector.SelectedItem
  $logs=Join-Path $script:Root 'launcher-logs'
  if (-not (Test-Path -LiteralPath $logs)) {return}
  $file=Get-ChildItem -LiteralPath $logs -Filter "*-$task-*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($null -eq $file) {$logPath.Text="No $task log yet.";return}
  $text=(Get-Content -LiteralPath $file.FullName -Tail 250 -ErrorAction Stop) -join "`r`n"
  if ($script:LastLogText -ne $text -or $script:LastLog -ne $file.FullName) {
   $console.Text=$text;$console.SelectionStart=$console.TextLength;$console.ScrollToCaret()
   $logPath.Text=$file.Name
   $script:LastLogText=$text;$script:LastLog=$file.FullName
  }
 } catch {$logPath.Text='Log is temporarily unavailable; retrying.'}
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
