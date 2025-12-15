# WSL2 硬件编码配置与调试指南

## 前置条件检查

### 1. 确认 Windows 版本

WSL2 的 GPU 支持需要：

- Windows 11
- 或 Windows 10 版本 21H2 (build 19044) 或更高

```powershell
# 在 PowerShell 中检查 Windows 版本
winver

# 或
[System.Environment]::OSVersion.Version
```

### 2. 确认 WSL2 已安装

```powershell
# 查看 WSL 版本
wsl --version

# 查看当前发行版
wsl --list --verbose

# 确保使用 WSL2（VERSION 列应该是 2）
```

如果是 WSL1，需要转换：

```powershell
# 转换为 WSL2
wsl --set-version <发行版名称> 2

# 设置默认版本
wsl --set-default-version 2
```

## 步骤 1：安装 NVIDIA CUDA on WSL 驱动

### 在 Windows 中安装驱动

1. **卸载旧的 NVIDIA 驱动**（如果有）

   - 控制面板 → 程序和功能 → 卸载 NVIDIA 驱动

2. **下载 NVIDIA CUDA on WSL 驱动**

   - 访问：https://developer.nvidia.com/cuda/wsl
   - 或：https://www.nvidia.com/Download/index.aspx
   - 选择 `NVIDIA CUDA on WSL` 或支持 WSL 的 Game Ready 驱动（>=470.76）

3. **安装驱动**

   - 运行下载的安装程序
   - 选择"自定义安装"
   - 确保勾选所有组件

4. **重启电脑**

5. **验证安装**
   ```powershell
   # 在 PowerShell 中
   nvidia-smi
   ```

## 步骤 2：在 WSL2 中验证 GPU 访问

```bash
# 在 WSL2 中运行
nvidia-smi
```

**预期输出：**

```
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 535.xx.xx    Driver Version: 535.xx.xx    CUDA Version: 12.2     |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  NVIDIA GeForce ...  Off  | 00000000:01:00.0 On |                  N/A |
| 30%   45C    P8    15W / 175W |    500MiB /  6144MiB |      2%      Default |
+-------------------------------+----------------------+----------------------+
```

**❌ 如果失败：**

```bash
# 错误：nvidia-smi: command not found
# 或：Failed to initialize NVML

# 解决方法：
# 1. 确认 Windows 驱动正确安装
# 2. 重启 WSL：
```

```powershell
# 在 PowerShell 中
wsl --shutdown
wsl
```

## 步骤 3：安装支持 NVENC 的 FFmpeg

### 方法 A：使用预编译版本（推荐）

```bash
# 1. 添加 PPA（Ubuntu）
sudo add-apt-repository ppa:savoury1/ffmpeg4
sudo apt update

# 2. 安装 FFmpeg
sudo apt install ffmpeg

# 3. 验证 NVENC 支持
ffmpeg -encoders 2>&1 | grep nvenc
```

**预期输出：**

```
 V..... h264_nvenc           NVIDIA NVENC H.264 encoder (codec h264)
 V..... hevc_nvenc           NVIDIA NVENC hevc encoder (codec hevc)
```

### 方法 B：从源码编译（完整支持）

```bash
#!/bin/bash

# 安装依赖
sudo apt update
sudo apt install -y \
    build-essential \
    yasm \
    cmake \
    git \
    pkg-config \
    libnuma-dev \
    libx264-dev \
    libx265-dev \
    libvpx-dev \
    libfdk-aac-dev \
    libmp3lame-dev \
    libopus-dev \
    libaom-dev

# 克隆 FFmpeg
cd /tmp
git clone https://git.ffmpeg.org/ffmpeg.git
cd ffmpeg

# 配置编译选项（包含 NVENC）
./configure \
    --enable-gpl \
    --enable-version3 \
    --enable-nonfree \
    --enable-cuda-nvcc \
    --enable-libnpp \
    --enable-nvenc \
    --enable-libx264 \
    --enable-libx265 \
    --enable-libvpx \
    --enable-libfdk-aac \
    --enable-libmp3lame \
    --enable-libopus \
    --enable-libaom \
    --extra-cflags=-I/usr/local/cuda/include \
    --extra-ldflags=-L/usr/local/cuda/lib64

# 编译（需要较长时间）
make -j$(nproc)

# 安装
sudo make install

# 更新动态链接库
sudo ldconfig

# 验证
ffmpeg -version
ffmpeg -encoders | grep nvenc
```

## 步骤 4：测试 NVENC 编码器

### 快速测试

