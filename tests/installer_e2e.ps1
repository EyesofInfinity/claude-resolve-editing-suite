# End-to-end installer test: a fake copy of the suite in a folder with spaces, an apostrophe and brackets, run the way
# Install.bat runs it (-Source "<folder>\."), into scratch roots; install twice, compare every file by name and hash,
# uninstall, and check the user's own files stay.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$base = Join-Path $env:TEMP "crs e2e"
Remove-Item -Recurse -Force -LiteralPath $base -ErrorAction SilentlyContinue
$pkg = Join-Path $base "O'Brien [1] Suite"
foreach ($d in "nodes", "effects\art\build", "effects\depth", "effects\fusegen\out", "plugins\prebuilt\Plug.vst3\Contents\x86_64-win", "installer") { [IO.Directory]::CreateDirectory((Join-Path $pkg $d)) | Out-Null }
# source path, then where it must land
$samples = [ordered]@{
    "Develop 1 Light.dctl"                                 = "LUT\Develop\Develop 1 Light.dctl"
    "Develop 2 Color.dctl"                                 = "LUT\Develop\Develop 2 Color.dctl"
    "nodes\Develop Bloom.dctl"                             = "LUT\Develop\Nodes\Develop Bloom.dctl"
    "effects\art\build\Develop Art.dctl"                   = "LUT\Develop\Art\Develop Art.dctl"
    "effects\fusegen\out\Develop Art.fuse"                 = "FUSE\Develop\Develop Art.fuse"
    "plugins\prebuilt\Plug.vst3\Contents\x86_64-win\Plug.vst3" = "VST\Develop\Plug.vst3\Contents\x86_64-win\Plug.vst3"
}
foreach ($s in $samples.Keys) { Set-Content -LiteralPath (Join-Path $pkg $s) "payload $s" }
Set-Content -LiteralPath (Join-Path $pkg "effects\depth\depthfx.py") "not installed"
foreach ($n in "install.ps1", "uninstall.ps1") { [IO.File]::Copy("$repo\installer\$n", (Join-Path $pkg "installer\$n"), $true) }
$lut = Join-Path $base "lut"; $fuse = Join-Path $base "fuse"; $vst = Join-Path $base "vst"; $state = Join-Path $base "state"
$ps = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$ins = Join-Path $pkg "installer\install.ps1"
function Run-Install { & $ps -NoProfile -ExecutionPolicy Bypass -File $ins -Source "$pkg\." -LutRoot $lut -FuseRoot $fuse -Vst3Root $vst -StateDir $state -Yes; if ($LASTEXITCODE) { throw "install exit $LASTEXITCODE" } }
Run-Install | Out-Null
Run-Install | Out-Null
$bad = 0
foreach ($s in $samples.Keys) {
    $dst = $samples[$s].Replace("LUT\", "$lut\").Replace("FUSE\", "$fuse\").Replace("VST\", "$vst\")
    if (-not (Test-Path -LiteralPath $dst)) { Write-Output "MISSING $dst"; $bad++ }
    elseif ((Get-FileHash -LiteralPath $dst).Hash -ne (Get-FileHash -LiteralPath (Join-Path $pkg $s)).Hash) { Write-Output "DIFF $dst"; $bad++ }
}
$list = @(Get-Content -LiteralPath "$state\installed.txt")
Write-Output "installed; manifest lines $($list.Count) (want $($samples.Count)); problems $bad"
Set-Content -LiteralPath (Join-Path $lut "keep me.dctl") "user file"
[IO.Directory]::CreateDirectory("$lut\Develop\Mine") | Out-Null
Set-Content -LiteralPath "$lut\Develop\Mine\user.dctl" "user file"
& $ps -NoProfile -ExecutionPolicy Bypass -File (Join-Path $pkg "installer\uninstall.ps1") -StateDir $state -Yes -SkipResolveCheck | Out-Null
$left = @(Get-ChildItem -LiteralPath $base -Recurse -File | Where-Object { -not $_.FullName.StartsWith($pkg) } | ForEach-Object { $_.FullName.Substring($base.Length + 1) })
Write-Output "after uninstall, left: $($left -join ' | ')"
if ($bad -or $list.Count -ne $samples.Count -or $left.Count -ne 2) { Write-Output "FAILED"; exit 1 }
Write-Output "passed"
