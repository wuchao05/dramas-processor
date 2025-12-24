# NVENC 内存错误修复指南

## 错误症状

```
CreateInputBuffer failed: out of memory (10)
Error while opening encoder - maybe incorrect parameters
Cannot allocate memory
invalid argument
```

## 原因分析

### 1. NVENC 会话限制
- **消费级显卡限制**：RTX 2060/3060 等消费级显卡有 NVENC 并发会话限制
- GeForce 卡默认最多 **3 个并发 NVENC 会话**
- 如果同时运行多个编码任务或其他程序使用 NVENC，会导致资源耗尽

### 2. GPU 显存不足
- 高分辨率视频 + 高码率 + 多并发 = 显存占用高
- RTX 2060 有 6GB 显存，处理 1080p/4K 视频时可能不足

### 3. 编码参数过高
- Buffer size 设置过大
- 同时处理的帧数过多
- 分辨率和码率组合不当

### 4. 驱动或系统问题
- NVIDIA 驱动版本过旧或有 bug
- 系统内存不足
- 其他程序占用 GPU

## 快速解决方案

### 方案 1：降低并发数（最有效 ✅）

```yaml
# configs/users/xh.yaml 或其他用户配置
jobs: 1  # 改为 1，不要并发编码

# 如果之前设置了 jobs: 2 或更高，这是最常见的原因
```

### 方案 2：优化 NVENC 参数

```yaml
# configs/users/xh.yaml
video:
  hw_codec: "h264_nvenc"
  bitrate: "5000k"      # 降低码率 (从 6500k)
  max_rate: "5000k"     # 降低最大码率
  buffer_size: "6000k"  # 降低 buffer (从 8000k)
  preset: "p1"          # 使用最快 preset，减少 GPU 负担
  profile: "main"       # 从 high 改为 main
  level: "4.1"          # 从 4.2 降低到 4.1
```

### 方案 3：减小分辨率或视频长度

```yaml
# 如果处理 4K 视频，考虑降低到 1080p
canvas: "1920x1080"  # 指定输出分辨率

# 或减少每条素材时长
max_duration: 720.0  # 从 900 秒减少到 720 秒 (12 分钟)
```

### 方案 4：检查并关闭其他占用 NVENC 的程序

```powershell
# 在 PowerShell 中检查 NVENC 使用情况
nvidia-smi --query-gpu=encoder.stats.sessionCount,encoder.stats.averageFps --format=csv

# 关闭可能占用 NVENC 的程序：
# - OBS Studio
# - 其他视频编辑软件
# - 浏览器硬件加速（Chrome/Edge）
# - GeForce Experience 录制/直播
```

### 方案 5：更新 NVIDIA 驱动

```powershell
# 下载最新驱动
# https://www.nvidia.com/Download/index.aspx

# 推荐版本：>= 530.xx（2023年后的版本）
```

### 方案 6：临时使用软件编码

如果急需处理，可以暂时切换到软件编码：

```yaml
# configs/users/xh.yaml
use_hardware: false
```

或命令行：
```bash
drama-processor process /path/to/dramas --sw
```

## 推荐配置（RTX 2060 优化）

```yaml
# configs/users/xh.yaml - RTX 2060 优化配置
count: 24
use_hardware: true
fast_mode: true
filter_threads: 12  # 降低线程数
jobs: 1  # ⚠️ 关键：不要并发编码

video:
  hw_codec: "h264_nvenc"
  bitrate: "5000k"      # 降低码率
  max_rate: "5500k"
  buffer_size: "6000k"  # 降低 buffer
  preset: "p1"          # 最快 preset
  profile: "main"       # main 比 high 占用更少资源
  level: "4.1"
  hw_level: "4.1"
  pixel_format: "yuv420p"
```

## 诊断步骤

### 1. 检查当前 NVENC 使用情况

