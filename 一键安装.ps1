# Windows 一键安装脚本
# 使用 winget 自动安装所有依赖

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Drama Processor - 一键安装脚本  " -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# 检查 winget
Write-Host "[0/4] 检查 winget..." -ForegroundColor Yellow
$winget = Get-Command winget -ErrorAction SilentlyContinue
if (-not $winget) {
    Write-Host "  ❌ winget 不可用" -ForegroundColor Red
    Write-Host ""
    Write-Host "  你的 Windows 版本不支持 winget（需要 Windows 10 1809+ 或 Windows 11）" -ForegroundColor Yellow
    Write-Host "  请使用手动安装方式，参考文档：docs\WINDOWS_使用教程.md" -ForegroundColor Yellow
    exit 1
}
Write-Host "  ✅ winget 可用" -ForegroundColor Green

# 1. 安装 Python
Write-Host ""
Write-Host "[1/4] 安装 Python..." -ForegroundColor Yellow
$pythonInstalled = Get-Command python -ErrorAction SilentlyContinue
if ($pythonInstalled) {
    $pythonVersion = python --version 2>&1
    Write-Host "  ✅ Python 已安装: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "  正在安装 Python 3.12..." -ForegroundColor Cyan
    winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Python 安装完成" -ForegroundColor Green
        Write-Host "  ⚠️  请关闭并重新打开 PowerShell 以使用 Python" -ForegroundColor Yellow
        Write-Host "  然后重新运行此脚本继续安装" -ForegroundColor Yellow
        pause
        exit 0
    } else {
        Write-Host "  ❌ Python 安装失败" -ForegroundColor Red
        exit 1
    }
}

# 2. 安装 FFmpeg
Write-Host ""
Write-Host "[2/4] 安装 FFmpeg..." -ForegroundColor Yellow
$ffmpegInstalled = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpegInstalled) {
    Write-Host "  ✅ FFmpeg 已安装" -ForegroundColor Green
} else {
    Write-Host "  正在安装 FFmpeg..." -ForegroundColor Cyan
    winget install --id=Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ FFmpeg 安装完成" -ForegroundColor Green
    } else {
        Write-Host "  ❌ FFmpeg 安装失败" -ForegroundColor Red
        exit 1
    }
}

# 3. 创建虚拟环境
Write-Host ""
Write-Host "[3/4] 创建虚拟环境..." -ForegroundColor Yellow
if (Test-Path "venv\Scripts\activate.ps1") {
    Write-Host "  ✅ 虚拟环境已存在" -ForegroundColor Green
} else {
    Write-Host "  创建虚拟环境..." -ForegroundColor Cyan
    python -m venv venv
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ 虚拟环境创建完成" -ForegroundColor Green
    } else {
        Write-Host "  ❌ 虚拟环境创建失败" -ForegroundColor Red
        exit 1
    }
}

# 4. 安装依赖
Write-Host ""
Write-Host "[4/4] 安装 Python 依赖..." -ForegroundColor Yellow
Write-Host "  激活虚拟环境..." -ForegroundColor Cyan
& .\venv\Scripts\Activate.ps1

Write-Host "  安装依赖（可能需要几分钟）..." -ForegroundColor Cyan
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ 依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "  ❌ 依赖安装失败" -ForegroundColor Red
    exit 1
}

# 完成
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  ✅ 安装完成！" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# 运行测试
$response = Read-Host "是否运行环境测试？(y/n)"
if ($response -eq "y" -or $response -eq "Y") {
    Write-Host ""
    python scripts\test_windows.py
}

Write-Host ""
Write-Host "📚 下一步：" -ForegroundColor Yellow
Write-Host "  1. 创建配置文件：" -ForegroundColor Cyan
Write-Host "     copy configs\windows_default.yaml configs\users\my_config.yaml" -ForegroundColor White
Write-Host "     notepad configs\users\my_config.yaml" -ForegroundColor White
Write-Host ""
Write-Host "  2. 开始处理：" -ForegroundColor Cyan
Write-Host "     .\venv\Scripts\activate" -ForegroundColor White
Write-Host "     python -m drama_processor process ""E:\短剧\你的剧集""" -ForegroundColor White
Write-Host ""
Write-Host "💡 查看完整文档：docs\WINDOWS_使用教程.md" -ForegroundColor Yellow
Write-Host ""
