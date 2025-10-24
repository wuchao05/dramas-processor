# Arch Linux WSL 快速指南

## 🎯 专为 Arch Linux WSL 用户优化

这个指南专门为使用 Arch Linux WSL 的用户设计，提供最简洁的使用方式。

## 🚀 30 秒快速开始

### 1. 安装依赖

```bash
sudo pacman -S xclip
```

### 2. 预演清理

```bash
# 方法1：使用 WSL 专用脚本（推荐）
./keep-show-wsl.sh "/mnt/c/dramas"

# 方法2：直接使用主脚本
./keep-show.sh "/mnt/c/dramas"
```

### 3. 执行清理

```bash
# 方法1：使用 WSL 专用脚本（推荐）
./keep-show-wsl.sh --apply "/mnt/c/dramas"

# 方法2：直接使用主脚本
./keep-show.sh --apply "/mnt/c/dramas"
```

## 📋 常用命令

### 基础操作

```bash
# 预演模式（推荐先使用）
./keep-show-wsl.sh "/mnt/c/dramas"

# 实际执行
./keep-show-wsl.sh --apply "/mnt/c/dramas"

# 移动到回收站（更安全）
./keep-show-wsl.sh --apply --to "/mnt/c/_Recycle" "/mnt/c/dramas"
```

### 高级选项

```bash
# 忽略大小写
./keep-show-wsl.sh --case-insensitive "/mnt/c/dramas"

# WSL 优化模式
./keep-show-wsl.sh --wsl "/mnt/c/dramas"

# 组合使用
./keep-show-wsl.sh --apply --case-insensitive --wsl "/mnt/c/dramas"
```

## 🎯 路径映射

| Windows 路径 | Arch WSL 路径   |
| ------------ | --------------- |
| `C:\dramas`  | `/mnt/c/dramas` |
| `D:\dramas`  | `/mnt/d/dramas` |
| `E:\dramas`  | `/mnt/e/dramas` |

## 🔧 故障排除

### 剪贴板问题

#### 错误：`pbpaste: command not found`

这是因为 WSL 环境中没有 `pbpaste` 命令。解决方案：

```bash
# 方法1：安装 xclip（推荐）
sudo pacman -S xclip

# 方法2：安装 xsel
sudo pacman -S xsel

# 方法3：使用 WSL 专用脚本（自动处理剪贴板）
./keep-show-wsl.sh "/mnt/c/dramas"

# 方法4：使用管道输入（无需剪贴板）
echo "剧名1
剧名2
剧名3" | ./keep-show.sh "/mnt/c/dramas"
```

#### 错误：`WL_AVAIL: unbound variable`

这是脚本内部错误，已修复。如果仍有问题，请使用最新版本的脚本。

### 权限问题

```bash
# 检查权限
ls -la "/mnt/c/dramas"

# 修改权限（如果需要）
sudo chmod 755 "/mnt/c/dramas"
```

## ⚠️ 安全建议

1. **先预演再执行**：总是先运行不带 `--apply` 的命令
2. **使用移动模式**：用 `--to` 参数移动到回收站而不是直接删除
3. **备份重要数据**：重要数据先备份

## 🎯 最佳实践

### 标准工作流

```bash
# 1. 预演查看会删除什么
./keep-show-wsl.sh "/mnt/c/dramas"

# 2. 安全执行（移动到回收站）
./keep-show-wsl.sh --apply --to "/mnt/c/_Recycle" "/mnt/c/dramas"

# 3. 确认无误后删除回收站内容
rm -rf "/mnt/c/_Recycle"/*
```

### 批量处理多个目录

```bash
# 处理多个驱动器
./keep-show-wsl.sh --apply "/mnt/c/dramas"
./keep-show-wsl.sh --apply "/mnt/d/dramas"
./keep-show-wsl.sh --apply "/mnt/e/dramas"
```

---

**提示**：Arch Linux WSL 用户享受最快的包管理体验，`pacman` 命令让依赖安装变得非常简单！
