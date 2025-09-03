# Drama Processor

🎬 **专业的短剧视频处理工具** - 模块化、高效的短剧批量处理解决方案

## ✨ **主要特性**

- 🎯 **功能完备**：支持所有主流短剧处理需求
- 🚀 **模块化架构**：VideoEncoder、TextOverlay 等独立模块
- ⚡ **智能优化**：自适应帧率、快速模式、硬件编码支持
- 🔄 **尾部视频拼接**：完整的缓存机制和增量处理

- 🎨 **文字叠加**：标题、底部、侧边文字的完整支持
- 🔀 **交互选择**：基于 InquirerPy 的模糊搜索多选界面
- ⚡ **并发处理**：支持多线程加速生成
- 📊 **分析模式**：不处理仅分析短剧信息
- ⚙️ **配置文件**：YAML 配置文件支持

## 🚀 **快速开始**

### 安装

```bash
cd dramas_process
pip install -r requirements.txt
pip install -e .
```

### 基础用法

```bash
# 使用默认源目录处理短剧（支持备份目录自动切换）
drama-processor process

# 处理指定目录的所有短剧
drama-processor process /path/to/dramas

# 生成3条素材，每条5-10分钟
drama-processor process --count 3 --min-sec 300 --max-sec 600

# 使用快速模式和软件编码
drama-processor process /path/to/dramas --fast-mode --sw --jobs 4

# 使用日期目录组织（会创建 "9.3导出" 目录）
drama-processor process --date "9.3" --count 2
```

## 📋 **完整命令参数**

### 素材生成设置

- `--count INTEGER`: 每部短剧生成素材条数量（默认 1）
- `--min-sec FLOAT`: 每条素材最小时长（默认 480s=8 分钟）
- `--max-sec FLOAT`: 每条素材最大时长（默认 900s=15 分钟）
- `--date TEXT`: 文件名前缀日期，如 9.3；默认当天。同时会在输出目录的上一层创建对应的日期目录

### 随机起点设置

- `--random-start / --no-random-start`: 随机起点，提升多样性（默认开启）
- `--seed INTEGER`: 随机起点种子；不传则每次运行都会不同

### 视频设置

- `--sw`: 使用软编(libx264)；默认硬编(h264_videotoolbox)
- `--fps INTEGER`: 输出帧率（默认 60）
- `--smart-fps / --no-smart-fps`: 自适应帧率（默认开启）
- `--canvas TEXT`: 参考画布：'WxH' 或 'first'；默认自动选择最常见分辨率

### 文字设置

- `--font-file TEXT`: 中文字体文件路径
- `--footer-text TEXT`: 底部居中文案
- `--side-text TEXT`: 右上竖排文案

### 尾部设置

- `--tail-file TEXT`: 尾部引导视频路径

### 选择设置

- `--include TEXT`: 仅处理指定短剧名（可多次传或用逗号分隔）
- `--exclude TEXT`: 排除指定短剧名（可多次传或用逗号分隔）
- `--full`: 全量扫描当前根目录下的所有短剧
- `--no-interactive`: 禁用交互式选择

### 性能设置

- `--jobs INTEGER`: 每部剧内的并发生成数（默认 1；建议 2~4）
- `--fast-mode`: 更快：关闭 eq/hue 随机色彩扰动
- `--filter-threads INTEGER`: 滤镜并行线程数

### 目录设置

- `--temp-dir TEXT`: 临时工作目录根（默认 /tmp）
- `--keep-temp`: 保留临时目录，便于调试
- `--out-dir TEXT`: 自定义导出目录（默认 ../导出素材）

### 尾部缓存设置

- `--tail-cache-dir TEXT`: 尾部规范化缓存目录（默认 /tmp/tails_cache）
- `--refresh-tail-cache`: 强制刷新尾部缓存

## 🎯 **使用示例**

### 基础处理

```bash
# 处理单个短剧目录
drama-processor process /path/to/dramas --include "我的短剧"

# 批量处理多个短剧
drama-processor process /path/to/dramas --include "短剧A,短剧B,短剧C"

# 排除某些短剧
drama-processor process /path/to/dramas --exclude "测试剧,废弃剧"
```

### 高级设置

```bash
# 高质量长时间素材
drama-processor process /path/to/dramas \
  --count 2 \
  --min-sec 900 \
  --max-sec 1800 \
  --fps 60 \
  --jobs 2

# 快速批量生成
drama-processor process /path/to/dramas \
  --count 10 \
  --min-sec 300 \
  --max-sec 600 \
  --fast-mode \
  --sw \
  --jobs 4
```

### 自定义文字

```bash
drama-processor process /path/to/dramas \
  --footer-text "精彩短剧 每日更新" \
  --side-text "内容纯属虚构" \
  --tail-file "assets/tail.mp4"
```

