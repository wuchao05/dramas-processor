# 短剧剪辑工具 - 达人打包脚本
# 用途：将项目打包为可交付给达人的压缩包

param(
    [string]$Name = "达人",
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

# 检查配置文件是否存在
$userConfigFile = "configs\users\${Name}.yaml"
if (-not (Test-Path $userConfigFile)) {
    Write-Host "❌ 配置文件不存在: $userConfigFile" -ForegroundColor Red
    Write-Host "请检查 configs/users/ 目录下是否有 ${Name}.yaml 文件" -ForegroundColor Yellow
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

# 复制基础文件和目录
$basicItems = @("src", "assets", "docs", "requirements.txt", "requirements_ai.txt", "pyproject.toml", "README.md")
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
Copy-Item -Path "configs\windows_default.yaml" -Destination "${packagePath}\项目文件\configs\" -Force

# 只复制该达人的配置文件
$userConfigFile = "configs\users\${Name}.yaml"
$userDailyConfigFile = "configs\users\${Name}-daily.yaml"

Copy-Item -Path $userConfigFile -Destination "${packagePath}\项目文件\configs\users\" -Force
Write-Host "  ✓ 已复制达人配置: ${Name}.yaml" -ForegroundColor Green

if (Test-Path $userDailyConfigFile) {
    Copy-Item -Path $userDailyConfigFile -Destination "${packagePath}\项目文件\configs\users\" -Force
    Write-Host "  ✓ 已复制达人配置: ${Name}-daily.yaml" -ForegroundColor Green
}

# 修改 windows_default.yaml 的 active_user
$defaultConfigPath = "${packagePath}\项目文件\configs\windows_default.yaml"
$defaultConfig = Get-Content $defaultConfigPath -Raw -Encoding UTF8
$defaultConfig = $defaultConfig -replace "active_user:.*", "active_user: ${Name}"
$defaultConfig | Out-File -FilePath $defaultConfigPath -Encoding UTF8 -NoNewline
Write-Host "  ✓ 已设置 active_user: ${Name}" -ForegroundColor Green

# 复制和创建启动脚本
Write-Host "[3/6] 创建启动脚本..." -ForegroundColor Yellow

# 复制通用脚本
Copy-Item -Path "一键安装.ps1" -Destination $packagePath -Force
Copy-Item -Path "启动命令行.bat" -Destination $packagePath -Force
Copy-Item -Path "达人使用说明.txt" -Destination $packagePath -Force
Write-Host "  ✓ 已复制通用脚本" -ForegroundColor Green

# 创建达人专属的飞书监控启动脚本
$feishuBatContent = @"
@echo off
chcp 65001 >nul
title 短剧剪辑工具 - 飞书自动监控（${Name}）

echo ========================================
echo    短剧剪辑工具 - 飞书自动监控
echo    账号：${Name}
echo ========================================
echo.

cd /d %~dp0\项目文件
call ..\venv\Scripts\activate.bat

echo [√] 虚拟环境已激活
echo [√] 正在启动飞书监控...
echo.
echo 提示：
echo - 按 Ctrl+C 可以安全停止
echo - 窗口会显示实时处理进度
echo.

python -m drama_processor feishu watch --config configs\users\${Name}.yaml

echo.
echo ========================================
echo    监控已停止
echo ========================================
pause
"@

$feishuBatPath = Join-Path $packagePath "启动飞书监控.bat"
$feishuBatContent | Out-File -FilePath $feishuBatPath -Encoding UTF8
Write-Host "  ✓ 已创建: 启动飞书监控.bat（配置: ${Name}.yaml）" -ForegroundColor Green

# 创建达人专属说明文件
Write-Host "[4/6] 生成达人专属说明..." -ForegroundColor Yellow
$readmeContent = @"
═══════════════════════════════════════════════════════════
          🎬 短剧剪辑工具 - 欢迎使用！
═══════════════════════════════════════════════════════════

📦 打包日期：$(Get-Date -Format "yyyy年MM月dd日 HH:mm")
👤 使用者：${Name}

📁 文件说明
───────────────────────────────────────────────────────────
[根目录]
  📄 达人使用说明.txt      - 【必读】快速开始指南
  📄 一键安装.ps1          - 首次使用需要运行
  📄 启动命令行.bat        - 打开命令行界面
  📄 启动飞书监控.bat      - 一键启动飞书自动监控

[项目文件]
  📁 src/                  - 程序源代码
  📁 configs/              - 配置文件
  📁 assets/               - 资源文件（尾部视频、水印等）
  📁 docs/                 - 详细文档

🚀 快速开始（3步）
───────────────────────────────────────────────────────────
1️⃣ 首次安装
   右键点击"一键安装.ps1" → 选择"使用 PowerShell 运行"
   等待安装完成（约5-10分钟）

2️⃣ 准备素材
   确保源素材放在：D:\短剧剪辑\源素材视频\
   （每部剧一个文件夹，文件夹名即剧名）

3️⃣ 开始使用
   双击运行"启动飞书监控.bat"即可自动监控和剪辑

📖 详细文档
───────────────────────────────────────────────────────────
• 快速上手：docs/达人快速上手指南.md
• 完整教程：docs/WINDOWS_使用教程.md
• 文档导航：docs/WINDOWS_文档导航.md

⚠️ 重要提示
───────────────────────────────────────────────────────────
1. 首次使用必须先运行"一键安装.ps1"安装环境
2. 确保电脑已连接网络（安装时需要下载依赖）
3. 建议使用 SSD 存储源素材和输出文件
4. 如遇问题，查看"达人使用说明.txt"中的常见问题

📞 技术支持
───────────────────────────────────────────────────────────
如有问题，请联系管理员，并提供：
  • 错误信息截图
  • 使用的配置文件名称（${Name}.yaml）
  • 操作步骤说明

═══════════════════════════════════════════════════════════
          祝创作愉快！🎬✨
═══════════════════════════════════════════════════════════
"@

$readmeContent | Out-File -FilePath "${packagePath}\README.txt" -Encoding UTF8

# 创建配置检查清单
Write-Host "[5/6] 生成配置检查清单..." -ForegroundColor Yellow
$checklistContent = @"
短剧剪辑工具 - 配置检查清单 (Checklist)
═══════════════════════════════════════════════════════════

✅ 使用前检查
───────────────────────────────────────────────────────────
□ 已运行"一键安装.ps1"完成环境安装
□ 已准备好源素材目录（D:\短剧剪辑\源素材视频\）
□ 电脑已连接网络
□ 有足够的磁盘空间（每部剧约5-10GB）

✅ 配置文件检查
───────────────────────────────────────────────────────────
□ 配置文件位置：项目文件\configs\users\${Name}.yaml
□ 飞书 API 凭证已配置（app_id, app_secret, app_token, table_id）
□ 源素材目录路径正确（default_source_dir）
□ 素材数量设置正确（count 参数）

✅ 飞书表格检查（如使用飞书自动化）
───────────────────────────────────────────────────────────
□ 表格包含必需字段：剧名、日期、当前状态
□ 表格中有"待剪辑"状态的剧集
□ 日期格式正确（如：1.16）
□ 剧名与源素材文件夹名称一致

✅ 测试运行
───────────────────────────────────────────────────────────
1. 打开 PowerShell，运行：
   python --version
   ffmpeg -version
   
2. 如果都有输出，表示环境安装成功

3. 测试命令：
   python -m drama_processor --help
   
4. 如果显示帮助信息，表示程序运行正常

✅ 首次剪辑建议
───────────────────────────────────────────────────────────
□ 先用单部剧测试（不要用飞书自动化）
□ 观察输出素材质量
□ 确认品牌文案显示正确
□ 检查素材时长是否合适

✅ 故障排除
───────────────────────────────────────────────────────────
如遇问题，请按以下顺序检查：
1. 查看"达人使用说明.txt"中的常见问题
2. 查看 docs/达人快速上手指南.md
3. 联系管理员（提供错误截图）

═══════════════════════════════════════════════════════════
打包日期：$(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
═══════════════════════════════════════════════════════════
"@

$checklistContent | Out-File -FilePath "${packagePath}\Checklist.txt" -Encoding UTF8

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
Write-Host "   3. 指导达人查看 README.txt" -ForegroundColor White
Write-Host "   4. 指导达人运行'一键安装.ps1'" -ForegroundColor White
Write-Host ""

# 打开输出目录
Start-Process explorer.exe -ArgumentList $OutputDir
