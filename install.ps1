# Windows 一键安装脚本
# 使用 winget 自动安装所有依赖

# 设置控制台编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null


Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Drama Processor - 一键安装脚本  " -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# 检查并切换到正确的目录
$scriptDir = $PSScriptRoot
Set-Location $scriptDir

# 检查 requirements.txt 是否存在
if (-not (Test-Path "requirements.txt")) {
    Write-Host "  ❌ 找不到 requirements.txt 文件" -ForegroundColor Red
    Write-Host "  当前目录: $(Get-Location)" -ForegroundColor Yellow
    Write-Host "  脚本目录: $scriptDir" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "工作目录: $scriptDir" -ForegroundColor Green
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

# 检测 Python 是否可用
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
$needInstall = $false

if ($pythonCmd) {
    $pythonPath = $pythonCmd.Source
    Write-Host "  [DEBUG] 检测到 Python: $pythonPath" -ForegroundColor Gray
    
    # 检查是否是 Windows Store 占位符
    if ($pythonPath -like "*WindowsApps*") {
        Write-Host "  ⚠️  检测到 Windows Store Python 占位符（不完整）" -ForegroundColor Yellow
        Write-Host "  将安装完整版 Python..." -ForegroundColor Cyan
        $needInstall = $true
    } else {
        # 检查 Python 是否真正可用
        $pythonVersion = python --version 2>&1 | Out-String
        if ($pythonVersion -and $pythonVersion.Trim()) {
            Write-Host "  ✅ Python 已安装: $($pythonVersion.Trim())" -ForegroundColor Green
        } else {
            Write-Host "  ⚠️  Python 命令存在但不可用" -ForegroundColor Yellow
            $needInstall = $true
        }
    }
} else {
    Write-Host "  未检测到 Python" -ForegroundColor Yellow
    $needInstall = $true
}

# 安装 Python
if ($needInstall) {
    Write-Host "  正在安装 Python 3.12（完整版）..." -ForegroundColor Cyan
    Write-Host "  这可能需要几分钟，请耐心等待..." -ForegroundColor Gray
    
    winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements --silent
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Python 安装完成" -ForegroundColor Green
        Write-Host ""
        Write-Host "  ⚠️  重要：请按以下步骤操作" -ForegroundColor Yellow
        Write-Host "  1. 关闭此窗口" -ForegroundColor Cyan
        Write-Host "  2. 重新双击 run-install.bat" -ForegroundColor Cyan
        Write-Host "  3. Python 将在新的环境中可用" -ForegroundColor Cyan
        Write-Host ""
        pause
        exit 0
    } else {
        Write-Host "  ❌ Python 安装失败" -ForegroundColor Red
        Write-Host ""
        Write-Host "  请手动安装 Python:" -ForegroundColor Yellow
        Write-Host "  1. 访问 https://www.python.org/downloads/" -ForegroundColor Cyan
        Write-Host "  2. 下载 Python 3.12" -ForegroundColor Cyan
        Write-Host "  3. 安装时勾选 'Add Python to PATH'" -ForegroundColor Cyan
        pause
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

# 检查当前目录
Write-Host "  当前目录: $(Get-Location)" -ForegroundColor Gray

if (Test-Path "venv\Scripts\activate.ps1") {
    Write-Host "  ✅ 虚拟环境已存在" -ForegroundColor Green
} else {
    Write-Host "  创建虚拟环境..." -ForegroundColor Cyan
    
    # 检查 Python 可执行性
    Write-Host "  [DEBUG] 测试 Python 命令..." -ForegroundColor Gray
    try {
        $pythonPath = (Get-Command python -ErrorAction Stop).Source
        Write-Host "  [DEBUG] Python 路径: $pythonPath" -ForegroundColor Gray
        
        $pythonVersion = python --version 2>&1 | Out-String
        Write-Host "  [DEBUG] Python 版本: $($pythonVersion.Trim())" -ForegroundColor Gray
    } catch {
        Write-Host "  ❌ Python 命令不可用！" -ForegroundColor Red
        Write-Host "  请确保 Python 已安装并添加到 PATH" -ForegroundColor Yellow
        pause
        exit 1
    }
    
    # 检查 venv 模块
    Write-Host "  [DEBUG] 检查 venv 模块..." -ForegroundColor Gray
    $venvCheck = python -m venv --help 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ❌ venv 模块不可用！" -ForegroundColor Red
        Write-Host "  输出: $venvCheck" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "请重新安装 Python，确保包含所有标准库模块" -ForegroundColor Yellow
        pause
        exit 1
    }
    Write-Host "  [DEBUG] venv 模块可用" -ForegroundColor Gray
    
    # 创建虚拟环境
    Write-Host "  [DEBUG] 正在创建虚拟环境..." -ForegroundColor Gray
    $venvOutput = python -m venv venv 2>&1 | Out-String
    $venvExitCode = $LASTEXITCODE
    
    Write-Host "  [DEBUG] Exit code: $venvExitCode" -ForegroundColor Gray
    if ($venvOutput) {
        Write-Host "  [DEBUG] Output: $venvOutput" -ForegroundColor Gray
    }
    
    # 等待文件系统同步
    Start-Sleep -Seconds 2
    
    # 验证虚拟环境是否创建成功
    if (Test-Path "venv\Scripts\activate.ps1") {
        Write-Host "  ✅ 虚拟环境创建完成" -ForegroundColor Green
    } else {
        Write-Host "  ❌ 虚拟环境创建失败（文件未生成）" -ForegroundColor Red
        Write-Host ""
        Write-Host "可能的原因：" -ForegroundColor Yellow
        Write-Host "  1. 当前目录没有写入权限" -ForegroundColor Yellow
        Write-Host "  2. 磁盘空间不足" -ForegroundColor Yellow
        Write-Host "  3. 杀毒软件阻止文件创建" -ForegroundColor Yellow
        Write-Host "  4. 路径包含特殊字符或过长" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "解决方法：" -ForegroundColor Cyan
        Write-Host "  1. 以管理员身份运行此脚本" -ForegroundColor Cyan
        Write-Host "  2. 将文件夹移动到更短的路径（如 C:\drama-processor）" -ForegroundColor Cyan
        Write-Host "  3. 暂时禁用杀毒软件" -ForegroundColor Cyan
        Write-Host "  4. 检查磁盘剩余空间（至少需要 500MB）" -ForegroundColor Cyan
        pause
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
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ 依赖安装失败" -ForegroundColor Red
    exit 1
}

Write-Host "  安装本地包..." -ForegroundColor Cyan
pip install -e . --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ 依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "  ❌ 本地包安装失败" -ForegroundColor Red
    exit 1
}

# 5. 读取并创建素材目录
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  📁 准备素材目录" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# 获取当前激活的用户配置（从 default.yaml 读取）
$defaultConfigPath = "configs\default.yaml"
$activeUser = "xh"  # 默认值

if (Test-Path $defaultConfigPath) {
    $defaultConfigContent = Get-Content $defaultConfigPath -Raw -Encoding UTF8
    if ($defaultConfigContent -match 'active_user:\s*(\S+)') {
        $activeUser = $matches[1]
        Write-Host "检测到激活用户：$activeUser" -ForegroundColor Gray
    }
}

# 读取用户配置文件中的路径
$userConfigPath = "configs\users\${activeUser}.yaml"
$sourcePath = "D:\短剧剪辑\源素材视频"  # 默认值
$outputPath = "D:\短剧剪辑\输出素材"    # 默认值
$tempPath = $null                      # 可选
$tailCachePath = $null                 # 可选

if (Test-Path $userConfigPath) {
    try {
        $configContent = Get-Content $userConfigPath -Raw -Encoding UTF8
        
        # 读取 default_source_dir
        if ($configContent -match 'default_source_dir:\s*"([^"]*)"') {
            $configuredPath = $matches[1]
            # 反转义 Windows 路径（\\ -> \）
            $sourcePath = $configuredPath -replace '\\\\', '\'
            
            # 提取盘符用于推断输出路径
            if ($sourcePath -match '^([A-Z]:)\\') {
                $driveLetter = $matches[1]
                $inferredOutputPath = "${driveLetter}\短剧剪辑\输出素材"
            }
        }
        
        # 读取 output_dir（优先使用配置中的值）
        if ($configContent -match 'output_dir:\s*"([^"]*)"') {
            $configuredOutput = $matches[1]
            $outputPath = $configuredOutput -replace '\\\\', '\'
        } elseif ($inferredOutputPath) {
            # 如果配置中没有 output_dir，使用推断的路径
            $outputPath = $inferredOutputPath
        }
        
        # 读取 temp_dir（可选，用于性能优化）
        if ($configContent -match 'temp_dir:\s*"([^"]*)"') {
            $configuredTemp = $matches[1]
            $tempPath = $configuredTemp -replace '\\\\', '\'
        }
        
        # 读取 tail_cache_dir（可选，用于性能优化）
        if ($configContent -match 'tail_cache_dir:\s*"([^"]*)"') {
            $configuredCache = $matches[1]
            $tailCachePath = $configuredCache -replace '\\\\', '\'
        }
        
        Write-Host "从配置文件读取到的路径：" -ForegroundColor Cyan
        Write-Host "  源素材目录：$sourcePath" -ForegroundColor White
        Write-Host "  输出目录：  $outputPath" -ForegroundColor White
        if ($tempPath) {
            Write-Host "  临时目录：  $tempPath" -ForegroundColor White
        }
        if ($tailCachePath) {
            Write-Host "  尾部缓存：  $tailCachePath" -ForegroundColor White
        }
    } catch {
        Write-Host "  ⚠️ 配置读取失败，使用默认路径" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ⚠️ 未找到用户配置文件，使用默认路径" -ForegroundColor Yellow
}

Write-Host ""

# 创建目录
Write-Host "创建目录..." -ForegroundColor Cyan
$directoriesCreated = 0
$directoriesFailed = 0

try {
    if (-not (Test-Path $sourcePath)) {
        New-Item -ItemType Directory -Path $sourcePath -Force | Out-Null
        Write-Host "  ✅ 已创建：$sourcePath" -ForegroundColor Green
        $directoriesCreated++
    } else {
        Write-Host "  ✓ 已存在：$sourcePath" -ForegroundColor Gray
    }
} catch {
    Write-Host "  ❌ 创建失败：$sourcePath" -ForegroundColor Red
    Write-Host "     错误：$_" -ForegroundColor Red
    $directoriesFailed++
}

try {
    if (-not (Test-Path $outputPath)) {
        New-Item -ItemType Directory -Path $outputPath -Force | Out-Null
        Write-Host "  ✅ 已创建：$outputPath" -ForegroundColor Green
        $directoriesCreated++
    } else {
        Write-Host "  ✓ 已存在：$outputPath" -ForegroundColor Gray
    }
} catch {
    Write-Host "  ❌ 创建失败：$outputPath" -ForegroundColor Red
    Write-Host "     错误：$_" -ForegroundColor Red
    $directoriesFailed++
}

# 创建临时目录（如果配置中指定）
if ($tempPath) {
    try {
        if (-not (Test-Path $tempPath)) {
            New-Item -ItemType Directory -Path $tempPath -Force | Out-Null
            Write-Host "  ✅ 已创建：$tempPath" -ForegroundColor Green
            $directoriesCreated++
        } else {
            Write-Host "  ✓ 已存在：$tempPath" -ForegroundColor Gray
        }
    } catch {
        Write-Host "  ❌ 创建失败：$tempPath" -ForegroundColor Red
        Write-Host "     错误：$_" -ForegroundColor Red
        $directoriesFailed++
    }
}

# 创建尾部缓存目录（如果配置中指定）
if ($tailCachePath) {
    try {
        if (-not (Test-Path $tailCachePath)) {
            New-Item -ItemType Directory -Path $tailCachePath -Force | Out-Null
            Write-Host "  ✅ 已创建：$tailCachePath" -ForegroundColor Green
            $directoriesCreated++
        } else {
            Write-Host "  ✓ 已存在：$tailCachePath" -ForegroundColor Gray
        }
    } catch {
        Write-Host "  ❌ 创建失败：$tailCachePath" -ForegroundColor Red
        Write-Host "     错误：$_" -ForegroundColor Red
        $directoriesFailed++
    }
}

if ($directoriesFailed -gt 0) {
    Write-Host ""
    Write-Host "  ⚠️ 部分目录创建失败，请手动创建或检查磁盘是否存在" -ForegroundColor Yellow
}

# 完成
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  ✅ 安装完成！" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "📚 下一步：" -ForegroundColor Yellow
Write-Host "  1. 将源素材放到：$sourcePath" -ForegroundColor Cyan
Write-Host "     （每部剧一个文件夹，文件夹名=剧名）" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. 双击运行：启动飞书监控.bat" -ForegroundColor Cyan
Write-Host ""
Write-Host "  3. 剪辑完成后，素材会输出到：$outputPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 查看详细使用说明：达人使用说明.txt" -ForegroundColor Yellow
Write-Host ""
