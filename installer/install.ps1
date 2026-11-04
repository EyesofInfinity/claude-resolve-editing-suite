# Claude Resolve Editing Suite installer for DaVinci Resolve on Windows. MIT License.
#
# Run Install.bat, which starts this script. It copies, from this folder as you cloned or downloaded it:
#   Develop 1 Light.dctl, Develop 2 Color.dctl   into Resolve's LUT folder, LUT\Develop
#   nodes\*.dctl                                 into LUT\Develop\Nodes
#   effects\<family>\build\*.dctl                into LUT\Develop\<Family>
#   effects\fusegen\out\*.fuse                   into your Fusion Fuses folder, Fuses\Develop
#   plugins\prebuilt\*.vst3                      into C:\Program Files\Common Files\VST3\Develop (asks Windows for admin
#                                                rights, this step only)
# Every file it writes is listed in %LOCALAPPDATA%\Claude Resolve Editing Suite\installed.txt, and Uninstall.bat removes
# exactly those. Nothing is downloaded and nothing outside these folders is changed.
#
# Options: -NoAudio (skip the audio plugins), -Yes (no questions), and for testing -LutRoot, -FuseRoot, -Vst3Root,
# -StateDir to install somewhere else.
param(
    [string]$Source = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)),
    [string]$AppData = $env:APPDATA,
    [string]$LutRoot = "$env:ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT",
    [string]$FuseRoot = "",
    [string]$Vst3Root = "$env:CommonProgramFiles\VST3",
    [string]$StateDir = "$env:LOCALAPPDATA\Claude Resolve Editing Suite",
    [switch]$NoAudio,
    [switch]$Yes
)
$ErrorActionPreference = "Stop"
if (-not $FuseRoot) { $FuseRoot = Join-Path $AppData "Blackmagic Design\DaVinci Resolve\Support\Fusion\Fuses" }
# Install.bat passes "<folder>\." ; made absolute and clean here, or every relative path below loses letters
$Source = (Resolve-Path -LiteralPath $Source).ProviderPath

function Say($text) { Write-Host $text }
function Ask($question) {
    if ($Yes) { return $true }
    $a = Read-Host "$question [Y/n]"
    return ($a -eq "" -or $a -match "^[Yy]")
}

$version = "unknown"
$vf = Join-Path $Source "VERSION.txt"
if (Test-Path -LiteralPath $vf) { $version = (Get-Content -LiteralPath $vf -TotalCount 1).Trim() }
Say ""
Say "Claude Resolve Editing Suite $version for DaVinci Resolve"
Say "========================================================="

# what is in this folder
$vstSrc = Join-Path $Source "plugins\prebuilt"
if (-not (Test-Path -LiteralPath (Join-Path $Source "Develop 1 Light.dctl"))) {
    throw "This folder has no Develop 1 Light.dctl. Run Install.bat from the suite's own folder."
}

# Resolve must be installed; it should be closed, so it loads the new files when it starts
$resolveExe = "$env:ProgramFiles\Blackmagic Design\DaVinci Resolve\Resolve.exe"
if (-not (Test-Path $resolveExe)) { Say "Note: DaVinci Resolve was not found at its usual place. The files are installed anyway." }
if (Get-Process -Name "Resolve" -ErrorAction SilentlyContinue) {
    Say "DaVinci Resolve is running. Close it first, so it loads the new effects when it starts again."
    if (-not (Ask "Continue anyway?")) { Say "Stopped. Nothing was installed."; exit 1 }
}

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
$manifest = Join-Path $StateDir "installed.txt"
$written = New-Object System.Collections.Generic.List[string]
if (Test-Path -LiteralPath $manifest) { foreach ($l in Get-Content -LiteralPath $manifest) { if ($l) { $written.Add($l) } } }
# a failure part way still lists what was copied, so Uninstall.bat can find it
trap { $written | Set-Content -LiteralPath $manifest -Encoding UTF8; break }

function Copy-One($from, $dst) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
    Copy-Item -LiteralPath $from -Destination $dst -Force
    if ((Get-FileHash -LiteralPath $from).Hash -ne (Get-FileHash -LiteralPath $dst).Hash) {
        throw "Copy check failed: $dst"
    }
    if (-not $written.Contains($dst)) { $written.Add($dst) }
}

