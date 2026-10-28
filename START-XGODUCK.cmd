@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy RemoteSigned -File "%~dp0XgoDuck.ps1"
if errorlevel 1 (
  echo.
  echo The XGO-Duck master launcher reported an error. Review the message above.
  pause
)
endlocal