```bash
# 创建测试脚本
cat > ~/test_nvenc.sh << 'EOF'
#!/bin/bash
echo "=========================================="
echo "NVENC 硬件编码器测试"
echo "=========================================="
echo ""

# 1. 检查 GPU
echo "1️⃣ 检查 GPU 状态："
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
echo ""

# 2. 检查 FFmpeg NVENC 支持
echo "2️⃣ 检查 FFmpeg NVENC 支持："
if ffmpeg -encoders 2>&1 | grep -q "h264_nvenc"; then
    echo "✅ FFmpeg 支持 h264_nvenc"
else
    echo "❌ FFmpeg 不支持 h264_nvenc"
    exit 1
fi
echo ""

# 3. 测试 NVENC 编码
echo "3️⃣ 测试 NVENC 实际编码（10秒测试）："
ffmpeg -y -f lavfi -i testsrc=duration=10:size=1920x1080:rate=30 \
    -c:v h264_nvenc -preset fast -b:v 5000k \
    /tmp/nvenc_test.mp4 2>&1 | grep -E "(encoder|fps|speed|error|failed)"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ NVENC 编码成功！"
    ls -lh /tmp/nvenc_test.mp4
    rm -f /tmp/nvenc_test.mp4
else
    echo ""
    echo "❌ NVENC 编码失败"
    exit 1
fi

echo ""
echo "=========================================="
echo "测试完成 - NVENC 可用！"
echo "=========================================="
EOF

chmod +x ~/test_nvenc.sh
bash ~/test_nvenc.sh
```

### 详细调试测试

```bash
# 带详细错误信息的测试
ffmpeg -loglevel debug -f lavfi -i testsrc=duration=1:size=320x240:rate=1 \
    -c:v h264_nvenc -t 0.1 -f null - 2>&1 | tee /tmp/nvenc_debug.log

# 查看错误日志
cat /tmp/nvenc_debug.log
```

## 常见错误及解决方案

### 错误 1：`nvidia-smi: command not found`

**原因：** WSL2 无法访问 GPU

**解决：**

1. 确认 Windows 驱动版本 >= 470.76
2. 重启 WSL：
   ```powershell
   wsl --shutdown
   ```
3. 重新启动 WSL 并测试

### 错误 2：`Unknown encoder 'h264_nvenc'`

**原因：** FFmpeg 未编译 NVENC 支持

**解决：**

```bash
# 检查 FFmpeg 编译配置
ffmpeg -version | grep configuration

# 应包含：--enable-nvenc 或 --enable-cuda-nvcc

# 如果没有，需要重新编译 FFmpeg（参考方法 B）
```

### 错误 3：`Cannot load nvcuda.dll` 或 `CUDA library not found`

**原因：** CUDA 库路径未设置

**解决：**

```bash
# 添加到 ~/.bashrc 或 ~/.zshrc
echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

### 错误 4：`Driver does not support the required NVENC API version`

**原因：** 驱动版本过旧

**解决：**

1. 更新 Windows 中的 NVIDIA 驱动
2. 确保版本 >= 470.76
3. 重启电脑
4. 重启 WSL

### 错误 5：`encoder setup failed` 或 `No NVENC capable devices found`

**原因：** GPU 被其他程序占用或不支持 NVENC

**解决：**

```bash
# 1. 检查 GPU 占用
nvidia-smi

# 2. 确认显卡支持 NVENC
# RTX 系列、GTX 16xx/20xx/30xx 系列均支持
# 参考：https://developer.nvidia.com/video-encode-and-decode-gpu-support-matrix

# 3. 检查 NVENC 会话
nvidia-smi --query-gpu=encoder.stats.sessionCount --format=csv

# 4. 尝试其他 preset
ffmpeg -f lavfi -i testsrc -c:v h264_nvenc -preset p1 -f null -
```

## 步骤 5：配置项目使用硬件编码

编辑用户配置文件：

```yaml
# configs/users/xh.yaml
use_hardware: true
fast_mode: true
filter_threads: 16

video:
  hw_codec: "h264_nvenc" # 明确指定 nvenc
  bitrate: "6500k"
  max_rate: "6500k"
  buffer_size: "8000k"
  preset: "p4" # NVENC preset: p1-p7 (p4=medium, p7=slow/high quality)
  profile: "high"
  level: "4.2"
```

## 步骤 6：验证项目中的硬件编码

```bash
# 运行项目并查看日志
drama-processor process /mnt/d/短剧剪辑/源素材视频 --verbose

