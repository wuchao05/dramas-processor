# Drama Processor Windows 版本使用教程

## 📋 目录

- [环境要求](#环境要求)
- [安装步骤](#安装步骤)
- [配置说明](#配置说明)
- [基础使用](#基础使用)
- [Feishu 功能](#feishu-功能)
- [打包发布](#打包发布)
- [常见问题](#常见问题)

---

## 🔧 环境要求

### 必需软件

- **Windows 10/11** (64 位)
  - 需要 Windows 10 1809+ 或 Windows 11（支持 winget）
- **Python 3.8+**（下面会教你安装）
- **FFmpeg**（视频处理工具，下面会教你安装）

### 硬件建议

- **CPU**: Intel i5 或更高
- **内存**: 8GB+（处理大量视频建议 16GB+）
- **硬盘**: SSD（用于临时文件，加速处理）
- **显卡**: 支持 NVENC 的 NVIDIA 显卡（可选，用于硬件加速）

---

## 📦 安装步骤

### 步骤 0: 获取项目代码

```powershell
# 如果已有代码，跳过此步骤
git clone <你的仓库地址>
cd dramas_processor
```

### 步骤 1: 安装 Python（使用 winget，推荐 ⭐⭐⭐）

Windows 10/11 自带 `winget` 包管理器，一行命令安装 Python！

```powershell
# 安装 Python 3.12（推荐）
winget install Python.Python.3.12

# 或安装 Python 3.11
winget install Python.Python.3.11
```

**验证安装**：

```powershell
# 关闭并重新打开 PowerShell（让 PATH 生效）
python --version
```

✅ **完成！** 如果显示 `Python 3.12.x` 或 `Python 3.11.x`，说明安装成功。

> 💡 **优点**：
>
> - 自动安装到系统 PATH
> - 自动配置环境变量
> - 一行命令搞定

> ⚠️ **注意**：
>
> - 安装后需要**重新打开 PowerShell** 才能使用 python 命令
> - 如果已经安装了 Python，可以跳过此步骤

---

### 步骤 2: 安装 FFmpeg（使用 winget，推荐 ⭐⭐⭐）

同样使用 winget，一行命令安装 FFmpeg！

```powershell
# 安装 FFmpeg
winget install --id=Gyan.FFmpeg -e
```

**验证安装**：

```powershell
ffmpeg -version
```

✅ **完成！** 如果显示版本信息，说明安装成功。

---

### 可选：手动安装方式

如果你的 Windows 版本不支持 winget（低于 Windows 10 1809），可以手动安装：

#### 手动安装 Python

1. 访问：https://www.python.org/downloads/
2. 下载最新的 Python 3.12 或 3.11
3. 运行安装程序
4. ⚠️ **重要**：勾选 "Add Python to PATH"
5. 点击 "Install Now"

#### 手动安装 FFmpeg（方案二：内置到项目）

如果你的系统没有 `winget`，或想将 FFmpeg 内置到项目中，可以使用这种方式

---

#### 手动安装 FFmpeg（内置到项目）

如果你的系统没有 `winget`，或想将 FFmpeg 内置到项目中（打包时需要）：

**详细步骤**：

1. **下载 FFmpeg**

   访问官方下载页面：https://www.gyan.dev/ffmpeg/builds/

   - 找到 **"release builds"** 部分
   - 点击下载 **`ffmpeg-release-essentials.zip`** (约 70-80 MB)
   - 或直接下载链接：https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip

2. **解压文件**

   ```powershell
   # 下载后，解压到任意位置，例如：
   # C:\Users\你的用户名\Downloads\ffmpeg-7.0-essentials_build\
   ```

   解压后的文件夹结构：

   ```
   ffmpeg-7.0-essentials_build/
   ├── bin/
   │   ├── ffmpeg.exe    ← 我们需要这个
   │   ├── ffprobe.exe   ← 我们需要这个
   │   └── ffplay.exe
   ├── doc/
   └── presets/
   ```

3. **复制到项目**

   ```powershell
   # 进入项目目录
   cd dramas_processor

   # 创建 bin 文件夹
   mkdir bin

   # 复制文件（修改路径为你实际的解压路径）
   copy "C:\Users\你的用户名\Downloads\ffmpeg-7.0-essentials_build\bin\ffmpeg.exe" bin\
   copy "C:\Users\你的用户名\Downloads\ffmpeg-7.0-essentials_build\bin\ffprobe.exe" bin\
   ```

4. **验证安装**

   ```powershell
   # 在项目根目录运行
   .\bin\ffmpeg.exe -version
   ```

✅ **完成！** 现在 FFmpeg 已经内置到项目中。

---

### 步骤 3: 安装 Python 依赖

```powershell
# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\activate

# 升级 pip（可选）
python -m pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt

# 如果需要开发工具
pip install -e ".[dev]"
```

### 步骤 4: 验证安装

```powershell
# 运行测试脚本
python scripts\test_windows.py
```

输出应该类似：

```
============================================================
Drama Processor Windows 环境测试
============================================================
[1/5] 测试 FFmpeg...
  ✅ FFmpeg: E:\dramas_processor\bin\ffmpeg.exe
[2/5] 测试字体检测...
  ✅ 字体: C:\Windows\Fonts\msyh.ttc
[3/5] 测试临时目录...
  ✅ 临时目录: C:\Users\YourName\AppData\Local\Temp\drama_processor
[4/5] 测试配置加载...
  ✅ 配置加载成功
[5/5] 测试 CLI...
  ✅ CLI 可用

============================================================
✅ 全部通过 (5/5)
============================================================
```

---

## ⚙️ 配置说明

### 创建配置文件

推荐使用 `configs/windows_default.yaml` 作为模板：

```powershell
# 复制默认配置
copy configs\windows_default.yaml configs\my_config.yaml

# 使用编辑器打开配置文件
notepad configs\my_config.yaml
```

### 关键配置项

```yaml
# 源视频目录（修改为你的实际路径）
default_source_dir: "E:\\短剧剪辑\\源素材视频"
backup_source_dir: "E:\\短剧剪辑\\源素材视频"

# 输出目录
output_dir: "E:\\短剧剪辑\\导出素材"

# 临时目录（null 表示使用系统临时目录）
temp_dir: null # 或指定路径如 "E:\\Temp\\drama_processor"

# 字体文件（null 表示自动检测）
font_file: null # 或指定如 "C:\\Windows\\Fonts\\msyh.ttc"

# 片尾视频
tail_file: "assets\\tail.mp4"

# 视频编码设置
video:
  codec: "h264_nvenc" # NVIDIA 显卡用户
  # codec: "libx264"   # CPU 编码（兼容性最好）
  preset: "p4" # p1-p7，数字越大质量越好但速度越慢
  fps: 30
  canvas:
    width: 1080
    height: 1920
```

### 飞书配置（如果使用）

```yaml
# 启用飞书功能
enable_feishu_features: true
enable_feishu_notification: true

feishu:
  app_id: "cli_xxx"
  app_secret: "xxx"
  bitable_app_token: "xxx"
  bitable_table_id: "xxx"

  # Webhook 通知（可选）
  webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"

# 飞书监听配置
feishu_watcher:
  enabled: true
  poll_interval: 60 # 每 60 秒检查一次
  pending_status_value: "待处理"
  processing_status_value: "处理中"
  completed_status_value: "已完成"
```

---

## 🚀 基础使用

### 方式一：使用 Python 直接运行

```powershell
# 激活虚拟环境
.\venv\Scripts\activate

# 处理单个短剧
python -m drama_processor process "E:\短剧剪辑\源素材视频\我的剧集"

# 使用自定义配置
python -m drama_processor -c configs\my_config.yaml process "E:\短剧剧集"

# 批量处理多个短剧
python -m drama_processor process "E:\短剧剪辑\源素材视频"

# 分析短剧结构（不处理）
python -m drama_processor analyze "E:\短剧剪辑\源素材视频\我的剧集"
```

### 方式二：使用打包的 EXE（推荐给非技术用户）

```powershell
# 先打包（见下文"打包发布"部分）
# 然后直接运行
.\dramas-processor-gui.exe
```

### 常用命令参数

```powershell
# 处理命令
python -m drama_processor process [选项] <源目录>

# 常用选项：
  -c, --config PATH           # 指定配置文件
  --count INTEGER             # 生成素材数量
  --min-sec FLOAT            # 最小片段时长（秒）
  --max-sec FLOAT            # 最大片段时长（秒）
  --date TEXT                # 过滤日期（如 9.6）
  --fps INTEGER              # 帧率
  --canvas TEXT              # 画布尺寸（如 1080x1920）
  --font-file PATH           # 字体文件路径
  --footer-text TEXT         # 页脚文本
  --tail-file PATH           # 片尾视频文件
  --jobs INTEGER             # 并行任务数
  --keep-temp                # 保留临时文件

# 示例：
python -m drama_processor process "E:\短剧" --count 5 --min-sec 55 --max-sec 65
```

---

## 🔗 Feishu 功能

Drama Processor 支持与飞书多维表格集成，实现自动化处理工作流。

### 配置 Feishu

1. **获取飞书凭证**:

   - 访问 [飞书开放平台](https://open.feishu.cn/)
   - 创建应用，获取 `app_id` 和 `app_secret`
   - 获取多维表格的 `app_token` 和 `table_id`

2. **配置文件设置**:

   ```yaml
   enable_feishu_features: true

   feishu:
     app_id: "cli_xxxxx"
     app_secret: "xxxxx"
     bitable_app_token: "xxxxx"
     bitable_table_id: "xxxxx"
   ```

### Feishu 命令使用

#### 1. 查看待处理列表

```powershell
# 查看所有待处理剧集
python -m drama_processor feishu list

# 筛选特定状态
python -m drama_processor feishu list --status "待处理"

# 筛选特定日期
python -m drama_processor feishu list --date "1.10"
```

#### 2. 手动执行处理

```powershell
# 处理指定剧集
python -m drama_processor feishu run --root-dir "E:\短剧剪辑\源素材视频\我的剧集"

# 使用表格中的配置自动处理
python -m drama_processor feishu run --status "待处理"

# 高级参数
python -m drama_processor feishu run \
  --status "待处理" \
  --count 10 \
  --min-sec 55 \
  --max-sec 65 \
  --fps 30
```

#### 3. 监听模式（自动处理）

```powershell
# 启动监听，自动处理新增的待处理剧集
python -m drama_processor feishu watch

# 使用自定义配置
python -m drama_processor -c configs\my_config.yaml feishu watch
```

**监听模式工作流程**:

1. 每隔指定时间（默认 60 秒）检查飞书表格
2. 查找状态为"待处理"的剧集
3. 自动开始处理，并更新状态为"处理中"
4. 完成后更新状态为"已完成"，并记录输出路径
5. 失败时更新状态为"失败"，并记录错误信息

**推荐设置**（Windows 后台运行）:

```powershell
# 方式 1：PowerShell 后台运行
Start-Process -NoNewWindow python -ArgumentList "-m", "drama_processor", "feishu", "watch"

# 方式 2：使用 nssm 安装为 Windows 服务（推荐生产环境）
# 下载 nssm: https://nssm.cc/download
nssm install DramaProcessorWatch "C:\path\to\python.exe" "-m drama_processor feishu watch"
nssm start DramaProcessorWatch
```

---

## 📦 打包发布

### 打包为单文件 EXE

```powershell
# 确保已安装 PyInstaller
pip install pyinstaller

# 确保 bin 目录下有 ffmpeg.exe 和 ffprobe.exe
dir bin\

# 运行打包脚本
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1 -Version "1.0.0"
```

打包过程：

```
=== Drama Processor Windows 打包 ===
版本: 1.0.0

[1/4] 清理旧文件...
[2/4] 开始打包...
[3/4] 验证打包...
打包成功！文件大小: 156.23 MB
[4/4] 创建发布包...

✅ 完成！发布包位于: release_windows_v1.0.0
```

### 发布包结构

```
release_windows_v1.0.0/
├── dramas-processor-gui.exe    # 主程序（单文件，双击运行）
├── assets/                     # 资源文件
│   ├── tail.mp4               # 片尾视频
│   └── watermark/             # 水印素材
├── configs/                    # 配置文件模板
│   ├── windows_default.yaml
│   └── default.yaml
└── README.md                   # 使用说明
```

### 分发给用户

用户只需：

1. 解压 `release_windows_v1.0.0.zip`
2. 双击 `dramas-processor-gui.exe` 运行
3. 无需安装 Python 或其他依赖

---

## ❓ 常见问题

### Q1: 提示找不到 FFmpeg

**解决方案**:

```powershell
# 检查 FFmpeg 是否存在
dir bin\ffmpeg.exe

# 如果不存在，重新下载并放置
# 或者安装到系统 PATH
```

### Q2: 字体显示异常

**解决方案**:

```yaml
# 在配置文件中明确指定字体
font_file: "C:\\Windows\\Fonts\\msyh.ttc"  # 微软雅黑
# 或
font_file: "C:\\Windows\\Fonts\\simhei.ttf"  # 黑体
```

### Q3: 处理速度慢

**解决方案**:

1. **使用硬件加速**（NVIDIA 显卡）:

   ```yaml
   video:
     codec: "h264_nvenc" # GPU 编码
     preset: "p4" # 平衡速度和质量
   ```

2. **调整并行任务数**:

   ```powershell
   python -m drama_processor process <目录> --jobs 4
   ```

3. **使用 SSD 作为临时目录**:
   ```yaml
   temp_dir: "E:\\Temp\\drama_processor" # SSD 路径
   ```

### Q4: 内存不足

**解决方案**:

1. **减少并行任务数**:

   ```powershell
   python -m drama_processor process <目录> --jobs 1
   ```

2. **使用硬盘临时目录**（而非内存盘）:

   ```yaml
   temp_dir: "E:\\Temp\\drama_processor"
   ```

3. **分批处理**:
   ```powershell
   # 每次处理一个剧集
   python -m drama_processor process "E:\短剧\剧集1"
   python -m drama_processor process "E:\短剧\剧集2"
   ```

### Q5: Feishu 无法连接

**解决方案**:

1. **检查网络连接**
2. **验证飞书凭证**:
   ```powershell
   # 测试飞书连接
   python -m drama_processor feishu list
   ```
3. **检查防火墙设置**

### Q6: 编码失败 (NVENC 相关)

**解决方案**:

```yaml
# 回退到 CPU 编码（兼容性最好）
video:
  codec: "libx264"
  preset: "medium"
```

### Q7: 临时文件占用空间过大

**解决方案**:

```powershell
# 处理后自动清理（默认行为）
python -m drama_processor process <目录>

# 手动清理临时目录
rmdir /s /q C:\Users\YourName\AppData\Local\Temp\drama_processor
```

### Q8: 打包后 EXE 无法运行

**解决方案**:

1. **检查 bin 目录下是否有 FFmpeg**
2. **使用管理员权限运行**
3. **检查杀毒软件是否误报**
4. **查看日志文件**（通常在 EXE 同目录下的 `logs/` 文件夹）

---

## 🎯 快速开始示例

### 场景 1：本地处理单个短剧

```powershell
# 1. 激活环境
.\venv\Scripts\activate

# 2. 处理
python -m drama_processor process "E:\短剧\超能力老公" --count 5

# 3. 查看输出
dir "导出素材"
```

### 场景 2：批量处理多个短剧

```powershell
# 处理整个目录下的所有短剧
python -m drama_processor process "E:\短剧剪辑\源素材视频" --jobs 2
```

### 场景 3：使用飞书自动化

```powershell
# 1. 配置飞书凭证（编辑 configs\my_config.yaml）

# 2. 查看待处理列表
python -m drama_processor -c configs\my_config.yaml feishu list

# 3. 启动监听模式（自动处理）
python -m drama_processor -c configs\my_config.yaml feishu watch
```

### 场景 4：分发给非技术用户

```powershell
# 1. 打包
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1 -Version "1.0.0"

# 2. 压缩发布包
Compress-Archive -Path release_windows_v1.0.0 -DestinationPath drama_processor_v1.0.0.zip

# 3. 分发 zip 文件给用户
# 用户解压后双击 dramas-processor-gui.exe 即可使用
```

---

## 📚 更多资源

- **命令详细文档**: `COMMANDS_USAGE_GUIDE.md`
- **Windows 迁移说明**: `docs/WINDOWS_NATIVE_MIGRATION.md`
- **Windows 快速开始**: `docs/WINDOWS_QUICKSTART.md`
- **配置示例**: `configs/windows_default.yaml`
- **测试脚本**: `scripts/test_windows.py`

---

## 💡 提示

1. **首次使用建议**:

   - 先用小数据集测试
   - 确认 FFmpeg 和字体正常工作
   - 调整配置以适应你的硬件

2. **性能优化**:

   - 使用 NVIDIA GPU 加速（如有）
   - SSD 作为临时目录
   - 根据 CPU 核心数调整 `--jobs` 参数

3. **生产环境**:

   - 使用 Windows 服务运行 `feishu watch`
   - 定期备份配置文件
   - 监控磁盘空间（临时文件）

4. **安全建议**:
   - 不要将包含飞书凭证的配置文件提交到 Git
   - 使用 `.gitignore` 排除敏感文件
   - 定期更新飞书 app_secret

---

**祝使用愉快！有问题请参考上面的常见问题或提 Issue。** 🎉
