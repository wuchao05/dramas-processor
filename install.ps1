# Windows 一键安装脚本
# 使用 winget 自动安装所有依赖

# 设置控制台编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

# 记录未完成的安装步骤，最后统一汇总，避免单个网络问题中断后续安装
$script:FailedSteps = New-Object "System.Collections.Generic.List[string]"

# 客户端调用时 stdin 被重定向，pause 可能卡住；只在交互式窗口中暂停
function Pause-IfInteractive {
    try {
        if (-not [Console]::IsInputRedirected) {
            pause
        }
    } catch {
    }
}


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
    Pause-IfInteractive
    exit 1
}

Write-Host "工作目录: $scriptDir" -ForegroundColor Green
Write-Host ""

function Sync-ProcessPath {
    $pathEntries = New-Object "System.Collections.Generic.List[string]"

    foreach ($source in @(
        [Environment]::GetEnvironmentVariable("Path", "Machine"),
        [Environment]::GetEnvironmentVariable("Path", "User"),
        $env:Path
    )) {
        if (-not $source) {
            continue
        }

        foreach ($entry in ($source -split ";")) {
            $trimmed = $entry.Trim()
            if ($trimmed -and -not $pathEntries.Contains($trimmed)) {
                $pathEntries.Add($trimmed)
            }
        }
    }

    if ($pathEntries.Count -gt 0) {
        $env:Path = $pathEntries -join ";"
    }
}

