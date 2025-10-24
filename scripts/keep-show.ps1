# 保留白名单中的顶层目录（每个剧=一个顶层目录），其余清理/移动
# 用法：
#   Get-Clipboard | .\keep-show.ps1 "D:\dramas"                    # 预演（不删除）
#   Get-Clipboard | .\keep-show.ps1 -Apply "D:\dramas"             # 真删/真移动
#   可选： -MoveTo "D:\_Recycle"                                   # 不直接删，先移到回收目录
#         -CaseInsensitive                                         # 名称忽略大小写

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$SourcePath,
    
    [switch]$Apply,
    [string]$MoveTo = "",
    [switch]$CaseInsensitive
)

# 错误处理
$ErrorActionPreference = "Stop"

# 验证源目录
if (-not (Test-Path $SourcePath -PathType Container)) {
    Write-Error "源目录不存在：$SourcePath"
    exit 1
}

# 验证移动目标目录
if ($MoveTo -and -not (Test-Path $MoveTo -PathType Container)) {
    try {
        New-Item -ItemType Directory -Path $MoveTo -Force | Out-Null
    } catch {
        Write-Error "无法创建移动目标目录：$MoveTo"
        exit 1
    }
}

# 读取白名单（来自管道或剪贴板）
$whitelist = @()
if ($input) {
    # 从管道读取
    $whitelist = $input | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
} else {
    # 从剪贴板读取
    try {
        $clipboard = Get-Clipboard -Raw
        $whitelist = $clipboard -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
    } catch {
        Write-Error "无法读取剪贴板内容"
        exit 1
    }
}

if ($whitelist.Count -eq 0) {
    Write-Error "白名单为空"
    exit 1
}

# 处理大小写
if ($CaseInsensitive) {
    $whitelist = $whitelist | ForEach-Object { $_.ToLower() }
}

# 去重并排序
$whitelist = $whitelist | Sort-Object -Unique

Write-Host "======= 白名单（共 $($whitelist.Count) 条）示例 =======" -ForegroundColor Cyan
$whitelist | Select-Object -First 10 | ForEach-Object { Write-Host $_ }
if ($whitelist.Count -gt 10) {
    Write-Host "(仅展示前 10 条...)"
}
Write-Host "=============================================" -ForegroundColor Cyan

# 扫描源目录下的顶层目录
Write-Host "[INFO] 正在扫描顶层目录：$SourcePath ..." -ForegroundColor Yellow
$allDirs = Get-ChildItem -Path $SourcePath -Directory | ForEach-Object { $_.FullName }
$totalDirs = $allDirs.Count
Write-Host "[INFO] 顶层目录数量：$totalDirs" -ForegroundColor Yellow

# 构建可用目录名列表
$availableDirs = @()
foreach ($dir in $allDirs) {
    $name = Split-Path $dir -Leaf
    if ($CaseInsensitive) {
        $name = $name.ToLower()
    }
    $availableDirs += $name
}
$availableDirs = $availableDirs | Sort-Object -Unique

# 计算白名单中但盘上不存在的剧
$missingShows = @()
foreach ($show in $whitelist) {
    if ($show -notin $availableDirs) {
        $missingShows += $show
    }
}

if ($missingShows.Count -gt 0) {
    Write-Host ""
    Write-Host "⚠️  以下白名单剧目在磁盘中【未找到】（共 $($missingShows.Count) 条，展示前 20 条）：" -ForegroundColor Red
    $missingShows | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }
    if ($missingShows.Count -gt 20) {
        Write-Host "(其余 $($missingShows.Count - 20) 条已省略)"
    }
}

# 根据白名单判定保留/清理
$toKeep = @()
$toDelete = @()

foreach ($dir in $allDirs) {
    $baseName = Split-Path $dir -Leaf
    $key = $baseName
    if ($CaseInsensitive) {
        $key = $key.ToLower()
    }
    
    if ($key -in $whitelist) {
        $toKeep += $dir
    } else {
        $toDelete += $dir
    }
}

Write-Host ""
Write-Host "[SUMMARY] 将保留目录数：$($toKeep.Count)" -ForegroundColor Green
Write-Host "[SUMMARY] 将清理目录数：$($toDelete.Count)" -ForegroundColor Red

if (-not $Apply) {
    Write-Host ""
    Write-Host "【Dry-run 预演】以下目录将被清理（不执行删除/移动）：" -ForegroundColor Yellow
    foreach ($dir in $toDelete) {
        Write-Host "  - $dir" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "要真正执行，请加：-Apply" -ForegroundColor Yellow
    if ($MoveTo) {
        Write-Host "当前设置为移动到：$MoveTo" -ForegroundColor Yellow
    }
    exit 0
}

Write-Host ""
Write-Host "【执行中】开始处理未在白名单中的目录..." -ForegroundColor Yellow

foreach ($dir in $toDelete) {
    if ($MoveTo) {
        $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $dest = Join-Path $MoveTo "$(Split-Path $dir -Leaf)__$timestamp"
        Write-Host "  移动：$dir -> $dest" -ForegroundColor Yellow
        Move-Item -Path $dir -Destination $dest
    } else {
        Write-Host "  删除：$dir" -ForegroundColor Red
        Remove-Item -Path $dir -Recurse -Force
    }
}

Write-Host "完成 ✅" -ForegroundColor Green
