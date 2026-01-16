# Windows 原生运行改造方案

## 📊 总览

将项目从 WSL 环境改造为 Windows 原生运行，预计工作量：**1-2天**

### 改造难度：⭐⭐☆☆☆（中等偏易）

## ✅ 已具备的跨平台能力

项目已经具备良好的跨平台基础：

1. ✅ **FFmpeg 调用** - 代码中已使用 `get_windows_subprocess_kwargs_hide_console()`
2. ✅ **GUI 程序** - 已有 Windows 打包配置
3. ✅ **硬件编码器** - NVENC 在 Windows 上原生支持
4. ✅ **路径处理** - 使用 `pathlib.Path`
5. ✅ **CLI 命令** - 通过 `pyproject.toml` 配置的 entry_points

## 🔧 需要改造的部分

### 1. 配置文件路径（⭐☆☆☆☆ - 非常简单）

#### 当前问题
```yaml
# configs/default.yaml
default_source_dir: "/mnt/e/短剧剪辑/源素材视频"  # WSL 路径
backup_source_dir: "/mnt/e/短剧剪辑/源素材视频"
temp_dir: "/home/drama_processor"
tail_cache_dir: "/home/tails_cache"
```

#### 解决方案

**方案 A：创建 Windows 专用配置**

```yaml
# configs/windows.yaml
default_source_dir: "E:\\短剧剪辑\\源素材视频"
backup_source_dir: "E:\\短剧剪辑\\源素材视频"
temp_dir: "%TEMP%\\drama_processor"  # 或 "C:\\Temp\\drama_processor"
tail_cache_dir: "C:\\ProgramData\\drama_processor\\tails_cache"
font_file: "C:\\Windows\\Fonts\\msyh.ttc"  # 微软雅黑
```

**方案 B：智能路径转换（推荐）**

在 `config.py` 中添加路径转换逻辑：

```python
def convert_wsl_path_to_windows(path: str) -> str:
    """将 WSL 路径转换为 Windows 路径"""
    import re
    # /mnt/e/xxx -> E:\xxx
    match = re.match(r'/mnt/([a-z])/(.+)', path)
    if match:
        drive = match.group(1).upper()
        rest = match.group(2).replace('/', '\\')
        return f"{drive}:\\{rest}"
    return path
```

### 2. 字体配置（⭐☆☆☆☆ - 非常简单）

#### 当前问题
```yaml
font_file: "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
```

#### 解决方案

在 `models/config.py` 中添加默认字体检测：

```python
class ProcessingConfig(BaseModel):
    font_file: Optional[str] = Field(default=None)
    
    def get_default_font(self) -> str:
        """自动检测平台默认字体"""
        if self.font_file and os.path.exists(self.font_file):
            return self.font_file
        
        import platform
        if platform.system() == "Windows":
            # Windows 默认字体
            fonts = [
                "C:\\Windows\\Fonts\\msyh.ttc",      # 微软雅黑
                "C:\\Windows\\Fonts\\simhei.ttf",    # 黑体
                "C:\\Windows\\Fonts\\simsun.ttc",    # 宋体
            ]
            for font in fonts:
                if os.path.exists(font):
                    return font
        elif platform.system() == "Linux":
            return "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
        
        return "arial.ttf"  # 兜底
```

### 3. FFmpeg 可执行文件（⭐⭐☆☆☆ - 简单）

#### 当前问题
- 依赖系统安装的 `ffmpeg` 和 `ffprobe`
- WSL 中通常通过 `apt` 或 `pacman` 安装

#### 解决方案

**方案 A：要求用户安装（简单）**

创建安装检查脚本：

```python
# scripts/check_ffmpeg_windows.py
import subprocess
import sys

def check_ffmpeg():
    """检查 FFmpeg 是否安装"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, 
                              text=True)
        if result.returncode == 0:
            print("✅ FFmpeg 已安装")
            print(result.stdout.split('\n')[0])
            return True
    except FileNotFoundError:
        print("❌ FFmpeg 未安装")
        print("\n请访问以下链接下载:")
        print("https://www.gyan.dev/ffmpeg/builds/")
        print("\n推荐下载: ffmpeg-release-essentials.zip")
        print("解压后将 bin 目录添加到系统 PATH")
        return False

if __name__ == "__main__":
    if not check_ffmpeg():
        sys.exit(1)
```

