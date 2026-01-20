# 短剧剪辑工具 - 达人打包脚本
# 用途：将项目打包为可交付给达人的压缩包

param(
    [string]$Name = "",
    [string]$OutputDir = "D:\打包输出"
)

# 设置控制台编码为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
# 设置 PowerShell 会话编码
chcp 65001 | Out-Null

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  短剧剪辑工具 - 达人打包脚本" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# 检查是否提供了达人名称
if ([string]::IsNullOrWhiteSpace($Name)) {
    Write-Host "❌ 请指定达人名称！" -ForegroundColor Red
    Write-Host ""
    Write-Host "使用方法：" -ForegroundColor Yellow
    Write-Host "  .\打包给达人.ps1 -Name xh" -ForegroundColor Cyan
    Write-Host "  .\打包给达人.ps1 -Name xl" -ForegroundColor Cyan
    Write-Host "  .\打包给达人.ps1 -Name xx" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "或者使用打包工具：" -ForegroundColor Yellow
    Write-Host "  .\打包工具.bat" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "可用的达人配置：" -ForegroundColor Yellow
    Get-ChildItem "configs\users\*.yaml" | ForEach-Object {
        $configName = $_.BaseName
        Write-Host "  - $configName" -ForegroundColor Green
    }
    exit 1
}

# 检查配置文件是否存在
$userConfigFile = "configs\users\${Name}.yaml"
if (-not (Test-Path $userConfigFile)) {
    Write-Host "❌ 配置文件不存在: $userConfigFile" -ForegroundColor Red
    Write-Host ""
    Write-Host "可用的达人配置：" -ForegroundColor Yellow
    Get-ChildItem "configs\users\*.yaml" | ForEach-Object {
        $configName = $_.BaseName
        Write-Host "  - $configName" -ForegroundColor Green
    }
    exit 1
}

Write-Host "✓ 找到配置文件: ${Name}.yaml" -ForegroundColor Green
Write-Host "✓ 打包对象: $Name" -ForegroundColor Green
Write-Host ""

# 设置输出路径
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$packageName = "短剧剪辑工具-${Name}-${timestamp}"
$packagePath = Join-Path $OutputDir $packageName
$zipFile = "${packagePath}.zip"

Write-Host "[1/6] 创建打包目录..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $packagePath -Force | Out-Null
New-Item -ItemType Directory -Path "${packagePath}\项目文件" -Force | Out-Null

# 复制核心文件
Write-Host "[2/6] 复制项目核心文件..." -ForegroundColor Yellow

# 复制基础文件和目录（只包含运行必需的文件）
$basicItems = @("src", "assets", "requirements.txt", "requirements_ai.txt", "pyproject.toml")
foreach ($item in $basicItems) {
    if (Test-Path $item) {
        Copy-Item -Path $item -Destination "${packagePath}\项目文件\" -Recurse -Force
        Write-Host "  ✓ 已复制: $item" -ForegroundColor Green
    }
}

# 复制 configs 目录（但只包含该达人的配置）
Write-Host "  复制配置文件（仅 ${Name}）..." -ForegroundColor Cyan
New-Item -ItemType Directory -Path "${packagePath}\项目文件\configs" -Force | Out-Null
New-Item -ItemType Directory -Path "${packagePath}\项目文件\configs\users" -Force | Out-Null

# 复制默认配置文件
Copy-Item -Path "configs\default.yaml" -Destination "${packagePath}\项目文件\configs\" -Force

# 只复制该达人的配置文件
$userConfigFile = "configs\users\${Name}.yaml"
$userDailyConfigFile = "configs\users\${Name}-daily.yaml"

Copy-Item -Path $userConfigFile -Destination "${packagePath}\项目文件\configs\users\" -Force
Write-Host "  ✓ 已复制达人配置: ${Name}.yaml" -ForegroundColor Green

if (Test-Path $userDailyConfigFile) {
    Copy-Item -Path $userDailyConfigFile -Destination "${packagePath}\项目文件\configs\users\" -Force
    Write-Host "  ✓ 已复制达人配置: ${Name}-daily.yaml" -ForegroundColor Green
}

