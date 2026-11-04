@echo off
rem Claude Resolve Editing Suite: double-click to install. It runs installer\install.ps1 from this folder. MIT License.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\install.ps1" -Source "%~dp0."
echo.
pause