**方案 B：内置 FFmpeg（推荐用于分发）**

```
项目结构:
dramas_processor/
├── bin/           # 新增
│   ├── ffmpeg.exe
│   ├── ffprobe.exe
├── src/
├── configs/
```

修改代码在调用时优先使用本地 ffmpeg：

```python
def get_ffmpeg_path() -> str:
    """获取 FFmpeg 可执行文件路径"""
    # 1. 检查项目 bin 目录
    local_ffmpeg = Path(__file__).parent.parent / "bin" / "ffmpeg.exe"
    if local_ffmpeg.exists():
        return str(local_ffmpeg)
    
    # 2. 使用系统 PATH
    return "ffmpeg"
```

### 4. 临时目录（⭐☆☆☆☆ - 非常简单）

#### 当前问题
```python
temp_dir: "/home/drama_processor"
```

#### 解决方案

修改 `utils/files.py` 中的 `ensure_temp_root`：

```python
def ensure_temp_root(temp_root_opt: Optional[str]) -> str:
    """确保临时目录存在，跨平台支持"""
    if temp_root_opt:
        root = temp_root_opt.strip()
        # 支持环境变量
        root = os.path.expandvars(root)  # 展开 %TEMP% 等
    else:
        # 使用系统临时目录
        import tempfile
        root = os.path.join(tempfile.gettempdir(), "drama_processor")
    
    try:
        os.makedirs(root, exist_ok=True)
    except Exception as e:
        print(f"⚠️ 创建临时目录失败（{root}），使用系统默认：{e}")
        import tempfile
        root = tempfile.gettempdir()
        os.makedirs(root, exist_ok=True)
    
    return root
```

### 5. Shell 脚本迁移（⭐⭐⭐☆☆ - 中等）

#### 当前问题
- 10个 `.sh` 脚本依赖 bash
- WSL 特定的脚本

#### 解决方案

**关键脚本需要移植为 PowerShell 或 Python：**

| Shell 脚本 | 用途 | 迁移方案 |
|-----------|------|---------|
| `feishu_quick.sh` | 飞书快捷命令 | → `feishu_quick.ps1` (PowerShell) |
| `keep-show.sh` | 清理脚本 | → `keep-show.py` (Python) |
| `run_with_caffeinate.sh` | 防休眠运行 | → Windows 自带电源管理 |
| `wsl_memory_guard.sh` | WSL 内存监控 | ❌ 不需要（Windows 内存管理更好） |

**示例：PowerShell 版本的 feishu_quick**

```powershell
# scripts/feishu_quick.ps1
param(
    [string]$Date = ""
)

Write-Host "🚀 Feishu Quick - Windows 版本" -ForegroundColor Green

if ($Date) {
    drama-processor feishu run --date $Date --yes
} else {
    drama-processor feishu run --yes
}
```

### 6. WSL 特定代码清理（⭐⭐☆☆☆ - 简单）

#### 需要修改的文件

**`src/drama_processor/utils/fingerprint.py`**

```python
def _get_windows_machine_guid_from_wsl() -> Optional[str]:
    # 这个函数在 Windows 原生环境下不需要
    # 改为直接读取 Windows 注册表
```

改为：

```python
def _get_windows_machine_guid() -> Optional[str]:
    """在 Windows 下读取 MachineGuid"""
    import platform
    if platform.system() != "Windows":
        return None
    
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                            r"SOFTWARE\Microsoft\Cryptography")
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return value
    except Exception:
        return None
```

## 📋 改造步骤清单

### 阶段 1：基础环境准备（30分钟）