## 📊 **分析模式**

```bash
# 分析短剧基本信息
drama-processor analyze /path/to/dramas

# 输出为 JSON 格式
drama-processor analyze /path/to/dramas --format json

# 输出为 YAML 格式
drama-processor analyze /path/to/dramas --format yaml
```

## ⚙️ **配置文件**

### 生成配置文件

```bash
drama-processor config generate my-config.yaml
```

### 使用配置文件

```bash
# 使用默认配置
drama-processor -c configs/default.yaml process /path/to/dramas

# 使用自定义配置
drama-processor -c my-config.yaml process /path/to/dramas
```

### 配置文件示例

```yaml
# Drama Processor Configuration

# 源素材目录设置（支持主备切换）
default_source_dir: "/Volumes/爆爆盘/短剧剪辑/源素材视频"
backup_source_dir: "/Volumes/机械盘/短剧剪辑/源素材视频"

# 其他配置
target_fps: 60
smart_fps: true
fast_mode: false
min_duration: 480.0
max_duration: 900.0
count: 1
footer_text: "热门短剧 休闲必看"
side_text: "剧情纯属虚构 请勿模仿"
use_hardware: true
jobs: 1
output_dir: "../导出素材"
tail_cache_dir: "/tmp/tails_cache"
```

## 🗂️ **智能源目录功能**

从此版本开始，处理器支持智能的源素材目录功能，包括默认目录和备份目录自动切换：

### 自动使用默认目录

```bash
# 不指定源目录时，自动使用配置的默认目录
drama-processor process

# 等同于：
drama-processor process /Volumes/爆爆盘/短剧剪辑/源素材视频
```

### 备份目录自动切换

当主目录不存在时，系统会自动切换到备份目录：

```bash
# 如果主目录存在，直接使用
drama-processor process
# 输出示例：
# 导出目录: /Volumes/爆爆盘/短剧剪辑/导出素材

# 如果 /Volumes/爆爆盘/短剧剪辑/源素材视频 不存在
# 会自动使用 /Volumes/机械盘/短剧剪辑/源素材视频
drama-processor process
# 输出示例：
# 使用备份源素材目录: /Volumes/机械盘/短剧剪辑/源素材视频
# (主目录不存在: /Volumes/爆爆盘/短剧剪辑/源素材视频)
# 调整导出目录为: /Volumes/机械盘/短剧剪辑/导出素材
```

### 智能导出目录

- 使用**主目录**时：导出到 `/Volumes/爆爆盘/短剧剪辑/导出素材`
- 使用**备份目录**时：导出到 `/Volumes/机械盘/短剧剪辑/导出素材`
- 使用**日期导出**时：在对应基础目录下创建 `{日期}导出` 目录（如 `/Volumes/爆爆盘/短剧剪辑/9.3导出`）

### 配置默认目录

在 `configs/default.yaml` 中修改：

```yaml
default_source_dir: "/你的/默认/源素材/目录路径"
```

### 优先级说明

1. **命令行指定目录**：最高优先级
2. **配置文件默认目录**：次优先级
3. **错误提示**：如果都不存在，会给出错误信息

### 使用场景

- 😊 **日常使用**：无需每次输入完整路径
- 🔄 **批处理脚本**：简化命令行参数
- ⚙️ **团队协作**：统一默认目录配置

## 🧪 **测试**

```bash
# 运行集成测试
python test_integration.py

# 查看帮助信息
drama-processor --help
drama-processor process --help
```

## 🏗️ **架构特性**

- **VideoEncoder**: 完整的视频编码和处理流水线
- **TextOverlay**: 专业的文字叠加系统

- **Interactive**: 用户友好的交互界面
- **模块化设计**: 易于扩展和维护
- **完整测试**: 集成测试验证功能

## 📝 **日志系统**

```bash
# 调试模式
drama-processor --log-level DEBUG process /path/to/dramas

# 保存日志到文件
drama-processor --log-file processing.log process /path/to/dramas

# 禁用富文本格式
drama-processor --no-rich process /path/to/dramas
```

## 🎯 **性能优化建议**

1. **使用硬件编码**（默认）：`h264_videotoolbox`
2. **启用快速模式**：`--fast-mode`
3. **合理设置并发**：`--jobs 2-4`
4. **调整滤镜线程**：`--filter-threads 4`
5. **使用智能帧率**：`--smart-fps`（默认开启）

## 🤝 **功能特性**

详见 [FEATURE_COMPARISON.md](docs/FEATURE_COMPARISON.md) - 完整的功能特性说明。

## 📄 **许可证**

MIT License

---

🎬 **Drama Processor** - 让短剧处理更专业、更高效！