# 修改 default.yaml 的 active_user
$defaultConfigPath = "${packagePath}\项目文件\configs\default.yaml"
$defaultConfig = Get-Content $defaultConfigPath -Raw -Encoding UTF8
$defaultConfig = $defaultConfig -replace "active_user:.*", "active_user: ${Name}"
$defaultConfig | Out-File -FilePath $defaultConfigPath -Encoding UTF8 -NoNewline
Write-Host "  ✓ 已设置 active_user: ${Name}" -ForegroundColor Green

# 复制和创建启动脚本
Write-Host "[3/6] 创建启动脚本..." -ForegroundColor Yellow

# 复制必要的脚本
Copy-Item -Path "运行一键安装.bat" -Destination $packagePath -Force
Write-Host "  ✓ 已复制运行一键安装.bat" -ForegroundColor Green

# 复制一键安装.ps1到项目文件目录（供运行一键安装.bat调用）
Copy-Item -Path "一键安装.ps1" -Destination "${packagePath}\项目文件\" -Force
Write-Host "  ✓ 已复制一键安装.ps1到项目文件目录" -ForegroundColor Green

# 创建达人专属的飞书监控启动脚本
# 使用英文避免编码问题
$feishuBatContent = @"
@echo off
chcp 65001 >nul
title Feishu Watcher - ${Name}

echo ========================================
echo   Drama Processor - Feishu Watcher
echo   User: ${Name}
echo ========================================
echo.

cd /d "%~dp0项目文件"
if not exist venv\Scripts\activate.bat (
    echo [ERROR] Virtual environment not found!
    echo Please run: Install.ps1
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo.
echo [OK] Starting Feishu watcher...
echo.

python -m drama_processor --config configs\default.yaml feishu watch

echo.
echo ========================================
echo   Watcher stopped
echo ========================================
pause
"@

$feishuBatPath = Join-Path $packagePath "启动飞书监控.bat"
# 使用 UTF-8 with BOM 编码
$utf8BOM = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllText($feishuBatPath, $feishuBatContent, $utf8BOM)
Write-Host "  ✓ 已创建: 启动飞书监控.bat（配置: ${Name}.yaml）" -ForegroundColor Green

# 跳过其他说明文件
Write-Host "[4/6] 跳过说明文件生成..." -ForegroundColor Yellow
Write-Host "  ✓ 仅保留必要文件" -ForegroundColor Green

# [5/6] 步骤已合并 - 跳过 Checklist 创建
Write-Host "[5/6] 跳过 Checklist 创建..." -ForegroundColor Yellow
Write-Host "  ✓ 简化打包，不包含 Checklist" -ForegroundColor Green

# 压缩文件
Write-Host "[6/6] 压缩打包文件..." -ForegroundColor Yellow
if (Test-Path $zipFile) {
    Remove-Item $zipFile -Force
}

Compress-Archive -Path $packagePath -DestinationPath $zipFile -Force
Write-Host "  ✓ 压缩完成: $zipFile" -ForegroundColor Green

# 清理临时目录
Remove-Item -Path $packagePath -Recurse -Force

# 完成
Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "  ✅ 打包完成！" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "📦 打包文件：" -ForegroundColor Cyan
Write-Host "   $zipFile" -ForegroundColor White
Write-Host ""
Write-Host "📝 文件大小：" -ForegroundColor Cyan
$fileSize = (Get-Item $zipFile).Length / 1MB
Write-Host "   $([math]::Round($fileSize, 2)) MB" -ForegroundColor White
Write-Host ""
Write-Host "🎯 下一步操作：" -ForegroundColor Cyan
Write-Host "   1. 将压缩包发送给达人" -ForegroundColor White
Write-Host "   2. 告知达人解压到任意位置" -ForegroundColor White
Write-Host "   3. 指导达人双击'运行一键安装.bat'安装环境" -ForegroundColor White
Write-Host "   4. 安装完成后双击'启动飞书监控.bat'开始使用" -ForegroundColor White
Write-Host ""

# 打开输出目录
Start-Process explorer.exe -ArgumentList $OutputDir
