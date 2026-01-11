# Drama Processor - Windows 快速参考

## 🚀 快速开始

### 第一次使用

**一键安装所有依赖**（使用 winget，推荐 ⭐⭐⭐）：

```powershell
# 1. 安装 Python
winget install Python.Python.3.12

# 2. 安装 FFmpeg
winget install --id=Gyan.FFmpeg -e

# 重新打开 PowerShell（让 PATH 生效）

# 3. 创建虚拟环境
python -m venv venv
.\venv\Scripts\activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 验证环境
python scripts\test_windows.py
```

**或使用自动设置脚本**：

```powershell
powershell -ExecutionPolicy Bypass -File setup_windows.ps1
```

### 启动命令行

双击运行：`启动命令行.bat`

或手动激活：
```powershell
.\venv\Scripts\activate
```

---

## 📋 常用命令速查

### 基础处理

```powershell
# 查看帮助
python -m drama_processor --help

# 处理单个短剧
python -m drama_processor process "E:\短剧\我的剧集"

# 使用自定义配置
python -m drama_processor -c configs\my_config.yaml process "E:\短剧"

# 批量处理
python -m drama_processor process "E:\短剧剪辑\源素材视频" --jobs 2

# 分析短剧（不处理）
python -m drama_processor analyze "E:\短剧\我的剧集"
```

### 处理参数

```powershell
# 生成 5 个素材，每个 55-65 秒
python -m drama_processor process "E:\短剧" \
  --count 5 \
  --min-sec 55 \
  --max-sec 65

# 自定义帧率和画布
python -m drama_processor process "E:\短剧" \
  --fps 30 \
  --canvas "1080x1920"

# 自定义文字
python -m drama_processor process "E:\短剧" \
  --footer-text "更多精彩请关注..." \
  --side-text "第 {episode} 集"

# 指定片尾视频
python -m drama_processor process "E:\短剧" \
  --tail-file "assets\my_tail.mp4"
```

### 飞书功能

```powershell
# 查看待处理列表
python -m drama_processor feishu list

# 筛选特定状态
python -m drama_processor feishu list --status "待处理"

# 筛选特定日期
python -m drama_processor feishu list --date "1.10"

# 手动处理指定剧集
python -m drama_processor feishu run --root-dir "E:\短剧\剧集名"

# 自动处理表格中的待处理剧集
python -m drama_processor feishu run --status "待处理"

# 监听模式（自动处理）
python -m drama_processor feishu watch
```

### 配置管理

```powershell
# 查看配置
python -m drama_processor config show

# 生成配置模板
python -m drama_processor config init my_config.yaml

# 验证配置
python -m drama_processor config validate configs\my_config.yaml
```

---

## ⚙️ 配置文件速查

### 路径配置（Windows 格式）

```yaml
# 源视频目录
default_source_dir: "E:\\短剧剪辑\\源素材视频"

# 输出目录
output_dir: "E:\\短剧剪辑\\导出素材"

# 临时目录（null = 系统临时目录）
temp_dir: null

# 字体文件（null = 自动检测）
font_file: null  # 或 "C:\\Windows\\Fonts\\msyh.ttc"

# 片尾视频
tail_file: "assets\\tail.mp4"
```

### 视频编码设置

```yaml
video:
  # NVIDIA 显卡用户（硬件加速）
  codec: "h264_nvenc"
  preset: "p4"  # p1-p7，数字越大质量越好
  
  # CPU 编码（兼容性最好）
  # codec: "libx264"
  # preset: "medium"
  
  fps: 30
  canvas:
    width: 1080
    height: 1920
```

### 飞书配置

```yaml
enable_feishu_features: true

feishu:
  app_id: "cli_xxxxx"
  app_secret: "xxxxx"
  bitable_app_token: "xxxxx"
  bitable_table_id: "xxxxx"
  webhook_url: "https://open.feishu.cn/..."  # 可选

feishu_watcher:
  enabled: true
  poll_interval: 60
  pending_status_value: "待处理"
  processing_status_value: "处理中"
  completed_status_value: "已完成"
```

---

## 🎯 典型工作流

### 工作流 1：本地批量处理

```powershell
# 1. 准备素材
# 将短剧视频放到 E:\短剧剪辑\源素材视频\

# 2. 编辑配置
notepad configs\my_config.yaml

# 3. 处理
python -m drama_processor -c configs\my_config.yaml process "E:\短剧剪辑\源素材视频"

# 4. 查看输出
dir "E:\短剧剪辑\导出素材"
```

### 工作流 2：飞书自动化

```powershell
# 1. 配置飞书凭证
notepad configs\my_config.yaml

# 2. 测试连接
python -m drama_processor -c configs\my_config.yaml feishu list

# 3. 启动监听（后台运行）
Start-Process -NoNewWindow python -ArgumentList "-m","drama_processor","-c","configs\my_config.yaml","feishu","watch"

# 4. 在飞书表格中添加待处理剧集，程序会自动处理
```

### 工作流 3：打包分发

```powershell
# 1. 确保 bin 目录有 FFmpeg
dir bin\ffmpeg.exe

# 2. 打包
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1 -Version "1.0.0"

# 3. 发布包位于
dir release_windows_v1.0.0\

# 4. 压缩并分发
Compress-Archive -Path release_windows_v1.0.0 -DestinationPath drama_processor.zip
```

---

## 🔧 故障排除

### FFmpeg 相关

```powershell
# 检查 FFmpeg
.\bin\ffmpeg.exe -version
# 或
ffmpeg -version

# 测试硬件编码
.\bin\ffmpeg.exe -encoders | findstr nvenc
```

### 环境测试

```powershell
# 运行完整测试
python scripts\test_windows.py

# 检查 Python
python --version

# 检查已安装的包
pip list
```

### 清理临时文件

```powershell
# 查看临时目录位置
python -c "import tempfile; print(tempfile.gettempdir())"

# 手动清理
rmdir /s /q %TEMP%\drama_processor
```

### 查看日志

```powershell
# 日志文件通常在
dir logs\

# 启用 DEBUG 日志
python -m drama_processor --log-level DEBUG process "E:\短剧"
```

---

## 📚 更多文档

- **完整使用教程**: `docs\WINDOWS_使用教程.md`
- **命令详细说明**: `COMMANDS_USAGE_GUIDE.md`
- **配置示例**: `configs\windows_default.yaml`
- **Windows 快速开始**: `docs\WINDOWS_QUICKSTART.md`

---

## 💡 性能优化提示

1. **使用 NVIDIA GPU 加速**（如果有独立显卡）：
   ```yaml
   video:
     codec: "h264_nvenc"
   ```

2. **调整并行任务数**（根据 CPU 核心数）：
   ```powershell
   python -m drama_processor process "E:\短剧" --jobs 4
   ```

3. **使用 SSD 作为临时目录**：
   ```yaml
   temp_dir: "E:\\Temp\\drama_processor"  # SSD 路径
   ```

4. **减少输出质量提升速度**（如需快速预览）：
   ```yaml
   video:
     preset: "p1"  # 更快但质量略低
   ```

---

**祝使用愉快！** 🎉

有问题请查看完整文档或提 Issue。
