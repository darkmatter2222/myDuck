@echo off
setlocal
cd /d "%~dp0"
if not exist "launcher-logs" mkdir "launcher-logs"
start "" /b powershell.exe -NoLogo -NoProfile -WindowStyle Hidden -ExecutionPolicy RemoteSigned -STA -File "%~dp0XgoDuck.Desktop.ps1" %* 1>>"launcher-logs\desktop-startup.log" 2>&1
endlocal
