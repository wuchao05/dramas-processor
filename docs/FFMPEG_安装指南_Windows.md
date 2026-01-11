# FFmpeg Windows 安装图解教程

本教程详细说明如何在 Windows 上安装 FFmpeg（带截图说明）。

---

## 📋 什么是 FFmpeg？

FFmpeg 是一个强大的视频处理工具，Drama Processor 需要它来处理视频。这是**必需的组件**。

---

## 🎯 推荐方法

### 方法 1：使用 winget（最简单 ⭐⭐⭐）

**适用**：Windows 10 (1809+) / Windows 11

**优点**：
- ✅ 一行命令，最简单
- ✅ 自动配置环境变量
- ✅ 全局可用，任何地方都能用

**步骤**：

1. 打开 PowerShell（无需管理员权限）
2. 运行命令：
   ```powershell
   winget install --id=Gyan.FFmpeg -e
   ```
3. 等待安装完成（约 1-2 分钟）
4. 验证：
   ```powershell
   ffmpeg -version
   ```

如果显示版本信息，说明安装成功！✅

**如果 winget 不可用**：使用方法 2

---

### 方法 2：手动下载内置到项目（传统方式）

**适用**：所有 Windows 版本

**优点**：
- ✅ 不需要修改系统设置
- ✅ 适合打包分发
- ✅ 版本可控

---

## 📖 方法 2 详细步骤：手动下载

### 步骤 1：下载 FFmpeg

#### 1.1 打开下载页面

在浏览器中访问：**https://www.gyan.dev/ffmpeg/builds/**

#### 1.2 找到正确的下载链接

在页面中找到 **"release builds"** 部分，点击下载：

```
📦 ffmpeg-release-essentials.zip
文件大小：约 70-80 MB
```

**直接下载链接**：  
https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip

> 💡 提示：如果下载很慢，可以使用下载工具（如 IDM、迅雷）或搜索"FFmpeg Windows 国内镜像"

---

### 步骤 2：解压文件

#### 2.1 找到下载的文件

下载完成后，文件通常在：
```
C:\Users\你的用户名\Downloads\ffmpeg-release-essentials.zip
```

#### 2.2 解压

- 右键点击 `ffmpeg-release-essentials.zip`
- 选择"全部提取..."或"解压到当前文件夹"
- 解压后会得到一个文件夹，例如：
  ```
  ffmpeg-7.0-essentials_build\
  ```

#### 2.3 查看解压内容

打开解压后的文件夹，你会看到：

```
ffmpeg-7.0-essentials_build/
├── bin/                    ← 这个文件夹里有我们需要的文件
│   ├── ffmpeg.exe         ← 需要这个 ✅
│   ├── ffprobe.exe        ← 需要这个 ✅
│   └── ffplay.exe         ← 不需要
├── doc/                    ← 文档，不需要
└── presets/                ← 预设，不需要
```

**我们只需要 `bin` 文件夹中的两个文件**：
- ✅ `ffmpeg.exe`
- ✅ `ffprobe.exe`

---

### 步骤 3：复制到项目

#### 3.1 打开项目文件夹

进入你的 Drama Processor 项目根目录，例如：
```
E:\dramas_processor\
```

#### 3.2 创建 bin 文件夹

如果项目中没有 `bin` 文件夹，需要创建：

**方法 A：用文件管理器**
- 在项目根目录右键
- 选择"新建" → "文件夹"
- 命名为 `bin`

**方法 B：用 PowerShell**
```powershell
# 进入项目目录
cd E:\dramas_processor

# 创建 bin 文件夹
mkdir bin
```

#### 3.3 复制文件

**方法 A：用文件管理器**（推荐新手）

1. 打开解压的 FFmpeg 文件夹：
   ```
   C:\Users\你的用户名\Downloads\ffmpeg-7.0-essentials_build\bin\
   ```

2. 找到并复制这两个文件：
   - `ffmpeg.exe`
   - `ffprobe.exe`

3. 粘贴到项目的 `bin\` 文件夹：
   ```
   E:\dramas_processor\bin\
   ```

4. 完成后，项目的 `bin` 文件夹应该包含：
   ```
   E:\dramas_processor\
   └── bin\
       ├── ffmpeg.exe     ✅
       └── ffprobe.exe    ✅
   ```

**方法 B：用 PowerShell**（高级用户）

```powershell
# 进入项目目录
cd E:\dramas_processor

# 创建 bin 文件夹（如果不存在）
mkdir bin

# 复制文件（修改路径为你实际的解压路径）
copy "C:\Users\你的用户名\Downloads\ffmpeg-7.0-essentials_build\bin\ffmpeg.exe" bin\
copy "C:\Users\你的用户名\Downloads\ffmpeg-7.0-essentials_build\bin\ffprobe.exe" bin\
```

---

### 步骤 4：验证安装

#### 4.1 打开 PowerShell

在项目根目录：
- 按住 `Shift` 键
- 右键点击空白处
- 选择"在此处打开 PowerShell 窗口"

或者：
```powershell
# 手动进入项目目录
cd E:\dramas_processor
```

#### 4.2 测试 FFmpeg

运行以下命令：

```powershell
.\bin\ffmpeg.exe -version
```

**成功的输出示例**：
```
ffmpeg version 7.0-essentials_build
built with gcc 13.2.0 (Rev1, Built by MSYS2 project)
configuration: --enable-gpl --enable-version3 ...
libavutil      59.  8.100 / 59.  8.100
libavcodec     61.  3.100 / 61.  3.100
libavformat    61.  1.100 / 61.  1.100
...
```

如果看到版本信息，说明安装成功！✅

**如果出错**：
```
.\bin\ffmpeg.exe : 无法将".\bin\ffmpeg.exe"项识别为 cmdlet、函数、脚本文件或可运行程序的名称。
```

这说明文件不存在或路径不对，请检查：
```powershell
# 查看 bin 目录内容
dir bin\
```

应该能看到 `ffmpeg.exe` 和 `ffprobe.exe`

---

## ✅ 安装完成！

现在你可以继续设置项目环境了：

```powershell
# 运行自动设置脚本
powershell -ExecutionPolicy Bypass -File setup_windows.ps1

