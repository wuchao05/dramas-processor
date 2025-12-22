$ErrorActionPreference = "Stop"

# Windows 便携版 GUI 打包脚本（需要先安装 pyinstaller）
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
    throw "无法定位项目根目录，请在项目根目录执行该脚本。"
}

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Host "未检测到 pyinstaller，请先安装：pip install pyinstaller"
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

Write-Host "生成完成：$distDir\drama-processor-gui.exe"