# 将目录加入用户 Path（保留原有 %VAR% 写法和 REG_EXPAND_SZ 类型），并同步到当前会话
function Add-UserPathEntry {
    param([string]$Entry)

    $normalizedEntry = $Entry.TrimEnd("\")
    try {
        $envKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Environment", $true)
        try {
            $rawPath = [string]$envKey.GetValue(
                "Path",
                "",
                [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames
            )
            $entries = @($rawPath -split ";" | Where-Object { $_.Trim() })
            $exists = $entries | Where-Object { $_.Trim().TrimEnd("\") -ieq $normalizedEntry }
            if (-not $exists) {
                $newPath = (@($entries) + $normalizedEntry) -join ";"
                $envKey.SetValue("Path", $newPath, [Microsoft.Win32.RegistryValueKind]::ExpandString)
                Write-Host "  已将 $normalizedEntry 加入用户 Path" -ForegroundColor Gray
                Send-EnvironmentChange
            }
        } finally {
            $envKey.Close()
        }
    } catch {
        Write-Host "  ⚠️ 写入用户 Path 失败：$_" -ForegroundColor Yellow
    }

    Sync-ProcessPath
    if (-not (($env:Path -split ";") | Where-Object { $_.Trim().TrimEnd("\") -ieq $normalizedEntry })) {
        $env:Path = "$normalizedEntry;$env:Path"
    }
}

# 通知资源管理器环境变量已变化，新开的终端无需重新登录即可读到（失败不影响安装）
function Send-EnvironmentChange {
    try {
        if (-not ("DramaProcessor.EnvBroadcast" -as [type])) {
            Add-Type -Namespace DramaProcessor -Name EnvBroadcast -MemberDefinition @"
[DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
"@
        }
        $result = [UIntPtr]::Zero
        [DramaProcessor.EnvBroadcast]::SendMessageTimeout(
            [IntPtr]0xffff, 0x1A, [UIntPtr]::Zero, "Environment", 2, 5000, [ref]$result
        ) | Out-Null
    } catch {
    }
}

function Save-RemoteFile {
    param([string]$Url, [string]$OutFile)

    # Windows PowerShell 5.1 默认可能未启用 TLS 1.2
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    # 进度条会让 Invoke-WebRequest 下载大文件变得极慢
    $ProgressPreference = "SilentlyContinue"
    Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing -TimeoutSec 120
}

function Expand-GzipFile {
    param([string]$Source, [string]$Destination)

    $inputStream = [IO.File]::OpenRead($Source)
    try {
        $gzipStream = New-Object IO.Compression.GZipStream($inputStream, [IO.Compression.CompressionMode]::Decompress)
        $outputStream = [IO.File]::Create($Destination)
        try {
            $gzipStream.CopyTo($outputStream)
        } finally {
            $outputStream.Dispose()
            $gzipStream.Dispose()
        }
    } finally {
        $inputStream.Dispose()
    }
}

# 校验暂存目录中的 ffmpeg/ffprobe 可执行后，再复制到运行时 bin 目录
function Copy-FfmpegBinaries {
    param([string]$StagingDir, [string]$TargetDir)

    foreach ($name in @("ffmpeg.exe", "ffprobe.exe")) {
        $candidate = Join-Path $StagingDir $name
        if (-not (Test-Path $candidate)) {
            throw "未找到 $name"
        }
        & $candidate -version *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "$name 无法执行（退出码 $LASTEXITCODE）"
        }
    }

    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
    foreach ($name in @("ffmpeg.exe", "ffprobe.exe")) {
        Copy-Item -Path (Join-Path $StagingDir $name) -Destination $TargetDir -Force
    }
}

function Install-FfmpegFromGzipMirror {
    param([string]$BaseUrl, [string]$TempDir, [string]$TargetDir)

    $stagingDir = Join-Path $TempDir "gzip"
    New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null
    foreach ($name in @("ffmpeg", "ffprobe")) {
        $gzipPath = Join-Path $stagingDir "$name.gz"
        Write-Host "  下载 $BaseUrl/$name-win32-x64.gz" -ForegroundColor Gray
        Save-RemoteFile -Url "$BaseUrl/$name-win32-x64.gz" -OutFile $gzipPath
        Expand-GzipFile -Source $gzipPath -Destination (Join-Path $stagingDir "$name.exe")
    }
    Copy-FfmpegBinaries -StagingDir $stagingDir -TargetDir $TargetDir
}

function Install-FfmpegFromZip {
    param([string]$Url, [string]$TempDir, [string]$TargetDir)

    $zipPath = Join-Path $TempDir "ffmpeg.zip"
    $extractDir = Join-Path $TempDir "zip"
    Remove-Item -Path $zipPath, $extractDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  下载 $Url" -ForegroundColor Gray
    Save-RemoteFile -Url $Url -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

    # 压缩包内通常多一层版本目录，按文件名查找 bin 所在位置
    $ffmpegExe = Get-ChildItem -Path $extractDir -Filter "ffmpeg.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $ffmpegExe) {
        throw "压缩包中未找到 ffmpeg.exe"
    }
    Copy-FfmpegBinaries -StagingDir $ffmpegExe.DirectoryName -TargetDir $TargetDir
}

# 下载 FFmpeg 到运行时 bin 目录：自定义地址 -> 国内镜像 -> gyan.dev
function Install-FfmpegToBin {
    param([string]$TargetDir)

    $sources = New-Object "System.Collections.Generic.List[object]"
    if ($env:DRAMA_FFMPEG_ZIP_URL) {
        $sources.Add(@{ Type = "zip"; Url = $env:DRAMA_FFMPEG_ZIP_URL; Label = "自定义地址" })
    }
    # npmmirror 托管的 ffmpeg-static 二进制，来源为 gyan.dev essentials 构建
    $sources.Add(@{ Type = "gzip"; Url = "https://registry.npmmirror.com/-/binary/ffmpeg-static/b6.1.1"; Label = "npmmirror 国内镜像" })
    $sources.Add(@{ Type = "zip"; Url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"; Label = "gyan.dev" })

    foreach ($source in $sources) {
        $tempDir = Join-Path ([IO.Path]::GetTempPath()) ("drama-ffmpeg-" + [Guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
        try {
            Write-Host "  正在从 $($source.Label) 下载 FFmpeg..." -ForegroundColor Cyan
            if ($source.Type -eq "gzip") {
                Install-FfmpegFromGzipMirror -BaseUrl $source.Url -TempDir $tempDir -TargetDir $TargetDir
            } else {
                Install-FfmpegFromZip -Url $source.Url -TempDir $tempDir -TargetDir $TargetDir
            }
            Write-Host "  ✅ FFmpeg 已下载到 $TargetDir" -ForegroundColor Green
            return $true
        } catch {
            Write-Host "  ⚠️ 从 $($source.Label) 下载失败：$($_.Exception.Message)" -ForegroundColor Yellow
        } finally {
            Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    return $false
}

function Get-UsablePythonInfo {
    $result = [PSCustomObject]@{
        DetectedPath        = $null
        PlaceholderDetected = $false
        Path                = $null
        Version             = $null
        Source              = $null
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        $result.DetectedPath = $pythonCmd.Source

        if ($pythonCmd.Source -notlike "*WindowsApps*") {
            try {
                $pythonVersion = (& $pythonCmd.Source --version 2>&1 | Out-String).Trim()
                if ($LASTEXITCODE -eq 0 -and $pythonVersion) {
                    $result.Path = $pythonCmd.Source
                    $result.Version = $pythonVersion
                    $result.Source = "PATH"
                    return $result
                }
            } catch {
            }
        } else {
            $result.PlaceholderDetected = $true
        }
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            $pythonExe = (& py -3 -c "import sys; print(sys.executable)" 2>&1 | Out-String).Trim()
            $pythonVersion = (& py -3 --version 2>&1 | Out-String).Trim()
            if ($LASTEXITCODE -eq 0 -and $pythonExe -and (Test-Path $pythonExe) -and $pythonVersion) {
                $result.Path = $pythonExe
                $result.Version = $pythonVersion
                $result.Source = "py launcher"
                return $result
            }
        } catch {
        }
    }

    $candidatePaths = @(
        "$env:LocalAppData\Programs\Python\Python312\python.exe",
        "$env:LocalAppData\Programs\Python\Python311\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python311\python.exe",
        "${env:ProgramFiles(x86)}\Python312\python.exe",
        "${env:ProgramFiles(x86)}\Python311\python.exe"
    ) | Where-Object { $_ }

    foreach ($candidate in $candidatePaths) {
        if (-not (Test-Path $candidate)) {
            continue
        }

        try {
            $pythonVersion = (& $candidate --version 2>&1 | Out-String).Trim()
            if ($LASTEXITCODE -eq 0 -and $pythonVersion) {
                $result.Path = $candidate
                $result.Version = $pythonVersion
                $result.Source = "install dir"
                return $result
            }
        } catch {
        }
    }

    return $result
}

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
Sync-ProcessPath
$pythonInfo = Get-UsablePythonInfo
$pythonExe = $null
$needInstall = $false

if ($pythonInfo.DetectedPath) {
    Write-Host "  [DEBUG] 检测到 Python: $($pythonInfo.DetectedPath)" -ForegroundColor Gray
}

if ($pythonInfo.Path) {
    $pythonExe = $pythonInfo.Path
    if ($pythonInfo.Source -ne "PATH") {
        Write-Host "  [DEBUG] 改用可用 Python: $pythonExe ($($pythonInfo.Source))" -ForegroundColor Gray
    }
    Write-Host "  ✅ Python 已安装: $($pythonInfo.Version)" -ForegroundColor Green
} else {
    if ($pythonInfo.PlaceholderDetected) {
        Write-Host "  ⚠️  检测到 Windows Store Python 占位符（不完整）" -ForegroundColor Yellow
        Write-Host "  将安装完整版 Python..." -ForegroundColor Cyan
    } else {
        Write-Host "  未检测到可用的 Python" -ForegroundColor Yellow
    }

    $needInstall = $true
}

# 安装 Python
if ($needInstall) {
    Write-Host "  正在安装 Python 3.12（完整版）..." -ForegroundColor Cyan
    Write-Host "  这可能需要几分钟，请耐心等待..." -ForegroundColor Gray
    
    winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements --silent
    $wingetExitCode = $LASTEXITCODE

    Sync-ProcessPath
    $pythonInfo = Get-UsablePythonInfo

    if ($pythonInfo.Path) {
        $pythonExe = $pythonInfo.Path
        Write-Host "  ✅ Python 已就绪: $($pythonInfo.Version)" -ForegroundColor Green
        if ($pythonInfo.Source -ne "PATH") {
            Write-Host "  [DEBUG] 当前会话改用: $pythonExe ($($pythonInfo.Source))" -ForegroundColor Gray
        }
    } elseif ($wingetExitCode -ne 0) {
        Write-Host "  ❌ Python 安装失败" -ForegroundColor Red
        Write-Host ""
        Write-Host "  请手动安装 Python:" -ForegroundColor Yellow
        Write-Host "  1. 访问 https://www.python.org/downloads/" -ForegroundColor Cyan
        Write-Host "  2. 下载 Python 3.12" -ForegroundColor Cyan
        Write-Host "  3. 安装时勾选 'Add Python to PATH'" -ForegroundColor Cyan
        Pause-IfInteractive
        exit 1
    } else {
        Write-Host "  ❌ Python 安装后仍未找到可执行文件" -ForegroundColor Red
        Write-Host ""
        Write-Host "  请先关闭客户端后重新打开，再重试自动安装。" -ForegroundColor Yellow
        Pause-IfInteractive
        exit 1
    }
}

# 2. 安装 FFmpeg
Write-Host ""
Write-Host "[2/4] 安装 FFmpeg..." -ForegroundColor Yellow
$bundledFfmpegDir = Join-Path $scriptDir "bin"
$bundledFfmpeg = Join-Path $bundledFfmpegDir "ffmpeg.exe"

if (Test-Path $bundledFfmpeg) {
    Write-Host "  ✅ 检测到内置 FFmpeg: $bundledFfmpeg" -ForegroundColor Green
    # 部分剪辑代码直接调用 ffmpeg 命令，需要 bin 目录在 Path 中
    Add-UserPathEntry $bundledFfmpegDir
} elseif (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "  ✅ FFmpeg 已安装" -ForegroundColor Green
} else {
    # 优先下载到运行时 bin 目录；winget 依赖 GitHub，国内网络经常失败，放到最后兜底
    if (Install-FfmpegToBin -TargetDir $bundledFfmpegDir) {
        Add-UserPathEntry $bundledFfmpegDir
    } else {
        Write-Host "  镜像下载均失败，尝试通过 winget 安装 FFmpeg..." -ForegroundColor Cyan
        winget install --id=Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
        $wingetExitCode = $LASTEXITCODE
        Sync-ProcessPath

        if ($wingetExitCode -eq 0 -or (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
            Write-Host "  ✅ FFmpeg 安装完成" -ForegroundColor Green
        } else {
            # 不中断安装，继续准备 Python 环境，最后统一提示
            Write-Host "  ❌ FFmpeg 安装失败，将继续安装 Python 依赖" -ForegroundColor Red
            $script:FailedSteps.Add("FFmpeg：自动下载失败，请手动下载 ffmpeg-release-essentials.zip，将 ffmpeg.exe、ffprobe.exe 放到 $bundledFfmpegDir 后重新安装")
        }
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
        if (-not $pythonExe) {
            Sync-ProcessPath
            $pythonInfo = Get-UsablePythonInfo
            $pythonExe = $pythonInfo.Path
        }
        if (-not $pythonExe) {
            throw "未找到可用的 Python 可执行文件"
        }

        Write-Host "  [DEBUG] Python 路径: $pythonExe" -ForegroundColor Gray

        $pythonVersion = (& $pythonExe --version 2>&1 | Out-String).Trim()
        Write-Host "  [DEBUG] Python 版本: $pythonVersion" -ForegroundColor Gray
    } catch {
        Write-Host "  ❌ Python 命令不可用！" -ForegroundColor Red
        Write-Host "  请确保 Python 已安装并添加到 PATH" -ForegroundColor Yellow
        Pause-IfInteractive
        exit 1
    }
    
    # 检查 venv 模块
    Write-Host "  [DEBUG] 检查 venv 模块..." -ForegroundColor Gray
    $venvCheck = (& $pythonExe -m venv --help 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ❌ venv 模块不可用！" -ForegroundColor Red
        Write-Host "  输出: $venvCheck" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "请重新安装 Python，确保包含所有标准库模块" -ForegroundColor Yellow
        Pause-IfInteractive
        exit 1
    }
    Write-Host "  [DEBUG] venv 模块可用" -ForegroundColor Gray
    
    # 创建虚拟环境
    Write-Host "  [DEBUG] 正在创建虚拟环境..." -ForegroundColor Gray
    $venvOutput = (& $pythonExe -m venv venv 2>&1 | Out-String)
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
        Pause-IfInteractive
        exit 1
    }
}

# 4. 安装依赖
Write-Host ""
Write-Host "[4/4] 安装 Python 依赖..." -ForegroundColor Yellow
# 直接使用虚拟环境里的 python，不依赖 Activate.ps1（执行策略受限时激活会失败）
$venvPython = Join-Path $scriptDir "venv\Scripts\python.exe"

# 依次尝试的 pip 源：自定义源 -> 默认源（含用户 pip 配置）-> 国内镜像
$pipIndexes = New-Object "System.Collections.Generic.List[string]"
if ($env:DRAMA_PIP_INDEX_URL) {
    $pipIndexes.Add($env:DRAMA_PIP_INDEX_URL)
}
$pipIndexes.Add("")
$pipIndexes.Add("https://mirrors.aliyun.com/pypi/simple/")
$pipIndexes.Add("https://pypi.tuna.tsinghua.edu.cn/simple/")

function Invoke-PipInstall {
    param([string[]]$PipArgs, [string]$Description)

    foreach ($index in $pipIndexes) {
        $pipCommandArgs = @("-m", "pip", "install") + $PipArgs + @(
            "--timeout", "30",
            "--retries", "2",
            "--disable-pip-version-check"
        )
        if ($index) {
            $pipCommandArgs += @("-i", $index)
            $indexLabel = $index
        } else {
            $indexLabel = "默认源"
        }

        Write-Host "  [$Description] 使用 $indexLabel ..." -ForegroundColor Cyan
        & $venvPython @pipCommandArgs
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
        Write-Host "  ⚠️ $indexLabel 安装失败，切换下一个源..." -ForegroundColor Yellow
    }

    return $false
}

Write-Host "  安装依赖（可能需要几分钟，请耐心等待）..." -ForegroundColor Cyan
Write-Host ""

if (-not (Invoke-PipInstall -PipArgs @("-r", "requirements.txt") -Description "requirements.txt")) {
    Write-Host ""
    Write-Host "  ❌ 依赖安装失败（所有 pip 源均失败）" -ForegroundColor Red
    Write-Host "  请检查网络连接，或设置环境变量 DRAMA_PIP_INDEX_URL 指定可用的 pip 源" -ForegroundColor Yellow
    Pause-IfInteractive
    exit 1
}

Write-Host ""
Write-Host "  安装本地包（drama_processor）..." -ForegroundColor Cyan
if (Invoke-PipInstall -PipArgs @("-e", ".") -Description "drama_processor") {
    Write-Host ""
    Write-Host "  ✅ 依赖安装完成" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  ❌ 本地包安装失败" -ForegroundColor Red
    Pause-IfInteractive
    exit 1
}

# 5. 读取并创建素材目录
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  📁 准备素材目录" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# 从默认配置读取素材目录
$defaultConfigPath = "configs\default.yaml"
$sourcePath = "D:\短剧剪辑\源素材视频"  # 默认值
$outputPath = "D:\短剧剪辑\输出素材"    # 默认值
$tempPath = $null                      # 可选
$tailCachePath = $null                 # 可选

if (Test-Path $defaultConfigPath) {
    try {
        $configContent = Get-Content $defaultConfigPath -Raw -Encoding UTF8
        
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
    Write-Host "  ⚠️ 未找到 default.yaml，使用默认路径" -ForegroundColor Yellow
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

# 有未完成的必需步骤时返回非 0，让客户端提示安装失败
if ($script:FailedSteps.Count -gt 0) {
    Write-Host ""
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "  ⚠️ 安装未全部完成" -ForegroundColor Yellow
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "  Python 依赖已就绪，以下步骤需要处理：" -ForegroundColor Yellow
    foreach ($step in $script:FailedSteps) {
        Write-Host "  ❌ $step" -ForegroundColor Red
    }
    Write-Host ""
    Pause-IfInteractive
    exit 1
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
Write-Host "  2. 回到 Electron 客户端的“素材剪辑”页面" -ForegroundColor Cyan
Write-Host "     在客户端内继续配置并执行自动剪辑或手动剪辑" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. 剪辑完成后，素材会按日期存放：" -ForegroundColor Cyan
Write-Host "     $sourcePath\MM-DD\剧名\" -ForegroundColor White
Write-Host "     文件名格式：月-日-剧名-素材标识-集数.mp4" -ForegroundColor Gray
Write-Host "     （例如：$sourcePath\01-20\霸总的隐婚娇妻\1-20-霸总的隐婚娇妻-xl-01.mp4）" -ForegroundColor Gray
Write-Host ""