- [ ] 安装 Python 3.8+ (Windows 版本)
- [ ] 下载 FFmpeg Windows 版本
  - 推荐：https://www.gyan.dev/ffmpeg/builds/
  - 下载 `ffmpeg-release-essentials.zip`
  - 解压到 `C:\ffmpeg\` 并添加到 PATH
- [ ] 验证 FFmpeg: `ffmpeg -version`

### 阶段 2：配置文件调整（15分钟）

- [ ] 创建 `configs/default.yaml`
- [ ] 修改路径为 Windows 格式
- [ ] 配置 Windows 字体路径
- [ ] 修改临时目录为 `%TEMP%\drama_processor`

### 阶段 3：代码修改（2-3小时）

- [ ] 修改 `utils/files.py` - `ensure_temp_root()` 支持 Windows
- [ ] 修改 `models/config.py` - 添加 `get_default_font()` 字体检测
- [ ] 修改 `utils/fingerprint.py` - 原生 Windows 注册表读取
- [ ] 测试所有 subprocess 调用在 Windows 下正常工作

### 阶段 4：脚本迁移（2-4小时）

- [ ] `feishu_quick.sh` → `feishu_quick.ps1`
- [ ] `keep-show.sh` → `keep_show.py`
- [ ] 创建 `scripts/setup_windows.ps1` 安装脚本
- [ ] 删除或标记 WSL 专用脚本为废弃

### 阶段 5：测试验证（1-2小时）

- [ ] CLI 命令测试：`drama-processor --help`
- [ ] 单部剧处理测试
- [ ] 飞书集成测试
- [ ] GUI 测试（如果使用）
- [ ] 硬件编码器测试

### 阶段 6：打包分发（1小时）

- [ ] 使用 PyInstaller 打包
- [ ] 测试独立 exe
- [ ] 创建安装文档

## 🎯 推荐的改造优先级

### 必须改（核心功能）
1. ✅ 配置文件路径
2. ✅ 字体路径
3. ✅ 临时目录
4. ✅ FFmpeg 路径

### 应该改（提升体验）
5. ⭐ Shell 脚本迁移（至少 `feishu_quick`）
6. ⭐ Windows 原生注册表读取

### 可选改（锦上添花）
7. 💡 内置 FFmpeg
8. 💡 自动安装脚本
9. 💡 Windows 服务支持（长期运行）

## 💻 示例：创建 Windows 配置

```yaml
# configs/default.yaml
---
# Windows 原生配置文件

# 激活的用户配置
active_user: xh

# 基本设置
target_fps: 60
smart_fps: true
fast_mode: true
filter_threads: 2
verbose: false

# 时长设置
min_duration: 480.0
max_duration: 900.0

# 目录设置（Windows 路径）
default_source_dir: "E:\\短剧剪辑\\源素材视频"
backup_source_dir: "E:\\短剧剪辑\\源素材视频备份"
temp_dir: "C:\\Temp\\drama_processor"  # 或使用 %TEMP%
output_dir: "..\\导出素材"
tail_cache_dir: "C:\\ProgramData\\drama_processor\\tails_cache"
tail_file: "assets\\tail.mp4"

# 字体设置（Windows 字体）
font_file: "C:\\Windows\\Fonts\\msyh.ttc"  # 微软雅黑

# 水印设置
watermark_path: "assets\\watermark-xiaohong.png"
enable_watermark: false
enable_brand_text: true
brand_text: "热门短剧"

# 其他设置保持不变...
```

## 🚀 快速启动脚本

### PowerShell 启动脚本

```powershell
# start_windows.ps1
param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

Write-Host "=" -repeat 60 -ForegroundColor Cyan
Write-Host "Drama Processor - Windows 版本" -ForegroundColor Green
Write-Host "=" -repeat 60 -ForegroundColor Cyan

# 检查 Python
Write-Host "`n[1/4] 检查 Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version
    Write-Host "  ✅ $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Python 未安装或未添加到 PATH" -ForegroundColor Red
    exit 1
}