# 查找关键日志：
# ✅ 检测到可用的硬件编码器: h264_nvenc
# 或
# ⚠️ 硬件编码器 h264_nvenc 不可用
```

## 性能监控

### 实时监控 GPU 使用

```bash
# 监控 GPU 利用率（每秒刷新）
watch -n 1 nvidia-smi

# 或使用更详细的监控
nvidia-smi dmon -s u -d 1
```

### 预期性能指标

| 指标         | 软件编码    | 硬件编码 (NVENC) |
| ------------ | ----------- | ---------------- |
| 编码速度     | 0.5-1x 实时 | 3-5x 实时        |
| CPU 使用     | 80-100%     | 10-20%           |
| GPU 使用     | 0%          | 60-80%           |
| 编码器利用率 | N/A         | 80-100%          |

## 调试技巧

### 1. 逐步验证

```bash
# Step 1: GPU 可见
nvidia-smi

# Step 2: FFmpeg 支持
ffmpeg -encoders | grep nvenc

# Step 3: 简单测试
ffmpeg -f lavfi -i testsrc -c:v h264_nvenc -t 1 -f null -

# Step 4: 实际文件
ffmpeg -i input.mp4 -c:v h264_nvenc output.mp4

# Step 5: 运行项目
drama-processor process ...
```

### 2. 启用详细日志

```bash
# 项目日志
drama-processor process ... --verbose --log-level DEBUG

# FFmpeg 日志
export FFREPORT=file=/tmp/ffmpeg-report.log:level=32
drama-processor process ...
cat /tmp/ffmpeg-report.log
```

### 3. 对比测试

```bash
# 测试软件编码速度
time ffmpeg -i input.mp4 -c:v libx264 -preset veryfast output_sw.mp4

# 测试硬件编码速度
time ffmpeg -i input.mp4 -c:v h264_nvenc -preset p4 output_hw.mp4

# 对比结果
```

## 优化建议

### NVENC Preset 选择

```yaml
# 速度优先（推荐）
preset: 'p1'  # 最快，画质略低

# 平衡（推荐）
preset: 'p4'  # 中等速度，中等画质

# 画质优先
preset: 'p7'  # 最慢，画质最好
```

### NVENC 专用参数

```yaml
video:
  hw_codec: "h264_nvenc"
  preset: "p4"
  profile: "high"
  level: "4.2"
  # NVENC 专用参数（可选）
  # -rc vbr         # 码率控制：cbr/vbr/vbr_hq
  # -2pass 1        # 双通道编码
  # -spatial-aq 1   # 空间自适应量化
  # -temporal-aq 1  # 时间自适应量化
```

## 故障排查清单

- [ ] Windows 版本 >= 21H2 (build 19044)
- [ ] WSL 版本 2
- [ ] NVIDIA 驱动 >= 470.76
- [ ] `nvidia-smi` 在 WSL2 中可用
- [ ] FFmpeg 支持 NVENC (`ffmpeg -encoders | grep nvenc`)
- [ ] NVENC 测试成功 (`test_nvenc.sh`)
- [ ] 项目配置 `use_hardware: true`
- [ ] 项目日志显示 "检测到可用的硬件编码器"

## 参考资源

- [NVIDIA CUDA on WSL 文档](https://docs.nvidia.com/cuda/wsl-user-guide/)
- [FFmpeg NVENC 文档](https://trac.ffmpeg.org/wiki/HWAccelIntro)
- [NVENC 视频编码器支持矩阵](https://developer.nvidia.com/video-encode-and-decode-gpu-support-matrix)
- [FFmpeg 编译指南](https://trac.ffmpeg.org/wiki/CompilationGuide/Ubuntu)

## 需要帮助？

如果遇到问题，请提供以下信息：

```bash
# 收集诊断信息
cat > ~/diagnostic_info.sh << 'EOF'
#!/bin/bash
echo "=== Windows 版本 ==="
cmd.exe /c ver

echo -e "\n=== WSL 版本 ==="
wsl.exe --version

echo -e "\n=== GPU 信息 ==="
nvidia-smi

echo -e "\n=== FFmpeg 版本 ==="
ffmpeg -version | head -n 1

echo -e "\n=== FFmpeg NVENC 支持 ==="
ffmpeg -encoders 2>&1 | grep nvenc

echo -e "\n=== NVENC 测试 ==="
ffmpeg -f lavfi -i testsrc -c:v h264_nvenc -t 0.1 -f null - 2>&1 | tail -n 20
EOF

chmod +x ~/diagnostic_info.sh
bash ~/diagnostic_info.sh > ~/diagnostic_report.txt
cat ~/diagnostic_report.txt
```

将 `diagnostic_report.txt` 的内容提供给我，我会帮你分析问题。
