# Windows 原生快速开始指南

## 概述

Drama Processor 现已支持 Windows 原生运行，无需 WSL！本指南将帮助你快速在 Windows 环境下开始使用。

## 系统要求

- Windows 10/11 (64位)
- Python 3.8+ (仅开发环境需要)
- 至少 4GB 可用内存
- 10GB 可用磁盘空间（用于临时文件和输出）

## 快速开始（exe 版本）

### 1. 下载发布包

下载 `drama-processor-windows-vX.X.X.zip` 并解压到任意目录。

### 2. 配置

编辑 `configs\windows_default.yaml`：

```yaml
# 修改为你的实际路径
default_source_dir: "E:\\短剧剪辑\\源素材视频"
backup_source_dir: "E:\\短剧剪辑\\源素材视频"
```

### 3. 运行

双击 `dramas-processor-gui.exe` 启动程序。

## 开发环境安装

### 1. 安装 Python

访问 [python.org](https://www.python.org/) 下载并安装 Python 3.8+。

安装时勾选 "Add Python to PATH"。

### 2. 克隆项目

```powershell
git clone <repository-url>
cd dramas_processor
```

### 3. 下载 FFmpeg

1. 访问 https://www.gyan.dev/ffmpeg/builds/
2. 下载 `ffmpeg-release-essentials.zip`
3. 解压后，将 `bin` 目录下的 `ffmpeg.exe` 和 `ffprobe.exe` 复制到项目的 `bin/` 目录

### 4. 安装依赖

```powershell
# 创建虚拟环境（推荐）
python -m venv venv
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 安装项目（开发模式）
pip install -e .
```

### 5. 测试环境

```powershell
python scripts\test_windows.py
```

应该看到所有测试通过。

### 6. 配置

复制并修改配置文件：

```powershell
# 使用 Windows 专用配置
drama-processor -c configs\windows_default.yaml --help
```

编辑 `configs\windows_default.yaml`，设置你的源视频目录等参数。

## 使用方法

### CLI 命令行

```powershell
# 查看帮助
drama-processor --help

# 处理单个剧目
drama-processor -c configs\windows_default.yaml process E:\短剧库 --count 5

# 使用飞书集成
drama-processor -c configs\windows_default.yaml feishu run --date 12.25
```

### GUI 图形界面

```powershell
# 启动 GUI
python run_gui.py
```

或直接运行 exe 版本（如果已打包）。

## 目录结构

```
dramas_processor/
├── bin/                    # FFmpeg 可执行文件
│   ├── ffmpeg.exe
│   └── ffprobe.exe
├── configs/                # 配置文件
│   ├── windows_default.yaml
│   └── users/
├── assets/                 # 资源文件
│   ├── tail.mp4
│   └── watermark-xiaohong.png
├── scripts/                # 工具脚本
│   ├── test_windows.py     # 环境测试
│   └── ...
├── packaging/              # 打包配置
│   └── build_windows.ps1
└── docs/                   # 文档
    └── WINDOWS_QUICKSTART.md
```

## 配置说明

### 关键配置项

在 `configs\windows_default.yaml` 中：

```yaml
# 源视频目录（修改为你的实际路径）
default_source_dir: "E:\\短剧剪辑\\源素材视频"

# 临时目录（null 则自动使用系统临时目录）
temp_dir: null

# 输出目录
output_dir: "..\\导出素材"

# 字体（null 则自动检测 Windows 字体）
font_file: null

# 视频编码设置
video:
  hw_codec: "auto"          # 自动检测硬件编码器
  bitrate: "6500k"
```

### 用户配置

在 `configs\users\` 目录下可以创建自己的配置文件：

```powershell
# 复制模板
copy configs\windows_default.yaml configs\users\my_config.yaml

# 使用自定义配置
drama-processor -c configs\users\my_config.yaml process E:\短剧库
```

## 常见问题

### Q: 提示找不到 FFmpeg？

**A**: 确保 `bin\ffmpeg.exe` 和 `bin\ffprobe.exe` 存在。运行测试脚本验证：

```powershell
python scripts\test_windows.py
```

### Q: 字体显示异常？

**A**: Windows 会自动检测系统字体（微软雅黑等）。如果有问题，可以在配置中指定：

```yaml
font_file: "C:\\Windows\\Fonts\\msyh.ttc"
```

### Q: 硬件编码器不可用？

**A**: 检查显卡驱动是否最新，或切换到软件编码：

```yaml
use_hardware: false
```

### Q: 临时文件占用过多磁盘？

**A**: 配置专门的临时目录：

```yaml
temp_dir: "D:\\Temp\\drama_processor"
```

### Q: 杀毒软件误报？

**A**: 将程序目录添加到杀毒软件的白名单。这是 PyInstaller 打包程序的常见现象。

### Q: 启动很慢？

**A**: 
- exe 版本首次启动需要解压文件，大约 5-10 秒
- 后续启动会快很多
- 开发环境启动更快

### Q: 如何打包自己的 exe？

**A**: 

```powershell
# 运行打包脚本
.\packaging\build_windows.ps1 -Version "1.0.0"

# 输出在 release_windows_v1.0.0/ 目录
```

## 性能优化

### 硬件编码器

Windows 原生环境下，NVENC (NVIDIA) 和 QSV (Intel) 编码器性能更好：

```yaml
video:
  hw_codec: "h264_nvenc"    # NVIDIA GPU
  # 或
  hw_codec: "h264_qsv"      # Intel CPU/GPU
```

### 并发处理

```yaml
jobs: 2  # 并发处理 2 个视频（根据 CPU 核心数调整）
```

### 滤镜线程

```yaml
filter_threads: 4  # 滤镜处理线程数
```

## 进阶功能

### 飞书集成

1. 在配置中填写飞书 API 信息：

```yaml
enable_feishu_features: true
feishu:
  app_id: "your_app_id"
  app_secret: "your_app_secret"
  app_token: "your_app_token"
  table_id: "your_table_id"
```

2. 运行飞书命令：

```powershell
# 手动运行
drama-processor feishu run --date 12.25

# 自动监听
drama-processor feishu watch
```

### 日期去重

避免重复处理相同日期的剧集：

```yaml
date_deduplication:
  enabled: true
```

### 批量处理

```powershell
# 处理多个剧集
drama-processor process E:\短剧库 --full --count 10
```

## 故障排除

### 查看日志

```powershell
# 开启详细日志
drama-processor -c configs\windows_default.yaml process E:\短剧库 --verbose
```

### 检查硬件编码器

```powershell
python scripts\check_encoders.py
```

### 清理临时文件

```powershell
# 查看临时目录
echo %TEMP%

# 手动清理
Remove-Item -Recurse -Force $env:TEMP\drama_processor
```

## 更新日志

### v1.0.0 (Windows 原生版本)

- ✅ 移除 WSL 依赖
- ✅ 自动检测 Windows 字体
- ✅ 内置 FFmpeg
- ✅ 改进临时文件管理
- ✅ 优化硬件编码器支持
- ✅ 提供独立 exe 版本

## 获取帮助

- 📖 完整文档: [README.md](../README.md)
- 🔧 改造指南: [WINDOWS_NATIVE_MIGRATION.md](WINDOWS_NATIVE_MIGRATION.md)
- 📝 命令使用: [COMMANDS_USAGE_GUIDE.md](../COMMANDS_USAGE_GUIDE.md)
- ⚙️ 硬件编码器故障排查: [HARDWARE_ENCODER_TROUBLESHOOTING.md](HARDWARE_ENCODER_TROUBLESHOOTING.md)

## 下一步

恭喜！你已经完成了 Windows 环境的配置。

现在可以：

1. 🎬 开始处理你的第一个短剧
2. 🔧 根据需要调整配置参数
3. 📦 打包成独立 exe 分发给其他用户
4. 🚀 探索更多高级功能

祝使用愉快！
