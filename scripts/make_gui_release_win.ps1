$ErrorActionPreference = "Stop"

# Windows portable GUI build script (requires pyinstaller)
$scriptDir = $PSScriptRoot
if (-not $scriptDir) {
    $scriptPath = $PSCommandPath
    if (-not $scriptPath) {
        $scriptPath = $MyInvocation.MyCommand.Path
    }
    if ($scriptPath) {
        $scriptDir = Split-Path -Parent $scriptPath
    }
}
if (-not $scriptDir) {
    $scriptDir = (Get-Location).Path
}

$repoRoot = Split-Path -Parent $scriptDir
$entry = Join-Path $repoRoot "src\drama_processor\gui\app.py"
if (-not (Test-Path $entry)) {
    $repoRoot = (Get-Location).Path
    $entry = Join-Path $repoRoot "src\drama_processor\gui\app.py"
}
if (-not (Test-Path $entry)) {
    throw "Unable to locate project root. Run this script from the repo root."
}

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Host "pyinstaller not found. Install it with: pip install pyinstaller"
    exit 1
}

$distDir = Join-Path $repoRoot "dist_gui"
$buildDir = Join-Path $repoRoot "build_gui"

if (Test-Path $distDir) { Remove-Item $distDir -Recurse -Force }
if (Test-Path $buildDir) { Remove-Item $buildDir -Recurse -Force }

$addData = @(
    "$repoRoot\assets;assets",
    "$repoRoot\configs;configs"
)

$addDataArgs = @()
foreach ($item in $addData) {
    $addDataArgs += @("--add-data", $item)
}

& pyinstaller -F -w -n "drama-processor-gui" $entry @addDataArgs --distpath $distDir --workpath $buildDir

Write-Host ("Done: {0}" -f (Join-Path $distDir "drama-processor-gui.exe"))
