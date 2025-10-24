# Windows 系统使用说明

## 🎯 概述

为 Windows 系统提供了两个版本的目录清理脚本：

1. **PowerShell 版本** (`keep-show.ps1`) - **推荐**
2. **批处理版本** (`keep-show.bat`) - 兼容性更好

## 📋 PowerShell 版本 (推荐)

### 基本用法

```powershell
# 预演模式（推荐先使用）
Get-Clipboard | .\keep-show.ps1 "D:\dramas"

# 实际执行清理
Get-Clipboard | .\keep-show.ps1 -Apply "D:\dramas"

# 移动到回收站而不是删除
Get-Clipboard | .\keep-show.ps1 -Apply -MoveTo "D:\_Recycle" "D:\dramas"

# 忽略大小写匹配
Get-Clipboard | .\keep-show.ps1 -CaseInsensitive "D:\dramas"
```

### 参数说明

| 参数               | 类型   | 说明                                    |
| ------------------ | ------ | --------------------------------------- |
| `SourcePath`       | 必需   | 源目录路径                              |
| `-Apply`           | 开关   | 真正执行删除/移动（不加此参数只是预演） |
| `-MoveTo`          | 字符串 | 移动到指定目录而不是直接删除            |
| `-CaseInsensitive` | 开关   | 忽略大小写匹配剧名                      |

## 📋 批处理版本 (兼容性)

### 基本用法

```cmd
REM 预演模式（推荐先使用）
keep-show.bat "D:\dramas"

REM 实际执行清理
keep-show.bat "D:\dramas" --apply

REM 移动到回收站而不是删除
keep-show.bat "D:\dramas" --apply --to "D:\_Recycle"

REM 忽略大小写匹配
keep-show.bat "D:\dramas" --case-insensitive
```

### 参数说明

| 参数                 | 说明                     |
| -------------------- | ------------------------ |
| `源目录路径`         | 必需，要清理的目录路径   |
| `--apply`            | 真正执行删除/移动        |
| `--to "目标路径"`    | 移动到指定目录而不是删除 |
| `--case-insensitive` | 忽略大小写匹配           |
| `--help`             | 显示帮助信息             |

## 🚀 使用步骤

### 1. 准备白名单

将需要保留的剧名复制到剪贴板，每行一个剧名：

```
一念春风起
测试短剧1
重要短剧2
```

### 2. 预演清理

```powershell
# PowerShell 版本
Get-Clipboard | .\keep-show.ps1 "D:\dramas"

# 批处理版本
keep-show.bat "D:\dramas"
```

### 3. 确认后执行

```powershell
# PowerShell 版本
Get-Clipboard | .\keep-show.ps1 -Apply "D:\dramas"

# 批处理版本
keep-show.bat "D:\dramas" --apply
```

## ⚠️ 安全建议

### 1. 先预演再执行

```powershell
# 第一步：预演查看会删除什么
Get-Clipboard | .\keep-show.ps1 "D:\dramas"

# 第二步：确认无误后执行
Get-Clipboard | .\keep-show.ps1 -Apply "D:\dramas"
```

### 2. 使用移动而不是删除

```powershell
# 移动到回收站而不是直接删除
Get-Clipboard | .\keep-show.ps1 -Apply -MoveTo "D:\_Recycle" "D:\dramas"
```

### 3. 备份重要数据

在执行清理前，建议备份重要的短剧目录。

## 🔧 故障排除

### PowerShell 执行策略问题

如果遇到 PowerShell 执行策略限制：

```powershell
# 临时允许执行脚本
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process

# 或者直接运行
PowerShell -ExecutionPolicy Bypass -File .\keep-show.ps1 "D:\dramas"
```

### 权限问题

如果遇到权限问题：

1. 以管理员身份运行 PowerShell 或命令提示符
2. 检查目录权限设置

### 路径包含空格

如果路径包含空格，使用引号包围：

```powershell
Get-Clipboard | .\keep-show.ps1 "D:\My Dramas"
```

## 📊 功能对比

| 功能       | PowerShell 版本 | 批处理版本 |
| ---------- | --------------- | ---------- |
| 执行速度   | 快              | 中等       |
| 功能完整性 | 完整            | 基础       |
| 错误处理   | 完善            | 基础       |
| 兼容性     | 需要 PowerShell | 通用       |
| 推荐度     | ⭐⭐⭐⭐⭐      | ⭐⭐⭐     |

## 🎯 推荐使用方式

**首选**：PowerShell 版本

```powershell
Get-Clipboard | .\keep-show.ps1 -Apply -MoveTo "D:\_Recycle" "D:\dramas"
```

**备选**：批处理版本

```cmd
keep-show.bat "D:\dramas" --apply --to "D:\_Recycle"
```

---

**注意**：两个脚本都支持相同的功能，但 PowerShell 版本功能更完善，错误处理更好，推荐使用。