# 或手动设置
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python scripts\test_windows.py
```

---

## 💡 方法对比

| 特性 | 方法 1 (winget) | 方法 2 (手动) |
|------|----------------|--------------|
| 安装难度 | ⭐ 最简单 | ⭐⭐⭐ 需要手动操作 |
| 系统要求 | Windows 10 1809+ | 所有 Windows |
| 安装位置 | 系统全局 | 项目 bin 文件夹 |
| 使用范围 | 全局可用 | 仅项目可用 |
| 打包分发 | 需要额外复制 | 直接打包 |
| 版本更新 | `winget upgrade` | 手动重新下载 |
| 推荐场景 | 开发使用 | 打包分发 |

**推荐策略**：
- 开发时使用 **winget**（简单方便）
- 打包时准备 **bin 文件夹**（确保用户无需安装）

---

## ❓ 常见问题

### Q1: 我应该用哪个方法？

**推荐选择**：
- **开发使用**：方法 1 (winget) - 最简单，全局可用
- **打包分发**：方法 2 (手动) - 必须内置到 `bin` 文件夹
- **旧版 Windows**：方法 2 (手动) - winget 不可用时

### Q2: winget 提示"找不到命令"？

**原因**：系统版本太旧或未安装 App Installer

**解决**：
1. 检查 Windows 版本（需要 Windows 10 1809+ 或 Windows 11）
2. 更新 Windows：设置 → Windows 更新
3. 或使用方法 2（手动下载）

### Q3: 使用 winget 后如何打包？

**打包时必须有 bin 文件夹中的 FFmpeg**：

```powershell
# 如果使用 winget 全局安装，打包前需要复制到项目
mkdir bin

# 找到 winget 安装的 FFmpeg 位置
where.exe ffmpeg

# 通常在：C:\Program Files\Gyan\FFmpeg\bin\
# 或：%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_...\bin\

# 复制到项目
copy "C:\Program Files\Gyan\FFmpeg\bin\ffmpeg.exe" bin\
copy "C:\Program Files\Gyan\FFmpeg\bin\ffprobe.exe" bin\
```

### Q4: 下载速度太慢怎么办？（方法 2）

**解决方案**：
- 使用下载工具（IDM、迅雷等）
- 搜索"FFmpeg Windows 国内镜像"
- 或者从其他可信来源下载（确保是官方构建）

### Q2: 解压后找不到 bin 文件夹？（方法 2）

**检查**：
- 确保下载的是 `ffmpeg-release-essentials.zip`
- 完整解压，不要只解压部分文件
- 打开解压后的文件夹，`bin` 应该在第一层

### Q3: 提示"无法识别为 cmdlet"？（方法 2）

**原因**：文件不存在或路径错误

**解决**：
```powershell
# 检查文件是否存在
dir bin\

# 检查当前目录
pwd

# 确保在项目根目录
cd E:\dramas_processor
```

### Q4: 文件大小不对？（方法 2）

**正常大小**：
- `ffmpeg.exe` 约 120-140 MB
- `ffprobe.exe` 约 120-140 MB

如果文件太小（几 KB），说明下载不完整，需要重新下载。

### Q5: 杀毒软件报警？（方法 2）

**原因**：某些杀毒软件会误报 FFmpeg

**解决**：
- FFmpeg 是安全的开源软件
- 从官方网站下载是安全的
- 可以将其添加到杀毒软件白名单
- 或暂时关闭杀毒软件完成复制

### Q6: 需要管理员权限吗？

**不需要**（方法 1 和方法 2 都不需要）：
- **方法 1 (winget)**：无需管理员权限
- **方法 2 (手动)**：只是复制文件，不需要管理员权限
- 只有修改系统环境变量时才需要管理员权限（本教程不涉及）

---

## 📚 相关资源

- **FFmpeg 官方网站**：https://ffmpeg.org/
- **Windows 构建下载页**：https://www.gyan.dev/ffmpeg/builds/
- **FFmpeg 文档**：https://ffmpeg.org/documentation.html
- **Drama Processor 使用教程**：`docs/WINDOWS_使用教程.md`

---

## 💡 提示

安装完成后：

1. **运行环境测试**：
   ```powershell
   python scripts\test_windows.py
   ```

2. **查看完整使用教程**：
   ```powershell
   notepad docs\WINDOWS_使用教程.md
   ```

3. **开始处理视频**：
   ```powershell
   python -m drama_processor process "E:\短剧\你的剧集"
   ```

---

**安装遇到问题？** 查看 `docs/WINDOWS_使用教程.md` 的"常见问题"章节，或提交 Issue。

祝使用愉快！🎉