function Copy-Tree($from, $to) {
    $n = 0
    foreach ($f in Get-ChildItem -LiteralPath $from -Recurse -File) {
        Copy-One $f.FullName (Join-Path $to $f.FullName.Substring($from.Length).TrimStart("\"))
        $n++
    }
    return $n
}

# 1. the DCTLs: the grade pair, the nodes, and every effect family under its capitalised folder name
$lutDev = Join-Path $LutRoot "Develop"
$n = 0
foreach ($f in "Develop 1 Light.dctl", "Develop 2 Color.dctl") {
    Copy-One (Join-Path $Source $f) (Join-Path $lutDev $f)
    $n++
}
foreach ($f in Get-ChildItem -LiteralPath (Join-Path $Source "nodes") -Filter "*.dctl" -File) {
    Copy-One $f.FullName (Join-Path $lutDev "Nodes\$($f.Name)")
    $n++
}
foreach ($fam in Get-ChildItem -LiteralPath (Join-Path $Source "effects") -Directory) {
    $built = Join-Path $fam.FullName "build"
    if (-not (Test-Path -LiteralPath $built)) { continue }
    $folder = $fam.Name.Substring(0, 1).ToUpper() + $fam.Name.Substring(1)
    foreach ($f in Get-ChildItem -LiteralPath $built -Filter "*.dctl" -File) {
        Copy-One $f.FullName (Join-Path $lutDev "$folder\$($f.Name)")
        $n++
    }
}
Say "Effects (DCTL): $n files into $lutDev"

# 2. the Fuses
$fuseSrc = Join-Path $Source "effects\fusegen\out"
if (Test-Path -LiteralPath $fuseSrc) {
    $fuseDev = Join-Path $FuseRoot "Develop"
    $n = Copy-Tree $fuseSrc $fuseDev
    Say "Fusion versions (Fuse): $n files into $fuseDev"
}

$written | Set-Content -LiteralPath $manifest -Encoding UTF8

# 3. the audio plugins: Program Files needs admin rights, so only this step asks for them
$vstDev = Join-Path $Vst3Root "Develop"
if ($NoAudio) {
    Say "Audio plugins: skipped (-NoAudio)."
} elseif (Test-Path -LiteralPath $vstSrc) {
    $bundles = Get-ChildItem -LiteralPath $vstSrc -Directory -Filter "*.vst3"
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
    $canWrite = $false
    try {
        New-Item -ItemType Directory -Force -Path $vstDev -ErrorAction Stop | Out-Null
        $probe = Join-Path $vstDev ".develop-write-test"
        Set-Content -LiteralPath $probe -Value "" -ErrorAction Stop
        Remove-Item -LiteralPath $probe -Force
        $canWrite = $true
    } catch { $canWrite = $false }
    if ($canWrite -or $isAdmin) {
        $n = Copy-Tree $vstSrc $vstDev
        Say "Audio plugins (VST3): $($bundles.Count) plugins into $vstDev"
    } elseif (Ask "The audio plugins go into Program Files, which needs admin rights. Ask Windows for them now?") {
        # paths go into the elevated command as quoted literals: an apostrophe is doubled (a folder like O'Brien's
        # broke the command) and brackets are never read as wildcards
        $qDev = "'" + ($vstDev -replace "'", "''") + "'"
        $qSrc = "'" + ($vstSrc -replace "'", "''") + "'"
        $cmd = "New-Item -ItemType Directory -Force -Path $qDev | Out-Null; " +
               "Get-ChildItem -LiteralPath $qSrc | Copy-Item -Destination $qDev -Recurse -Force"
        try {
            $p = Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Verb RunAs -Wait -PassThru `
                -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $cmd
            if ($p.ExitCode -ne 0) { throw "exit $($p.ExitCode)" }
            foreach ($f in Get-ChildItem -LiteralPath $vstSrc -Recurse -File) {
                $dst = Join-Path $vstDev $f.FullName.Substring($vstSrc.Length).TrimStart("\")
                if (-not (Test-Path -LiteralPath $dst)) { throw "missing $dst" }
                if (-not $written.Contains($dst)) { $written.Add($dst) }
            }
            Say "Audio plugins (VST3): $($bundles.Count) plugins into $vstDev"
        } catch {
            Say "Audio plugins: not installed ($_). Run Install.bat again to retry."
        }
    } else {
        Say "Audio plugins: skipped."
    }
}

$written | Set-Content -LiteralPath $manifest -Encoding UTF8
Say ""
Say "Done. Start DaVinci Resolve. Then open this folder in Claude Code and ask for what you want."
Say "By hand: on the Color page, add the DCTL effect to a node and pick a file from the Develop folder (EFFECTS.md"
Say "shows how). The Fusion versions are in Fusion's tool list, the audio plugins in Fairlight's effects list once"
Say "Resolve has scanned them."
Say "The list of installed files: $manifest"
