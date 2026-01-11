# Windows 版本使用文档索引

本文档汇总了所有 Windows 相关的使用指南和资源。

---

## 📚 文档导航

### 🚀 快速开始（推荐新手）

1. **[Windows 快速参考](../WINDOWS_快速参考.md)** ⭐
   - 一页纸速查表
   - 常用命令速查
   - 配置速查
   - 典型工作流

2. **[Windows 快速开始指南](WINDOWS_QUICKSTART.md)**
   - 5-10 分钟快速上手
   - 最小化安装步骤
   - 快速验证环境

3. **[FFmpeg 安装图解教程](FFMPEG_安装指南_Windows.md)** ⭐
   - 手把手教你安装 FFmpeg
   - 详细图文说明
   - 常见问题解答

### 📖 完整文档（推荐所有用户）

4. **[Windows 使用教程](WINDOWS_使用教程.md)** ⭐⭐⭐
   - 完整的安装步骤
   - 详细的配置说明
   - 所有功能的使用方法
   - Feishu 集成教程
   - 打包发布指南
   - 常见问题解答

### 🔧 技术文档（开发者）

5. **[Windows 原生迁移文档](WINDOWS_NATIVE_MIGRATION.md)**
   - 架构设计说明
   - 技术实现细节
   - 代码修改说明
   - 跨平台兼容性

---

## 🛠️ 实用工具

### 脚本工具

- **`setup_windows.ps1`** - 一键设置 Windows 环境
  ```powershell
  powershell -ExecutionPolicy Bypass -File setup_windows.ps1
  ```

- **`启动命令行.bat`** - 快速启动开发环境
  ```
  双击运行即可
  ```

- **`scripts/test_windows.py`** - 环境测试脚本
  ```powershell
  python scripts\test_windows.py
  ```

- **`packaging/build_windows.ps1`** - 打包脚本
  ```powershell
  powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1 -Version "1.0.0"
  ```

### 配置文件

- **`configs/windows_default.yaml`** - Windows 默认配置模板
- **`configs/default.yaml`** - 通用配置模板

---

## 📝 文档选择指南

### 我是新手，第一次使用
👉 **推荐阅读**:
1. [FFmpeg 安装图解教程](FFMPEG_安装指南_Windows.md) - 先安装 FFmpeg
2. [Windows 快速参考](../WINDOWS_快速参考.md) - 快速浏览
3. [Windows 使用教程](WINDOWS_使用教程.md) - 完整学习

**操作流程**:
```powershell
# 1. 安装 FFmpeg（见上面的教程）
# 下载并复制 ffmpeg.exe 和 ffprobe.exe 到 bin\ 文件夹

# 2. 运行设置脚本
powershell -ExecutionPolicy Bypass -File setup_windows.ps1

# 3. 运行测试
python scripts\test_windows.py

# 4. 开始处理
python -m drama_processor process "你的短剧目录"
```

### 我要快速上手，时间紧迫
👉 **推荐阅读**:
1. [Windows 快速开始](WINDOWS_QUICKSTART.md) - 5 分钟上手
2. [Windows 快速参考](../WINDOWS_快速参考.md) - 命令速查

**最快流程**:
```powershell
# 1. 一键设置
powershell -ExecutionPolicy Bypass -File setup_windows.ps1

# 2. 直接使用
.\venv\Scripts\activate
python -m drama_processor process "E:\短剧"
```

