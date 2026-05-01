# 通用运行时打包脚本
# 用途：将 drama_processor 打包为可导入 Electron 客户端的统一运行时压缩包

param(
    [string]$OutputDir = "D:\打包输出"
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
if ($IsWindows -or $PSVersionTable.PSVersion.Major -lt 6) {
    chcp 65001 | Out-Null
}

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  Drama Processor 通用运行时打包" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$packageName = "drama-processor-runtime-${timestamp}"
$packagePath = Join-Path $OutputDir $packageName
$zipFile = "${packagePath}.zip"
$runtimeRoot = Join-Path $packagePath "drama-processor"

Write-Host "[1/6] 创建打包目录..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $packagePath -Force | Out-Null
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null

Write-Host "[2/6] 复制运行时核心文件..." -ForegroundColor Yellow
$runtimeItems = @("src", "assets", "bin", "requirements.txt", "requirements_ai.txt", "pyproject.toml")
foreach ($item in $runtimeItems) {
    if (Test-Path $item) {
        Copy-Item -Path $item -Destination $runtimeRoot -Recurse -Force
        Write-Host "  ✓ 已复制: $item" -ForegroundColor Green
    }
}

Write-Host "[3/6] 准备通用配置..." -ForegroundColor Yellow
$configRoot = Join-Path $runtimeRoot "configs"
New-Item -ItemType Directory -Path $configRoot -Force | Out-Null

$sourceDefaultConfig = "configs\default.yaml"
if (-not (Test-Path $sourceDefaultConfig)) {
    Write-Host "❌ 找不到默认配置文件: $sourceDefaultConfig" -ForegroundColor Red
    exit 1
}

$packagedDefaultConfig = Join-Path $configRoot "default.yaml"
Copy-Item -Path $sourceDefaultConfig -Destination $packagedDefaultConfig -Force

Write-Host "  ✓ 已复制默认配置 default.yaml" -ForegroundColor Green

Write-Host "[4/6] 复制安装入口..." -ForegroundColor Yellow
Copy-Item -Path "run-install.bat" -Destination $packagePath -Force
Write-Host "  ✓ 已复制 run-install.bat" -ForegroundColor Green

Copy-Item -Path "install.ps1" -Destination $runtimeRoot -Force
Write-Host "  ✓ 已复制 install.ps1" -ForegroundColor Green

Write-Host "[5/6] 生成压缩包..." -ForegroundColor Yellow
if (Test-Path $zipFile) {
    Remove-Item $zipFile -Force
}
Compress-Archive -Path $packagePath -DestinationPath $zipFile -Force
Write-Host "  ✓ 压缩完成: $zipFile" -ForegroundColor Green

Write-Host "[6/6] 清理临时目录..." -ForegroundColor Yellow
Remove-Item -Path $packagePath -Recurse -Force
Write-Host "  ✓ 临时目录已清理" -ForegroundColor Green

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "  ✅ 通用运行时打包完成！" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "📦 打包文件：" -ForegroundColor Cyan
Write-Host "   $zipFile" -ForegroundColor White
Write-Host ""
Write-Host "📝 文件大小：" -ForegroundColor Cyan
$fileSize = (Get-Item $zipFile).Length / 1MB
Write-Host "   $([math]::Round($fileSize, 2)) MB" -ForegroundColor White
Write-Host ""
Write-Host "🎯 Next Steps:" -ForegroundColor Cyan
Write-Host "   1. 在客户端素材剪辑页导入这个 zip 包" -ForegroundColor White
Write-Host "   2. 导入后点击环境安装" -ForegroundColor White
Write-Host "   3. 环境就绪后在客户端内执行剪辑" -ForegroundColor White
Write-Host ""

try {
    if ($IsWindows -or $PSVersionTable.PSVersion.Major -lt 6) {
        Start-Process explorer.exe -ArgumentList $OutputDir
    } elseif ($IsMacOS) {
        & open $OutputDir
    } elseif ($IsLinux) {
        & xdg-open $OutputDir
    }
} catch {
    Write-Host "提示：无法自动打开输出目录，请手动查看：$OutputDir" -ForegroundColor Yellow
}
