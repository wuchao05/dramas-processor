# Drama Processor

🎬 **专业的短剧视频处理工具** - 完全兼容 `dramas_process.py` 的工程化版本

## ✨ **主要特性**

- 🎯 **100% 兼容** `dramas_process.py` 的所有功能和参数
- 🚀 **模块化架构**：VideoEncoder、TextOverlay、CoverProcessor 等独立模块
- ⚡ **智能优化**：自适应帧率、快速模式、硬件编码支持
- 🔄 **尾部视频拼接**：完整的缓存机制和增量处理
- 🖼️ **封面处理**：自动提取首帧或使用自定义封面
- 🎨 **文字叠加**：标题、底部、侧边文字的完整支持
- 🔀 **交互选择**：基于 InquirerPy 的模糊搜索多选界面
- ⚡ **并发处理**：支持多线程加速生成
- 📊 **分析模式**：不处理仅分析短剧信息
- ⚙️ **配置文件**：YAML 配置文件支持

## 🚀 **快速开始**

### 安装

```bash
cd drama_processor
pip install -r requirements.txt
pip install -e .
```

### 基础用法

```bash
# 处理当前目录的所有短剧
drama-processor process /path/to/dramas

# 生成3条素材，每条5-10分钟
drama-processor process /path/to/dramas --count 3 --min-sec 300 --max-sec 600

# 使用快速模式和软件编码
drama-processor process /path/to/dramas --fast-mode --sw --jobs 4
```

## 📋 **完整命令参数**

### 素材生成设置

- `--count INTEGER`: 每部短剧生成素材条数量（默认 1）
- `--min-sec FLOAT`: 每条素材最小时长（默认 480s=8 分钟）
- `--max-sec FLOAT`: 每条素材最大时长（默认 900s=15 分钟）
- `--date TEXT`: 文件名前缀日期，如 8.26；默认当天

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

### 尾部和封面

- `--tail-file TEXT`: 尾部引导视频路径
- `--cover-file TEXT`: 统一封面图路径（jpg/png）
- `--cover-dir TEXT`: 按剧名匹配封面图的目录

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

### 自定义文字和封面

```bash
drama-processor process /path/to/dramas \
  --footer-text "精彩短剧 每日更新" \
  --side-text "内容纯属虚构" \
  --cover-dir "/path/to/covers" \
  --tail-file "/path/to/tail.mp4"
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
drama-processor -c my-config.yaml process /path/to/dramas
```

### 配置文件示例

```yaml
# Drama Processor Configuration
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

## 🔄 **从 dramas_process.py 迁移**

### 零成本迁移

```bash
# 原来的命令
python dramas_process.py /path/to/dramas --count 3 --fast-mode

# 直接替换为
drama-processor process /path/to/dramas --count 3 --fast-mode
```

所有参数保持完全一致，无需修改现有的脚本和工作流！

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
- **CoverProcessor**: 智能封面处理
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

## 🤝 **功能对比**

详见 [FEATURE_COMPARISON.md](FEATURE_COMPARISON.md) - 与 `dramas_process.py` 的完整功能对比。

## 📄 **许可证**

MIT License

---

🎬 **Drama Processor** - 让短剧处理更专业、更高效！
