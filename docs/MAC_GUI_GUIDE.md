# macOS GUI 启动指南（Tkinter）

本指南用于在 macOS 上启动 `drama_processor` 的 GUI（Tkinter 版）。

## 1. 核心前置条件

- **必须使用带 Tk 8.6 的 Python**  
  mac 自带 Python 通常绑定 Tk 8.5，容易出现 GUI 黑屏。推荐使用 **python.org 官方安装包**。
- **FFmpeg 必须可用**  
  GUI 启动前会检查 `ffmpeg` 是否在 PATH 中。

## 2. 安装官方 Python（推荐）

下载并安装 python.org 官方版本（建议 3.11 或 3.12）：  
https://www.python.org/downloads/macos/

安装完成后常见路径：

```
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
```

## 3. 创建虚拟环境

在仓库根目录执行：

```bash
cd /Users/wuchao/Documents/code/guazai/dramas_processor
rm -rf .venv
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m venv .venv
source .venv/bin/activate
```

## 4. 确认 Tk 版本

```bash
python -c "import tkinter as tk; print('TkVersion:', tk.TkVersion)"
```

必须看到 `8.6.x`，否则 GUI 可能黑屏。

## 5. 解决 pip 证书问题（如遇到 SSL 失败）

如果安装依赖时报 SSL 证书错误，可临时使用以下方式：

```bash
python -m pip install --upgrade pip setuptools wheel certifi \
  --trusted-host pypi.org \
  --trusted-host files.pythonhosted.org \
  --trusted-host pypi.python.org
```

## 6. 安装项目并启动 GUI

```bash
python -m pip install -e . --no-build-isolation \
  --trusted-host pypi.org \
  --trusted-host files.pythonhosted.org \
  --trusted-host pypi.python.org

python -m drama_processor.gui
```

## 7. 常见问题排查

### 7.1 GUI 黑屏

原因：使用了 Tk 8.5（系统 Python）。  
解决：必须换成 python.org 官方安装包（Tk 8.6）。

### 7.2 `_tkinter` 缺失

原因：Homebrew 的 Python 版本未编译 Tk。  
解决：换 python.org 官方安装包，或确认 Homebrew Python 已链接 `tcl-tk` 并含 `_tkinter`。

### 7.3 FFmpeg 未安装

```bash
brew install ffmpeg
```

## 8. 最小自检脚本

用于确认 Tk 能正常显示：

```python
import tkinter as tk
from tkinter import ttk

root = tk.Tk()
ttk.Label(root, text="Tk 显示测试").pack(padx=20, pady=20)
root.after(2000, root.destroy)
root.mainloop()
```
