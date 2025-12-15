# 硬件编码器故障排查指南

## 问题描述

在 WSL 环境中，即使有 NVIDIA 显卡（如 RTX 2060），程序仍然无法检测到 NVENC 硬件编码器，显示：

```
硬件编码器 h264_nvenc 不可用，继续检测...
硬件编码器 h264_qsv 不可用，继续检测...
硬件编码器 h264_vaapi 不可用，继续检测...
```

## 原因分析

在 **WSL (Windows Subsystem for Linux)** 环境中，硬件编码器无法使用的主要原因：

### 1. WSL 不支持 GPU 直通（WSL1）
- WSL1 是一个兼容层，不支持直接访问 GPU 硬件
- NVIDIA NVENC 等硬件编码器依赖于直接 GPU 访问

### 2. WSL2 需要特殊配置
- WSL2 理论上支持 GPU 访问（WSLg），但需要：
  - Windows 11 或 Windows 10 20H2+ 
  - NVIDIA CUDA on WSL 驱动
  - 特定的 FFmpeg 编译版本

### 3. FFmpeg 编译问题
- WSL 中的 FFmpeg 可能未编译 NVENC 支持
- 即使编译了，也需要正确的运行时库

## 诊断步骤

运行诊断脚本检查问题：

```bash
# 在 WSL 中运行
bash /tmp/check_hw_encoder.sh
```

或手动检查：

```bash
# 1. 检查 FFmpeg 是否支持 NVENC
ffmpeg -encoders 2>&1 | grep nvenc

# 2. 检查 NVIDIA 驱动（WSL2）
nvidia-smi

# 3. 测试 NVENC
ffmpeg -y -f lavfi -i testsrc=duration=1:size=320x240:rate=1 \
    -c:v h264_nvenc -t 0.1 -f null -
```

## 解决方案

### 方案 1：使用软件编码（推荐 ✅）

**优点：**
- 无需额外配置
- 兼容性最好
- 在 WSL 中稳定可靠

**缺点：**
- 编码速度较慢
- CPU 占用高

**配置方法：**

1. 在配置文件中禁用硬件编码：

```yaml
# configs/default.yaml 或用户配置文件
use_hardware: false

video:
  sw_codec: 'libx264'
  soft_crf: '24'
  preset: 'veryfast'  # 或 'faster', 'fast'
```

2. 或使用命令行参数：

```bash
drama-processor process /path/to/dramas --sw
```

### 方案 2：在 Windows 原生环境运行（推荐 ✅✅）

**优点：**
- 完全支持硬件编码
- 编码速度快 3-5 倍
- GPU 利用率高

**步骤：**

1. 在 Windows PowerShell 中安装 Python：
   ```powershell
   # 下载并安装 Python 3.8+
   # https://www.python.org/downloads/windows/
   ```

2. 安装完整版 FFmpeg（包含 NVENC）：
   ```powershell
   # 下载 FFmpeg 完整版
   # https://github.com/BtbN/FFmpeg-Builds/releases
   # 选择 ffmpeg-n*-win64-gpl.zip
   
   # 解压并添加到 PATH
   ```

3. 安装项目：
   ```powershell
   cd D:\dramas-processor
   pip install -e .
   ```

4. 运行：
   ```powershell
   drama-processor process "D:\短剧剪辑\源素材视频"
   ```

### 方案 3：升级到 WSL2 + CUDA on WSL（复杂 ⚠️）

**适用场景：** 必须在 WSL 中运行且需要硬件加速

**步骤：**

1. 升级到 WSL2：
   ```powershell
   # 在 PowerShell (管理员) 中运行
   wsl --set-default-version 2
   wsl --update
   ```

2. 安装 CUDA on WSL 驱动：
   - 下载：https://developer.nvidia.com/cuda/wsl
   - 安装 NVIDIA CUDA on WSL 驱动（不是标准驱动）

3. 在 WSL 中编译支持 CUDA 的 FFmpeg：
   ```bash
   # 这需要从源码编译 FFmpeg，非常复杂
   # 参考：https://trac.ffmpeg.org/wiki/CompilationGuide/Ubuntu
   ```

4. 验证：
   ```bash
   nvidia-smi
   ffmpeg -encoders | grep nvenc
   ```

## 性能对比

| 方案 | 编码速度 | CPU 占用 | GPU 占用 | 复杂度 |
|------|----------|----------|----------|--------|
| 软件编码 (WSL) | 1x | 80-100% | 0% | ⭐ 简单 |
| 硬件编码 (Windows) | 3-5x | 10-20% | 60-80% | ⭐⭐ 中等 |
| 硬件编码 (WSL2+CUDA) | 3-5x | 10-20% | 60-80% | ⭐⭐⭐⭐⭐ 复杂 |

## 推荐配置

### WSL 环境（当前）

```yaml
# configs/default.yaml
use_hardware: false
fast_mode: true
filter_threads: 16

video:
  sw_codec: 'libx264'
  soft_crf: '24'
  preset: 'veryfast'  # 提升编码速度
  bitrate: '6500k'
```

### Windows 原生环境

```yaml
# configs/default.yaml
use_hardware: true
fast_mode: true
filter_threads: 16

video:
  hw_codec: 'auto'  # 自动检测 h264_nvenc
  bitrate: '6500k'
```

## 常见问题

### Q: 为什么 WSL 中看不到显卡？
**A:** WSL1 完全不支持 GPU。WSL2 需要特殊的 CUDA on WSL 驱动，且只在 Windows 11 和某些 Windows 10 版本上支持。

### Q: 软件编码是否会影响画质？
**A:** 不会。软件编码（libx264）的画质通常比硬件编码更好，只是速度较慢。

### Q: 如何提升软件编码速度？
**A:** 
1. 使用更快的 preset：`veryfast` 或 `faster`
2. 启用快速模式：`fast_mode: true`
3. 增加 filter 线程数：`filter_threads: 16`
4. 降低 CRF 值（会增加文件大小）

### Q: 多久能处理完一部剧？
**A:** 
- 硬件编码：10-15 分钟/剧
- 软件编码（veryfast）：30-45 分钟/剧
- 软件编码（medium）：60-90 分钟/剧

## 验证配置

运行测试确认当前使用的编码方式：

```bash
# 查看详细日志
drama-processor process /path/to/dramas --verbose

# 日志中会显示：
# ✅ 检测到可用的硬件编码器: h264_nvenc  (硬件编码)
# 或
# ⚠️ 未检测到可用的硬件编码器，将使用软件编码  (软件编码)
```

## 总结

对于 **WSL 环境 + NVIDIA 显卡** 的情况：

1. **最简单**：使用软件编码（`use_hardware: false`）
2. **最高效**：切换到 Windows 原生环境运行
3. **最复杂**：配置 WSL2 + CUDA（不推荐，性价比低）

建议使用方案 1 或方案 2，避免在 WSL 中折腾硬件编码。

