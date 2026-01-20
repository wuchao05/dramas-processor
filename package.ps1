# 短剧剪辑工具 - 达人打包脚本
# 用途：将项目打包为可交付给达人的压缩包

param(
    [string]$Name = "",
    [string]$OutputDir = "D:\打包输出"
)

# 设置控制台编码为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
# 设置 PowerShell 会话编码（仅 Windows）
if ($IsWindows -or $PSVersionTable.PSVersion.Major -lt 6) {
    chcp 65001 | Out-Null
}

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
New-Item -ItemType Directory -Path "${packagePath}\drama-processor" -Force | Out-Null

# 复制核心文件
Write-Host "[2/6] 复制项目核心文件..." -ForegroundColor Yellow

# 复制基础文件和目录（只包含运行必需的文件）
$basicItems = @("src", "assets", "requirements.txt", "requirements_ai.txt", "pyproject.toml")
foreach ($item in $basicItems) {
    if (Test-Path $item) {
        Copy-Item -Path $item -Destination "${packagePath}\drama-processor\" -Recurse -Force
        Write-Host "  ✓ 已复制: $item" -ForegroundColor Green
    }
}

# 复制 configs 目录（但只包含该达人的配置）
Write-Host "  复制配置文件（仅 ${Name}）..." -ForegroundColor Cyan
New-Item -ItemType Directory -Path "${packagePath}\drama-processor\configs" -Force | Out-Null
New-Item -ItemType Directory -Path "${packagePath}\drama-processor\configs\users" -Force | Out-Null

# 复制默认配置文件
Copy-Item -Path "configs\default.yaml" -Destination "${packagePath}\drama-processor\configs\" -Force

# 只复制该达人的配置文件
$userConfigFile = "configs\users\${Name}.yaml"
$userDailyConfigFile = "configs\users\${Name}-daily.yaml"

Copy-Item -Path $userConfigFile -Destination "${packagePath}\drama-processor\configs\users\" -Force
Write-Host "  ✓ 已复制达人配置: ${Name}.yaml" -ForegroundColor Green

if (Test-Path $userDailyConfigFile) {
    Copy-Item -Path $userDailyConfigFile -Destination "${packagePath}\drama-processor\configs\users\" -Force
    Write-Host "  ✓ 已复制达人配置: ${Name}-daily.yaml" -ForegroundColor Green
}

# 修改 default.yaml 的 active_user
$defaultConfigPath = "${packagePath}\drama-processor\configs\default.yaml"
$defaultConfig = Get-Content $defaultConfigPath -Raw -Encoding UTF8
$defaultConfig = $defaultConfig -replace "active_user:.*", "active_user: ${Name}"
$defaultConfig | Out-File -FilePath $defaultConfigPath -Encoding UTF8 -NoNewline
Write-Host "  ✓ 已设置 active_user: ${Name}" -ForegroundColor Green

# 复制和创建启动脚本
Write-Host "[3/6] 创建启动脚本..." -ForegroundColor Yellow

# 复制必要的脚本
Copy-Item -Path "run-install.bat" -Destination $packagePath -Force
Write-Host "  ✓ 已复制 run-install.bat" -ForegroundColor Green

# 复制安装脚本到项目目录（供 run-install.bat 调用）
Copy-Item -Path "install.ps1" -Destination "${packagePath}\drama-processor\" -Force
Write-Host "  ✓ 已复制 install.ps1 到项目目录" -ForegroundColor Green

# 创建达人专属的飞书监控启动脚本
# 自动检测并使用最佳终端（Windows Terminal > PowerShell > CMD）
$feishuBatContent = @"
@echo off
REM Try to use Windows Terminal or PowerShell for better Unicode support

REM Check if Windows Terminal is available
where wt.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo Starting in Windows Terminal...
    wt.exe -w 0 new-tab --title "Feishu Watcher - ${Name}" powershell.exe -NoExit -Command "cd '%~dp0drama-processor'; if (Test-Path 'venv\Scripts\activate.ps1') { .\venv\Scripts\activate.ps1; python -m drama_processor --config configs\default.yaml feishu watch } else { Write-Host '[ERROR] Virtual environment not found! Please run run-install.bat first' -ForegroundColor Red; pause }"
    exit /b 0
)

REM Check if PowerShell is available
where powershell.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo Starting in PowerShell...
    start "Feishu Watcher - ${Name}" powershell.exe -NoExit -Command "cd '%~dp0drama-processor'; if (Test-Path 'venv\Scripts\activate.ps1') { .\venv\Scripts\activate.ps1; Write-Host '========================================' -ForegroundColor Cyan; Write-Host '  Drama Processor - Feishu Watcher' -ForegroundColor Cyan; Write-Host '  User: ${Name}' -ForegroundColor Cyan; Write-Host '========================================' -ForegroundColor Cyan; Write-Host ''; python -m drama_processor --config configs\default.yaml feishu watch } else { Write-Host '[ERROR] Virtual environment not found!' -ForegroundColor Red; Write-Host 'Please run: run-install.bat' -ForegroundColor Yellow; pause }"
    exit /b 0
)

REM Fallback to CMD (default)
chcp 65001 >nul
title Feishu Watcher - ${Name}

echo ========================================
echo   Drama Processor - Feishu Watcher
echo   User: ${Name}
echo ========================================
echo.
echo Note: Using CMD. For better display, install Windows Terminal.
echo.

cd /d "%~dp0drama-processor"
if not exist venv\Scripts\activate.bat (
    echo [ERROR] Virtual environment not found!
    echo Please run: run-install.bat
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

$feishuBatPath = Join-Path $packagePath "start-feishu-watch.bat"
# 英文内容，使用 ASCII 编码（完全兼容）
$ascii = [System.Text.Encoding]::ASCII
[System.IO.File]::WriteAllText($feishuBatPath, $feishuBatContent, $ascii)
Write-Host "  ✓ 已创建: start-feishu-watch.bat (Config: ${Name}.yaml)" -ForegroundColor Green

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
Write-Host "🎯 Next Steps:" -ForegroundColor Cyan
Write-Host "   1. Send the package to user" -ForegroundColor White
Write-Host "   2. Extract to any location" -ForegroundColor White
Write-Host "   3. Double-click 'run-install.bat' to install" -ForegroundColor White
Write-Host "   4. Double-click 'start-feishu-watch.bat' to start" -ForegroundColor White
Write-Host ""

# 打开输出目录（跨平台）
try {
    if ($IsWindows -or $PSVersionTable.PSVersion.Major -lt 6) {
        # Windows: 使用 explorer
        Start-Process explorer.exe -ArgumentList $OutputDir
    } elseif ($IsMacOS) {
        # macOS: 使用 open
        & open $OutputDir
    } elseif ($IsLinux) {
        # Linux: 使用 xdg-open
        & xdg-open $OutputDir
    }
} catch {
    # 如果打开失败，只是跳过，不影响打包结果
    Write-Host "提示：无法自动打开输出目录，请手动查看：$OutputDir" -ForegroundColor Yellow
}
