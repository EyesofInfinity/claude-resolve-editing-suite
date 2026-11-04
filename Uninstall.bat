@echo off
rem Claude Resolve Editing Suite: double-click to remove everything the installer put in place. MIT License.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\uninstall.ps1"
echo.
pause