```powershell
# 查看 GPU 状态
nvidia-smi

# 查看 NVENC 编码器使用
nvidia-smi --query-gpu=name,memory.used,memory.total,encoder.stats.sessionCount,encoder.stats.averageFps --format=csv
```

### 2. 测试简单编码

```bash
# 测试最简单的 NVENC 编码
ffmpeg -f lavfi -i testsrc=duration=5:size=640x480:rate=30 \
    -c:v h264_nvenc -preset p1 -b:v 2000k \
    test_simple.mp4

# 如果失败，问题在驱动或硬件
# 如果成功，问题在参数配置
```

### 3. 测试实际文件（降低参数）

```bash
# 使用最低配置测试
ffmpeg -i input.mp4 \
    -c:v h264_nvenc \
    -preset p1 \
    -profile:v main \
    -b:v 3000k \
    -maxrate 3500k \
    -bufsize 4000k \
    output_test.mp4
```

## 常见问题

### Q: 为什么并发 (jobs > 1) 会导致问题？
**A:** 消费级 GeForce 卡的 NVENC 有并发限制（通常 2-3 个会话）。每个并发任务占用一个 NVENC 会话，超过限制就会报错。

### Q: 降低参数会影响画质吗？
**A:** 
- 码率从 6500k 降到 5000k：画质略有下降，但对短视频影响不大
- preset 从 p4 改为 p1：速度更快，画质略降
- profile 从 high 改为 main：兼容性更好，画质差异极小

### Q: 如何知道是否超过 NVENC 限制？
**A:** 
```powershell
# 运行项目前检查
nvidia-smi --query-gpu=encoder.stats.sessionCount --format=csv

# 如果显示 >= 2，说明已有程序占用 NVENC
```

### Q: RTX 2060 能同时编码几个视频？
**A:** 
- 官方限制：2-3 个并发 NVENC 会话
- 建议：`jobs: 1`，单个视频顺序处理
- 如果需要并发，考虑升级到 RTX 专业卡（无限制）或使用软件编码

### Q: 错误信息中的 "out of memory (10)" 是什么意思？
**A:** 这是 NVENC API 返回的错误码：
- 10 = `NV_ENC_ERR_OUT_OF_MEMORY`
- 表示 GPU 内存不足或 NVENC 资源耗尽

## 临时解除 NVENC 限制（仅供参考）

⚠️ **警告：修改驱动文件有风险，不推荐普通用户操作**

对于开发/测试需求，可以使用第三方补丁解除限制：
- https://github.com/keylase/nvidia-patch
- 仅适用于 Linux，Windows 需要禁用驱动签名

**更安全的方案：**
1. 使用 `jobs: 1` 避免并发
2. 或购买 RTX 专业卡（Quadro/RTX A 系列）

## 验证修复

修改配置后，运行测试：

```bash
# 1. 清理 GPU 缓存
# 关闭所有使用 GPU 的程序

# 2. 检查 NVENC 状态
nvidia-smi --query-gpu=encoder.stats.sessionCount --format=csv

# 3. 运行项目（使用优化配置）
drama-processor process /path/to/dramas --verbose

# 4. 监控 GPU 使用
# 另开终端运行：
watch -n 1 nvidia-smi
```

## 性能对比

| 配置 | 速度 | 画质 | GPU 占用 | 稳定性 |
|------|------|------|----------|--------|
| 原配置 (6500k, p4, jobs:2) | 快 | 高 | 高 | ❌ 不稳定 |
| 优化配置 (5000k, p1, jobs:1) | 很快 | 中高 | 中 | ✅ 稳定 |
| 软件编码 (libx264) | 慢 | 最高 | 低 | ✅ 最稳定 |

## 推荐方案总结

对于 RTX 2060 + WSL2/Windows 环境：

1. **首选**：`jobs: 1` + 优化参数（见上方推荐配置）
2. **备用**：软件编码（`use_hardware: false`）
3. **升级**：更强显卡（RTX 3060 Ti/4060 或专业卡）

关键是**避免并发编码**，这是导致内存错误的主要原因。

