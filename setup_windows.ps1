# Drama Processor - Windows 快速设置脚本
# 运行此脚本可快速检查和设置 Windows 环境

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Drama Processor - Windows 快速设置  " -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查 Python
Write-Host "[1/5] 检查 Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python (\d+\.\d+)") {
        $version = $Matches[1]
        if ([double]$version -ge 3.8) {
            Write-Host "  ✅ Python $version 已安装" -ForegroundColor Green
        } else {
            Write-Host "  ❌ Python 版本过低 ($version)，需要 3.8+" -ForegroundColor Red
            Write-Host "     请访问 https://www.python.org/downloads/ 下载" -ForegroundColor Yellow
            exit 1
        }
    }
} catch {
    Write-Host "  ❌ 未安装 Python" -ForegroundColor Red
    Write-Host "     请访问 https://www.python.org/downloads/ 下载安装" -ForegroundColor Yellow
    exit 1
}

# 2. 检查 FFmpeg
Write-Host ""
Write-Host "[2/5] 检查 FFmpeg..." -ForegroundColor Yellow
$ffmpegFound = $false

# 检查 bin 目录
if (Test-Path "bin\ffmpeg.exe") {
    Write-Host "  ✅ 找到内置 FFmpeg: bin\ffmpeg.exe" -ForegroundColor Green
    $ffmpegFound = $true
} else {
    # 检查系统 PATH
    $systemFFmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($systemFFmpeg) {
        Write-Host "  ✅ 找到系统 FFmpeg: $($systemFFmpeg.Source)" -ForegroundColor Green
        $ffmpegFound = $true
    }
}

if (-not $ffmpegFound) {
    Write-Host "  ❌ 未找到 FFmpeg" -ForegroundColor Red
    Write-Host ""
    Write-Host "  请按以下步骤安装：" -ForegroundColor Yellow
    Write-Host "  1. 访问 https://www.gyan.dev/ffmpeg/builds/" -ForegroundColor Cyan
    Write-Host "  2. 下载 'ffmpeg-release-essentials.zip'" -ForegroundColor Cyan
    Write-Host "  3. 解压后，将 ffmpeg.exe 和 ffprobe.exe 复制到项目的 bin\ 文件夹" -ForegroundColor Cyan
    Write-Host ""
    
    $response = Read-Host "  是否现在打开下载页面？(y/n)"
    if ($response -eq "y" -or $response -eq "Y") {
        Start-Process "https://www.gyan.dev/ffmpeg/builds/"
    }
    exit 1
}

# 3. 检查虚拟环境
Write-Host ""
Write-Host "[3/5] 检查虚拟环境..." -ForegroundColor Yellow
if (Test-Path "venv\Scripts\activate.ps1") {
    Write-Host "  ✅ 虚拟环境已存在" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  虚拟环境不存在" -ForegroundColor Yellow
    $response = Read-Host "  是否创建虚拟环境？(y/n)"
    if ($response -eq "y" -or $response -eq "Y") {
        Write-Host "  创建虚拟环境..." -ForegroundColor Cyan
        python -m venv venv
        Write-Host "  ✅ 虚拟环境创建完成" -ForegroundColor Green
    } else {
        Write-Host "  跳过虚拟环境创建" -ForegroundColor Yellow
    }
}

# 4. 安装依赖
Write-Host ""
Write-Host "[4/5] 检查依赖..." -ForegroundColor Yellow
if (Test-Path "venv\Scripts\activate.ps1") {
    Write-Host "  激活虚拟环境..." -ForegroundColor Cyan
    & .\venv\Scripts\Activate.ps1
    
    # 检查是否已安装
    $clickInstalled = & python -c "import click" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ 依赖已安装" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  依赖未安装" -ForegroundColor Yellow
        $response = Read-Host "  是否安装依赖？(y/n)"
        if ($response -eq "y" -or $response -eq "Y") {
            Write-Host "  安装依赖（可能需要几分钟）..." -ForegroundColor Cyan
            pip install -r requirements.txt
            Write-Host "  ✅ 依赖安装完成" -ForegroundColor Green
        } else {
            Write-Host "  ⚠️  跳过依赖安装，某些功能可能无法使用" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  ⚠️  跳过（虚拟环境未创建）" -ForegroundColor Yellow
}

# 5. 运行测试
Write-Host ""
Write-Host "[5/5] 运行环境测试..." -ForegroundColor Yellow
$response = Read-Host "  是否运行环境测试？(y/n)"
if ($response -eq "y" -or $response -eq "Y") {
    Write-Host ""
    if (Test-Path "venv\Scripts\python.exe") {
        & .\venv\Scripts\python.exe scripts\test_windows.py
    } else {
        python scripts\test_windows.py
    }
}

# 完成
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  ✅ 设置完成！" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📚 下一步：" -ForegroundColor Yellow
Write-Host "  1. 查看使用教程：docs\WINDOWS_使用教程.md" -ForegroundColor Cyan
Write-Host "  2. 编辑配置文件：configs\windows_default.yaml" -ForegroundColor Cyan
Write-Host "  3. 运行处理命令：" -ForegroundColor Cyan
Write-Host "     .\venv\Scripts\activate" -ForegroundColor White
Write-Host "     python -m drama_processor --help" -ForegroundColor White
Write-Host ""
Write-Host "💡 提示：" -ForegroundColor Yellow
Write-Host "  - 完整使用教程：docs\WINDOWS_使用教程.md" -ForegroundColor Cyan
Write-Host "  - 命令详细文档：COMMANDS_USAGE_GUIDE.md" -ForegroundColor Cyan
Write-Host "  - 问题反馈：提交 Issue 到项目仓库" -ForegroundColor Cyan
Write-Host ""