# 检查 FFmpeg
Write-Host "`n[2/4] 检查 FFmpeg..." -ForegroundColor Yellow
try {
    $ffmpegVersion = ffmpeg -version 2>&1 | Select-Object -First 1
    Write-Host "  ✅ FFmpeg 已安装" -ForegroundColor Green
} catch {
    Write-Host "  ❌ FFmpeg 未安装或未添加到 PATH" -ForegroundColor Red
    Write-Host "  请访问: https://www.gyan.dev/ffmpeg/builds/" -ForegroundColor Yellow
    exit 1
}

# 检查依赖
Write-Host "`n[3/4] 检查 Python 依赖..." -ForegroundColor Yellow
try {
    pip show pydantic | Out-Null
    Write-Host "  ✅ 依赖已安装" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  依赖未完全安装，正在安装..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

# 检查配置
Write-Host "`n[4/4] 检查配置文件..." -ForegroundColor Yellow
if (Test-Path "configs\default.yaml") {
    Write-Host "  ✅ Windows 配置文件存在" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  未找到 Windows 配置，使用默认配置" -ForegroundColor Yellow
}

if ($CheckOnly) {
    Write-Host "`n✅ 环境检查完成！" -ForegroundColor Green
    exit 0
}

# 启动程序
Write-Host "`n[启动] 运行 Drama Processor..." -ForegroundColor Green
drama-processor --help
```

## 📦 一键部署包结构

```
drama-processor-windows/
├── drama-processor.exe      # PyInstaller 打包的可执行文件
├── bin/                     # FFmpeg 可执行文件（可选内置）
│   ├── ffmpeg.exe
│   └── ffprobe.exe
├── assets/                  # 资源文件
│   ├── tail.mp4
│   └── watermark-xiaohong.png
├── configs/                 # 配置文件
│   ├── default.yaml
│   └── users/
│       └── example.yaml
├── setup.ps1                # 首次设置脚本
├── start.ps1                # 快速启动脚本
├── README_WINDOWS.txt       # Windows 使用说明
└── 使用指南.pdf              # 图文教程
```

## 🎬 实际部署示例

### 场景：为客户部署 Windows 版本

```powershell
# 1. 下载发布包
Invoke-WebRequest -Uri "https://xxx/drama-processor-windows-v1.0.0.zip" -OutFile "drama-processor.zip"

# 2. 解压
Expand-Archive -Path "drama-processor.zip" -DestinationPath "C:\drama-processor"

# 3. 运行设置
cd C:\drama-processor
.\setup.ps1

# 4. 配置（编辑 configs\default.yaml）
notepad configs\default.yaml

# 5. 首次运行测试
.\drama-processor.exe --version
.\drama-processor.exe process E:\短剧库 --count 1

# 6. 创建桌面快捷方式
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Drama Processor.lnk")
$Shortcut.TargetPath = "C:\drama-processor\drama-processor.exe"
$Shortcut.Save()
```

## ⚠️ 注意事项

### 1. 路径分隔符
- Windows 使用 `\`，但 Python 的 `Path` 类会自动处理
- 配置文件中建议使用 `\\` 或 `/`（两者都支持）

### 2. 权限问题
- `C:\Program Files\` 需要管理员权限
- 推荐使用 `C:\ProgramData\` 或用户目录

### 3. 中文路径
- Windows 对中文路径支持良好
- 确保文件编码为 UTF-8

### 4. 长路径支持
- Windows 默认路径长度限制 260 字符
- 如需支持更长路径，修改注册表或使用 `\\?\` 前缀

## 📚 参考文档

- [PyInstaller Windows 打包](https://pyinstaller.org/en/stable/operating-mode.html#windows)
- [Python pathlib 跨平台路径](https://docs.python.org/3/library/pathlib.html)
- [FFmpeg Windows 构建](https://www.gyan.dev/ffmpeg/builds/)
- [Windows 字体列表](https://learn.microsoft.com/en-us/typography/fonts/windows_11_font_list)

## 🎉 预期效果

改造完成后：
- ✅ 无需 WSL，直接在 Windows 运行
- ✅ 双击 exe 即可启动（打包后）
- ✅ 性能提升（无 WSL 转换开销）
- ✅ 更好的硬件兼容性
- ✅ 更简单的部署流程
