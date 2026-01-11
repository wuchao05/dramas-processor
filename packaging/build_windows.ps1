# Windows 打包脚本
param(
    [string]$Version = "1.0.0"
)

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "  Drama Processor Windows 打包" -ForegroundColor Green
Write-Host "  版本: $Version" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ""

# 检查 FFmpeg
Write-Host "[Step 0/5] 检查 FFmpeg..." -ForegroundColor Yellow
if (-not (Test-Path "bin\ffmpeg.exe")) {
    Write-Host "❌ 错误: 未找到 bin\ffmpeg.exe" -ForegroundColor Red
    Write-Host ""
    Write-Host "请先下载 FFmpeg 并放置在 bin 目录:" -ForegroundColor Yellow
    Write-Host "  1. 访问: https://www.gyan.dev/ffmpeg/builds/" -ForegroundColor Cyan
    Write-Host "  2. 下载: ffmpeg-release-essentials.zip" -ForegroundColor Cyan
    Write-Host "  3. 解压后将 ffmpeg.exe 和 ffprobe.exe 复制到 bin/ 目录" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

if (-not (Test-Path "bin\ffprobe.exe")) {
    Write-Host "❌ 错误: 未找到 bin\ffprobe.exe" -ForegroundColor Red
    Write-Host "请将 ffprobe.exe 也复制到 bin/ 目录" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ FFmpeg 检查通过" -ForegroundColor Green

# 检查 Python 和 PyInstaller
Write-Host ""
Write-Host "[Step 1/5] 检查环境..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  Python: $pythonVersion" -ForegroundColor Cyan
} catch {
    Write-Host "❌ 错误: 未找到 Python" -ForegroundColor Red
    exit 1
}

try {
    $null = pyinstaller --version 2>&1
    Write-Host "  PyInstaller: 已安装" -ForegroundColor Cyan
} catch {
    Write-Host "❌ 错误: 未找到 PyInstaller" -ForegroundColor Red
    Write-Host "请运行: pip install pyinstaller" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ 环境检查通过" -ForegroundColor Green

# 清理旧文件
Write-Host ""
Write-Host "[Step 2/5] 清理旧文件..." -ForegroundColor Yellow
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
Write-Host "✅ 清理完成" -ForegroundColor Green

# 打包
Write-Host ""
Write-Host "[Step 3/5] 开始打包（这可能需要几分钟）..." -ForegroundColor Yellow
$startTime = Get-Date
pyinstaller packaging\pyinstaller_gui_onefile.spec
$endTime = Get-Date
$duration = ($endTime - $startTime).TotalSeconds

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ 打包失败！" -ForegroundColor Red
    exit 1
}

Write-Host "✅ 打包完成（用时 $([math]::Round($duration, 1)) 秒）" -ForegroundColor Green

# 验证
Write-Host ""
Write-Host "[Step 4/5] 验证打包..." -ForegroundColor Yellow
if (Test-Path "dist\dramas-processor-gui.exe") {
    $size = (Get-Item "dist\dramas-processor-gui.exe").Length / 1MB
    Write-Host "  文件: dist\dramas-processor-gui.exe" -ForegroundColor Cyan
    Write-Host "  大小: $([math]::Round($size, 2)) MB" -ForegroundColor Cyan
    Write-Host "✅ 打包成功！" -ForegroundColor Green
} else {
    Write-Host "❌ 未找到输出文件" -ForegroundColor Red
    exit 1
}

# 创建发布包
Write-Host ""
Write-Host "[Step 5/5] 创建发布包..." -ForegroundColor Yellow
$releaseDir = "release_windows_v$Version"
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null

Copy-Item "dist\dramas-processor-gui.exe" "$releaseDir\"
Copy-Item -Recurse "assets" "$releaseDir\" -ErrorAction SilentlyContinue
Copy-Item -Recurse "configs" "$releaseDir\" -ErrorAction SilentlyContinue
Copy-Item "README.md" "$releaseDir\" -ErrorAction SilentlyContinue

# 创建快速开始文档
$quickStartContent = @"
# Drama Processor Windows 版本 - 快速开始

## 运行程序

双击运行: dramas-processor-gui.exe

## 首次使用

1. 修改配置文件 configs\windows_default.yaml
   - 设置源视频目录路径
   - 调整其他参数

2. 启动程序后在 GUI 界面进行配置

## 注意事项

- 已内置 FFmpeg，无需额外安装
- 首次运行可能需要几秒钟启动
- 杀毒软件可能会误报，请添加信任

## 技术支持

- 文档: README.md
- 问题反馈: [项目地址]

版本: $Version
打包时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
"@

$quickStartContent | Out-File -FilePath "$releaseDir\快速开始.txt" -Encoding UTF8

Write-Host "✅ 发布包创建完成" -ForegroundColor Green

# 总结
Write-Host ""
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "  打包完成！" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "发布包位置: $releaseDir" -ForegroundColor Cyan
Write-Host "可执行文件: $releaseDir\dramas-processor-gui.exe" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步:" -ForegroundColor Yellow
Write-Host "  1. 测试运行: .\$releaseDir\dramas-processor-gui.exe" -ForegroundColor White
Write-Host "  2. 打包压缩: Compress-Archive -Path $releaseDir -DestinationPath drama-processor-v$Version.zip" -ForegroundColor White
Write-Host ""