### 我要使用 Feishu 自动化功能
👉 **推荐阅读**:
1. [Windows 使用教程 - Feishu 功能章节](WINDOWS_使用教程.md#-feishu-功能)

**Feishu 工作流**:
```powershell
# 1. 配置飞书凭证
notepad configs\my_config.yaml

# 2. 测试连接
python -m drama_processor feishu list

# 3. 启动监听
python -m drama_processor feishu watch
```

### 我要打包分发给其他人
👉 **推荐阅读**:
1. [Windows 使用教程 - 打包发布章节](WINDOWS_使用教程.md#-打包发布)

**打包流程**:
```powershell
# 1. 准备 FFmpeg
# 确保 bin\ffmpeg.exe 存在

# 2. 打包
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1 -Version "1.0.0"

# 3. 发布
dir release_windows_v1.0.0\
```

### 我遇到了问题
👉 **推荐阅读**:
1. [Windows 使用教程 - 常见问题](WINDOWS_使用教程.md#-常见问题)
2. [Windows 快速参考 - 故障排除](../WINDOWS_快速参考.md#-故障排除)

**诊断步骤**:
```powershell
# 1. 运行测试
python scripts\test_windows.py

# 2. 启用详细日志
python -m drama_processor --log-level DEBUG process "E:\短剧"

# 3. 查看日志文件
dir logs\
```

### 我是开发者，想了解技术细节
👉 **推荐阅读**:
1. [Windows 原生迁移文档](WINDOWS_NATIVE_MIGRATION.md)
2. [项目仓库规范](../../README.md)
3. 源码注释

---

## 🎯 常见场景快速索引

| 场景 | 推荐文档 | 快速命令 |
|------|----------|----------|
| 安装 FFmpeg | [FFmpeg 安装教程](FFMPEG_安装指南_Windows.md) | 图文教程 |
| 首次安装 | [使用教程-安装步骤](WINDOWS_使用教程.md#-安装步骤) | `setup_windows.ps1` |
| 处理视频 | [快速参考-基础处理](../WINDOWS_快速参考.md#基础处理) | `drama-processor process` |
| 配置修改 | [使用教程-配置说明](WINDOWS_使用教程.md#️-配置说明) | `notepad configs\my_config.yaml` |
| 飞书集成 | [使用教程-Feishu功能](WINDOWS_使用教程.md#-feishu-功能) | `drama-processor feishu` |
| 性能优化 | [快速参考-性能优化](../WINDOWS_快速参考.md#-性能优化提示) | 配置 `h264_nvenc` |
| 问题排查 | [使用教程-常见问题](WINDOWS_使用教程.md#-常见问题) | `test_windows.py` |
| 打包发布 | [使用教程-打包发布](WINDOWS_使用教程.md#-打包发布) | `build_windows.ps1` |

---

## 📖 文档特点对比

| 文档 | 长度 | 适合人群 | 特点 |
|------|------|----------|------|
| Windows 快速参考 | 短 (1 页) | 所有人 | 速查表，命令速查 |
| Windows 快速开始 | 短 (5-10 分钟) | 新手 | 最小化步骤 |
| Windows 使用教程 | 长 (完整) | 所有人 | 详尽全面，FAQ |
| Windows 原生迁移 | 中 (技术) | 开发者 | 架构和实现 |

---

## 🔗 其他资源

### 主项目文档
- **[主 README](../../README.md)** - 项目概览和功能介绍
- **[命令使用指南](../../COMMANDS_USAGE_GUIDE.md)** - CLI 命令详细说明

### 配置文件
- **[默认配置](../../configs/default.yaml)** - 通用默认配置
- **[Windows 配置](../../configs/windows_default.yaml)** - Windows 专用配置
- **[Lite 配置](../../configs/lite.yaml)** - 精简版配置

### 示例和测试
- **[示例目录](../../examples/)** - 使用示例
- **[测试脚本](../../scripts/)** - 各种测试和工具脚本

---

## 💡 推荐学习路径

### 路径 1：快速上手路径（30 分钟）
```
1. 浏览 Windows 快速参考 (5 分钟)
   ↓
2. 运行 setup_windows.ps1 (10 分钟)
   ↓
3. 测试环境 test_windows.py (2 分钟)
   ↓
4. 处理第一个短剧 (10 分钟)
   ↓
5. 查看输出结果 (3 分钟)
```

### 路径 2：深度学习路径（2-3 小时）
```
1. 阅读 Windows 使用教程 - 安装章节 (20 分钟)
   ↓
2. 阅读 Windows 使用教程 - 配置章节 (30 分钟)
   ↓
3. 实践基础处理 (30 分钟)
   ↓
4. 阅读 Feishu 功能章节 (20 分钟)
   ↓
5. 配置和测试 Feishu (30 分钟)
   ↓
6. 阅读打包发布章节 (20 分钟)
   ↓
7. 实践打包 (30 分钟)
```

### 路径 3：开发者路径（1 小时）
```
1. 阅读 Windows 原生迁移文档 (30 分钟)
   ↓
2. 查看关键代码实现 (20 分钟)
   ↓
3. 运行测试和验证 (10 分钟)
```

---

## 🆘 获取帮助

如果文档无法解决你的问题：

1. **查看日志**:
   ```powershell
   python -m drama_processor --log-level DEBUG process "E:\短剧"
   ```

2. **运行诊断**:
   ```powershell
   python scripts\test_windows.py
   ```

3. **提交 Issue**:
   - 描述问题和错误信息
   - 附上系统信息 (Windows 版本、Python 版本等)
   - 附上相关日志

4. **查看源码**:
   - 所有代码都有详细注释
   - 可以直接阅读源码了解实现

---

**选择合适的文档，快速上手 Drama Processor！** 🚀
