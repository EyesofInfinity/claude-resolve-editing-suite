# Claude Resolve Editing Suite uninstaller. MIT License.
#
# Removes exactly the files listed in %LOCALAPPDATA%\Claude Resolve Editing Suite\installed.txt (written by the installer),
# then any folder that is left empty. Files in Program Files (the audio plugins) need admin rights; only that step asks.
param(
    [string]$StateDir = "$env:LOCALAPPDATA\Claude Resolve Editing Suite",
    [switch]$Yes,
    [switch]$SkipResolveCheck   # for tests on a scratch install only
)
$ErrorActionPreference = "Stop"
$manifest = Join-Path $StateDir "installed.txt"
if (-not (Test-Path -LiteralPath $manifest)) { Write-Host "Nothing to remove: $manifest is not there."; exit 0 }
$files = @(Get-Content -LiteralPath $manifest | Where-Object { $_ })
Write-Host "Claude Resolve Editing Suite: $($files.Count) installed files are listed in $manifest"
if (-not $Yes) {
    $a = Read-Host "Remove them? [y/N]"
    if ($a -notmatch "^[Yy]") { Write-Host "Stopped. Nothing was removed."; exit 1 }
}
if (-not $SkipResolveCheck -and (Get-Process -Name "Resolve" -ErrorAction SilentlyContinue)) {
    Write-Host "DaVinci Resolve is running. Close it first, then run Uninstall.bat again."
    exit 1
}

# only names the installer wrote, and only under a folder named Develop
$mine = $files | Where-Object { $_ -match "\\Develop\\" }
$admin = New-Object System.Collections.Generic.List[string]
$removed = 0
foreach ($f in $mine) {
    if (-not (Test-Path -LiteralPath $f)) { continue }
    try { Remove-Item -LiteralPath $f -Force -ErrorAction Stop; $removed++ }
    catch { $admin.Add($f) }
}
if ($admin.Count -gt 0) {
    Write-Host "$($admin.Count) files need admin rights to remove (the audio plugins). Windows will ask."
    $list = Join-Path $StateDir "remove-admin.txt"
    $admin | Set-Content -Path $list -Encoding UTF8
    # the path goes into the elevated command as a quoted literal, its apostrophes doubled
    $qList = "'" + ($list -replace "'", "''") + "'"
    # the elevated step trusts nothing in the list: only paths under the VST3\Develop folder, and then the folders left empty
    $vstDev = Join-Path "$env:CommonProgramFiles\VST3" "Develop"
    $qRoot = "'" + ($vstDev -replace "'", "''") + "'"
    $cmd = "`$r = $qRoot; Get-Content -LiteralPath $qList | Where-Object { `$_.StartsWith(`$r + '\', [StringComparison]::OrdinalIgnoreCase) -and `$_ -notmatch '\\\.\.\\' } | " +
           "ForEach-Object { Remove-Item -LiteralPath `$_ -Force -ErrorAction SilentlyContinue }; " +
           "if (Test-Path -LiteralPath `$r) { Get-ChildItem -LiteralPath `$r -Recurse -Directory | Sort-Object { `$_.FullName.Length } -Descending | " +
           "Where-Object { -not (Get-ChildItem -LiteralPath `$_.FullName -Force) } | Remove-Item -Force; " +
           "if (-not (Get-ChildItem -LiteralPath `$r -Force)) { Remove-Item -LiteralPath `$r -Force } }"
    try {
        Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Verb RunAs -Wait `
            -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $cmd
        $removed += @($admin | Where-Object { -not (Test-Path -LiteralPath $_) }).Count
    } catch { Write-Host "Not removed: $_" }
    Remove-Item -LiteralPath $list -Force -ErrorAction SilentlyContinue
}

# folders the removal left empty, deepest first, never above a Develop folder
$dirs = $mine | ForEach-Object { Split-Path -Parent $_ } | Sort-Object -Unique
foreach ($d in ($dirs | Sort-Object { $_.Length } -Descending)) {
    $cur = $d
    while ($cur -and ($cur -match "\\Develop(\\|$)") -and (Test-Path -LiteralPath $cur) -and
           -not (Get-ChildItem -LiteralPath $cur -Force)) {
        try { Remove-Item -LiteralPath $cur -Force -ErrorAction Stop } catch { break }
        if ($cur -match "\\Develop$") { break }
        $cur = Split-Path -Parent $cur
    }
}

$left = @($mine | Where-Object { Test-Path -LiteralPath $_ })
if ($left.Count -eq 0) {
    Remove-Item -LiteralPath $manifest -Force
    Write-Host "Removed $removed files. Claude Resolve Editing Suite is uninstalled."
} else {
    $left | Set-Content -Path $manifest -Encoding UTF8
    Write-Host "Removed $removed files; $($left.Count) could not be removed and stay listed in $manifest."
}
