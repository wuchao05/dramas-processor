## Windows 单文件 EXE 打包指南（NiceGUI 原生模式）

目标：生成一个 `dramas-processor-gui.exe`，拷到新电脑上即可双击运行（无需安装 Python）。

### 你打包电脑（Windows 开发机）需要做什么

1. **安装 Python（建议 3.10/3.11 x64）**

2. **安装依赖**

在项目根目录执行：

```bash
pip install -r requirements.txt
pip install pyinstaller
```

3. **执行打包（单文件）**

```bash
pyinstaller packaging/pyinstaller_gui_onefile.spec
```

生成文件：

- `dist/dramas-processor-gui.exe`

### 新电脑（Windows）需要做什么

- 直接拷贝 `dramas-processor-gui.exe`，双击运行即可

> 首次启动如果弹出 Windows 防火墙提示，请允许（NiceGUI 原生模式内部会启动本地服务）。

### 已内置的资源（无需用户改配置）

此打包方式会把以下内容打进 exe：

- `configs/default.yaml`
- `assets/` 目录（包含 `tail.mp4`、水印、以及你放进去的字体文件等）

程序运行时会自动通过 `sys._MEIPASS` 定位这些资源。

### 重要说明：FFmpeg

项目剪辑依赖 `ffmpeg` 命令。

- 如果你的环境已经在系统 PATH 里有 ffmpeg，新电脑也需要安装并配置到 PATH
- 或者你也可以把 `ffmpeg.exe` 随 exe 同目录分发，并在代码里扩展优先查找同目录（如需要我可以继续帮你做成“完全自带 ffmpeg”的版本）


