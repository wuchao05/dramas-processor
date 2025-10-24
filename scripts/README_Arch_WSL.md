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
pbpaste | ./keep-show.sh "/mnt/c/dramas"
```

### 3. 执行清理

```bash
pbpaste | ./keep-show.sh --apply "/mnt/c/dramas"
```

## 📋 常用命令

### 基础操作

```bash
# 预演模式（推荐先使用）
pbpaste | ./keep-show.sh "/mnt/c/dramas"

# 实际执行
pbpaste | ./keep-show.sh --apply "/mnt/c/dramas"

# 移动到回收站（更安全）
pbpaste | ./keep-show.sh --apply --to "/mnt/c/_Recycle" "/mnt/c/dramas"
```

### 高级选项

```bash
# 忽略大小写
pbpaste | ./keep-show.sh --case-insensitive "/mnt/c/dramas"

# WSL 优化模式
pbpaste | ./keep-show.sh --wsl "/mnt/c/dramas"

# 组合使用
pbpaste | ./keep-show.sh --apply --case-insensitive --wsl "/mnt/c/dramas"
```

## 🎯 路径映射

| Windows 路径 | Arch WSL 路径   |
| ------------ | --------------- |
| `C:\dramas`  | `/mnt/c/dramas` |
| `D:\dramas`  | `/mnt/d/dramas` |
| `E:\dramas`  | `/mnt/e/dramas` |

## 🔧 故障排除

### 剪贴板问题

```bash
# 安装 xclip
sudo pacman -S xclip

# 或者安装 xsel
sudo pacman -S xsel

# 使用管道输入（无需剪贴板）
echo "剧名1
剧名2
剧名3" | ./keep-show.sh "/mnt/c/dramas"
```

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
pbpaste | ./keep-show.sh "/mnt/c/dramas"

# 2. 安全执行（移动到回收站）
pbpaste | ./keep-show.sh --apply --to "/mnt/c/_Recycle" "/mnt/c/dramas"

# 3. 确认无误后删除回收站内容
rm -rf "/mnt/c/_Recycle"/*
```

### 批量处理多个目录

```bash
# 处理多个驱动器
pbpaste | ./keep-show.sh --apply "/mnt/c/dramas"
pbpaste | ./keep-show.sh --apply "/mnt/d/dramas"
pbpaste | ./keep-show.sh --apply "/mnt/e/dramas"
```

---

**提示**：Arch Linux WSL 用户享受最快的包管理体验，`pacman` 命令让依赖安装变得非常简单！
