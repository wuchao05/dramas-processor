# WSL 环境使用说明

## 🎯 概述

`keep-show.sh` 脚本已优化支持 WSL (Windows Subsystem for Linux) 环境，可以无缝在 Windows 的 WSL 中运行。

**特别支持**：Arch Linux WSL、Ubuntu WSL、Debian WSL 等主流发行版。

## 🚀 快速开始

### 🎯 Arch Linux WSL 用户（推荐）

如果你是 Arch Linux WSL 用户，这是最快的开始方式：

```bash
# 1. 安装剪贴板工具
sudo pacman -S xclip

# 2. 预演清理（安全模式）
pbpaste | ./keep-show.sh "/mnt/c/dramas"

# 3. 实际执行清理
pbpaste | ./keep-show.sh --apply "/mnt/c/dramas"
```

## 📋 详细安装步骤

### 1. 安装剪贴板工具（推荐）

#### Arch Linux WSL

```bash
# 安装 xclip（推荐）
sudo pacman -S xclip

# 或者安装 xsel
sudo pacman -S xsel
```

#### Ubuntu/Debian WSL

```bash
# 安装 xclip（推荐）
sudo apt-get update
sudo apt-get install xclip

# 或者安装 xsel
sudo apt-get install xsel
```

### 2. 基本使用

```bash
# 预演模式（推荐先使用）
pbpaste | ./keep-show.sh "/mnt/c/dramas"

# 实际执行清理
pbpaste | ./keep-show.sh --apply "/mnt/c/dramas"

# WSL 优化模式
pbpaste | ./keep-show.sh --wsl "/mnt/c/dramas"
```

## 📋 参数说明

| 参数                 | 说明                                    |
| -------------------- | --------------------------------------- |
| `源目录路径`         | 必需，要清理的目录路径                  |
| `--apply`            | 真正执行删除/移动（不加此参数只是预演） |
| `--to "目标路径"`    | 移动到指定目录而不是删除                |
| `--case-insensitive` | 忽略大小写匹配剧名                      |
| `--wsl`              | WSL 环境优化模式                        |

## 🎯 WSL 路径映射

### Windows 路径 → WSL 路径

| Windows 路径 | WSL 路径        |
| ------------ | --------------- |
| `C:\dramas`  | `/mnt/c/dramas` |
| `D:\dramas`  | `/mnt/d/dramas` |
| `E:\dramas`  | `/mnt/e/dramas` |

### 使用示例

```bash
# Windows 路径：C:\dramas
./keep-show.sh "/mnt/c/dramas"

# Windows 路径：D:\My Dramas
./keep-show.sh "/mnt/d/My Dramas"

# Windows 路径：E:\短剧库
./keep-show.sh "/mnt/e/短剧库"
```

## 🔧 剪贴板支持

### 自动检测模式

脚本会自动检测可用的剪贴板工具：

1. **xclip** (推荐)
2. **xsel**
3. **Windows PowerShell** (WSL 模式)
4. **pbpaste** (macOS)

### 手动安装剪贴板工具

```bash
# 方法1：安装 xclip
sudo apt-get install xclip

# 方法2：安装 xsel
sudo apt-get install xsel

# 方法3：使用 Windows PowerShell（无需安装）
./keep-show.sh --wsl "/mnt/c/dramas"
```

## 🚀 使用步骤

### 1. 准备白名单

在 Windows 中复制要保留的剧名到剪贴板：

```
一念春风起
测试短剧1
重要短剧2
```

### 2. 预演清理

```bash
# 在 WSL 中运行
pbpaste | ./keep-show.sh "/mnt/c/dramas"
```

### 3. 确认后执行

```bash
# 实际执行清理
pbpaste | ./keep-show.sh --apply "/mnt/c/dramas"

# 安全模式（移动到回收站）
pbpaste | ./keep-show.sh --apply --to "/mnt/c/_Recycle" "/mnt/c/dramas"
```

## ⚠️ 安全建议

### 1. 先预演再执行

```bash
# 第一步：预演查看会删除什么
pbpaste | ./keep-show.sh "/mnt/c/dramas"

# 第二步：确认无误后执行
pbpaste | ./keep-show.sh --apply "/mnt/c/dramas"
```

### 2. 使用移动而不是删除

```bash
# 移动到回收站而不是直接删除
pbpaste | ./keep-show.sh --apply --to "/mnt/c/_Recycle" "/mnt/c/dramas"
```

### 3. 备份重要数据

在执行清理前，建议备份重要的短剧目录。

## 🔧 故障排除

### 剪贴板问题

如果遇到剪贴板问题：

#### Arch Linux WSL

```bash
# 方法1：安装 xclip
sudo pacman -S xclip

# 方法2：安装 xsel
sudo pacman -S xsel
```

#### Ubuntu/Debian WSL

```bash
# 方法1：安装 xclip
sudo apt-get install xclip

# 方法2：安装 xsel
sudo apt-get install xsel
```

#### 通用解决方案

```bash
# 方法3：使用管道输入
echo "剧名1
剧名2
剧名3" | ./keep-show.sh "/mnt/c/dramas"

# 方法4：使用 WSL 模式
./keep-show.sh --wsl "/mnt/c/dramas"
```

### 权限问题

如果遇到权限问题：

```bash
# 检查目录权限
ls -la "/mnt/c/dramas"

# 修改权限（如果需要）
sudo chmod 755 "/mnt/c/dramas"
```

### 路径问题

如果路径包含空格或特殊字符：

```bash
# 使用引号包围路径
./keep-show.sh "/mnt/c/My Dramas"

# 使用转义字符
./keep-show.sh /mnt/c/My\ Dramas
```

## 🎯 推荐使用方式

### 标准流程

#### Arch Linux WSL

```bash
# 1. 安装剪贴板工具
sudo pacman -S xclip

# 2. 预演清理
pbpaste | ./keep-show.sh "/mnt/c/dramas"

# 3. 安全执行
pbpaste | ./keep-show.sh --apply --to "/mnt/c/_Recycle" "/mnt/c/dramas"
```

#### Ubuntu/Debian WSL

```bash
# 1. 安装剪贴板工具
sudo apt-get install xclip

# 2. 预演清理
pbpaste | ./keep-show.sh "/mnt/c/dramas"

# 3. 安全执行
pbpaste | ./keep-show.sh --apply --to "/mnt/c/_Recycle" "/mnt/c/dramas"
```

### 高级用法

```bash
# 忽略大小写匹配
pbpaste | ./keep-show.sh --case-insensitive "/mnt/c/dramas"

# WSL 优化模式
pbpaste | ./keep-show.sh --wsl "/mnt/c/dramas"

# 组合使用
pbpaste | ./keep-show.sh --apply --case-insensitive --wsl "/mnt/c/dramas"
```

## 📊 环境兼容性

| 环境       | 支持状态    | 剪贴板工具 | 推荐度     |
| ---------- | ----------- | ---------- | ---------- |
| Arch WSL1  | ✅ 完全支持 | xclip/xsel | ⭐⭐⭐⭐⭐ |
| Arch WSL2  | ✅ 完全支持 | xclip/xsel | ⭐⭐⭐⭐⭐ |
| Ubuntu WSL | ✅ 完全支持 | xclip/xsel | ⭐⭐⭐⭐⭐ |
| Debian WSL | ✅ 完全支持 | xclip/xsel | ⭐⭐⭐⭐⭐ |
| macOS      | ✅ 完全支持 | pbpaste    | ⭐⭐⭐⭐⭐ |

---

**注意**：WSL 环境下的路径需要使用 `/mnt/` 前缀来访问 Windows 驱动器。
