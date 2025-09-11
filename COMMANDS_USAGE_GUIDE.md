# 短剧处理器命令使用指南

本指南详细说明了短剧处理器的所有命令、参数和功能实现。

## 目录

- [命令概览](#命令概览)
- [1. drama-processor process](#1-drama-processor-process)
- [2. fscut run](#2-fscut-run)
- [3. fscut select](#3-fscut-select)
- [AI 功能详解](#ai功能详解)
- [参数详解](#参数详解)
- [使用示例](#使用示例)

## 命令概览

| 命令                      | 功能         | 数据源   | 特点                               |
| ------------------------- | ------------ | -------- | ---------------------------------- |
| `drama-processor process` | 基础剪辑命令 | 本地目录 | 支持交互选择、全量处理             |
| `fscut run`               | 飞书自动剪辑 | 飞书表格 | **推荐** 全自动处理，无需人工干预  |
| `fscut select`            | 飞书选择剪辑 | 飞书表格 | 交互式选择特定剧目，适合精细化控制 |

## 1. drama-processor process

**基础的短剧剪辑命令，从本地目录处理剧集。**

### 基本语法

```bash
drama-processor process [ROOT_DIR] [OPTIONS]
```

### 核心参数

#### 素材生成设置

- `--count INTEGER`: 每部短剧生成素材条数量（默认 10）
- `--min-sec FLOAT`: 每条素材最小时长（默认 480s=8 分钟）
- `--max-sec FLOAT`: 每条素材最大时长（默认 900s=15 分钟）
- `--date STRING`: 文件名前缀日期，如 8.26；默认当天

#### 随机起点设置

- `--random-start/--no-random-start`: 随机起点，提升多样性（默认开启）
- `--seed INTEGER`: 随机起点种子；不传则每次运行都会不同

#### 视频设置

- `--sw`: 使用软编(libx264)；默认硬编(h264_videotoolbox)
- `--fps INTEGER`: 输出帧率（默认 60）
- `--smart-fps/--no-smart-fps`: 自适应帧率（默认开启）
- `--canvas STRING`: 参考画布：'WxH' 或 'first'；默认自动选择

#### 文字设置

- `--font-file STRING`: 中文字体文件路径
- `--footer-text STRING`: 底部居中文案（默认"热门短剧 休闲必看"）
- `--side-text STRING`: 右上竖排文案（默认"剧情纯属虚构 请勿模仿"）

#### 尾部设置

- `--tail-file STRING`: 尾部引导视频路径

#### 选择设置

- `--include STRING`: 仅处理指定短剧名（可多次使用）
- `--exclude STRING`: 排除指定短剧名（可多次使用）
- `--full`: 全量扫描当前根目录下的所有短剧
- `--no-interactive`: 禁用交互式选择

#### 性能设置

- `--jobs INTEGER`: 每部剧内的并发生成数（默认 1；建议 2~4）
- `--temp-dir STRING`: 临时工作目录根（默认 /tmp）
- `--keep-temp`: 保留临时目录，便于调试
- `--out-dir STRING`: 自定义导出目录（默认 ../导出素材）

#### 缓存设置

- `--tail-cache-dir STRING`: 尾部规范化缓存目录
- `--refresh-tail-cache`: 强制刷新尾部缓存

#### 处理优化

- `--fast-mode`: 更快：关闭随机色彩扰动，仅保留基本处理
- `--filter-threads INTEGER`: 滤镜并行线程数（默认=CPU 核数一半，至少 2）
- `--verbose`: 详细日志：显示完整的 FFmpeg 命令

#### AI 增强设置

- `--ai-scene-detection`: 启用 AI 智能场景检测，自动选择最佳剪辑点
- `--enable-deduplication`: 启用剪辑点去重功能，避免生成重复素材

#### 飞书通知设置

- `--feishu-webhook STRING`: 飞书群通知 webhook 地址
- `--no-feishu-notification`: 禁用飞书群通知

### 功能实现

```python
def process_command(ctx, root_dir, ...):
    """处理本地目录中的短剧文件"""

    # 1. 配置初始化
    config = ProcessingConfig()
    # 设置所有参数到config对象

    # 2. 项目扫描和选择
    if full:
        # 全量扫描所有短剧
        projects = scan_all_projects(root_dir)
    elif include or exclude:
        # 根据包含/排除规则筛选
        projects = filter_projects(include, exclude)
    elif not no_interactive:
        # 交互式选择
        projects = interactive_select_projects()

    # 3. 处理器初始化
    if ai_scene_detection:
        processor = AIEnhancedProcessor(config, enable_ai_scene_detection=True)
    else:
        processor = DramaProcessor(config)

    # 4. 批量处理
    for project in projects:
        processor.process_project(project)
```

## 2. fscut run

**从飞书表格自动获取待剪辑剧目并处理，自动更新状态。**

### 基本语法

```bash
fscut run [OPTIONS] [ROOT_DIR]
```

### 特有参数

- `--status STRING`: 筛选状态（默认："待剪辑"）

### 功能实现

```python
def feishu_run(ctx, status, ...):
    """一键查询飞书表格中的剧目并自动剪辑"""

    # 1. 飞书客户端初始化
    client = FeishuClient(config.feishu)

    # 2. 获取待处理剧目
    drama_info = client.get_pending_dramas_with_dates(
        status_filter=status,
        date_filter=feishu_date_filter
    )

    # 3. 状态更新回调
    def status_update_callback(drama_name, new_status):
        record_id = drama_records[drama_name]
        client.update_record_status(record_id, new_status)

    # 4. 处理器创建（带状态回调）
    if ai_scene_detection:
        processor = AIEnhancedProcessor(config, status_callback=status_update_callback)
    else:
        processor = DramaProcessor(config, status_callback=status_update_callback)

    # 5. 自动处理所有剧目
    for drama_name in dramas:
        # 自动更新状态为"剪辑中"
        processor.process_project(project)
        # 完成后自动更新状态为"待上传"
```

## 3. fscut select

**从飞书表格选择特定剧目进行剪辑，支持交互式选择。**

### 基本语法

```bash
fscut select [OPTIONS] [ROOT_DIR]
```

### 特有参数

- `--status STRING`: 筛选状态（默认："待剪辑"）

### 功能实现

```python
def feishu_select(ctx, status, ...):
    """从飞书表格选择特定剧目进行剪辑"""

    # 1. 获取剧目列表
    drama_info = client.get_pending_dramas_with_dates(status_filter=status)

    # 2. 交互式选择
    click.echo("🎭 可用剧目列表：")
    for i, (drama, info) in enumerate(drama_info.items(), 1):
        click.echo(f"{i:2d}. {drama}")

    # 3. 用户选择处理
    selected_indices = click.prompt("请选择要处理的剧目").split(',')
    selected_dramas = [list(drama_info.keys())[int(i)-1] for i in selected_indices]

    # 4. 批量处理选中的剧目
    for drama_name in selected_dramas:
        processor.process_project(project)
```

## AI 功能详解

### 1. AI 智能场景检测 (`--ai-scene-detection`)

**功能**：使用 AI 算法自动识别视频中的场景变化，选择最佳剪辑点。

**实现原理**：

- 使用深度学习模型分析视频帧
- 识别场景转换、对话开始/结束等关键时刻
- 计算每个候选剪辑点的质量评分
- 自动选择评分最高的剪辑点

**使用示例**：

```bash
# 启用AI场景检测
drama-processor process /path/to/dramas --ai-scene-detection

# 结合其他参数
fscut run --ai-scene-detection --count 5 --min-sec 600
```

**处理器创建**：

```python
if ai_scene_detection:
    click.echo("🤖 启用AI智能场景处理...")
    click.echo("  ✅ AI场景检测：自动识别场景变化")
    click.echo("  ✅ 智能剪辑点：选择最佳片段")

    processor = AIEnhancedProcessor(
        config,
        enable_ai_scene_detection=True,
        status_callback=callback
    )
else:
    processor = DramaProcessor(config, status_callback=callback)
```

### 2. 剪辑点去重功能 (`--enable-deduplication`)

**功能**：避免在多次运行时生成重复的素材内容。

**工作原理**：

- **持久化存储**：将已使用的剪辑点保存到文件
- **排除半径**：新剪辑点与已使用剪辑点距离小于 30 秒时被跳过
- **智能回退**：当 AI 剪辑点全部被使用时，自动回退到随机生成

**存储位置**：`{temp_dir}/cut_points_history/{hash}_{drama_name}.json`

**使用示例**：

```bash
# 启用去重功能
drama-processor process /path/to/dramas --enable-deduplication

# 同时启用AI检测和去重
fscut sync --ai-scene-detection --enable-deduplication --auto-update
```

**实现细节**：

```python
class AIEnhancedProcessor(DramaProcessor):
    def __init__(self, config, enable_ai_scene_detection=True):
        # 去重配置
        self.enable_deduplication = config.enable_deduplication
        self.used_cut_points = []  # 已使用的剪辑点
        self.exclusion_radius = 30.0  # 排除半径30秒

    def _is_cut_point_valid(self, episode_idx, timestamp):
        """检查剪辑点是否与已使用的点冲突"""
        for used_ep_idx, used_timestamp in self.used_cut_points:
            if (used_ep_idx == episode_idx and
                abs(used_timestamp - timestamp) < self.exclusion_radius):
                return False
        return True
```

## 参数详解

### 素材生成参数

| 参数        | 类型  | 默认值 | 说明                   |
| ----------- | ----- | ------ | ---------------------- |
| `--count`   | int   | 10     | 每部短剧生成的素材条数 |
| `--min-sec` | float | 480    | 每条素材最小时长（秒） |
| `--max-sec` | float | 900    | 每条素材最大时长（秒） |
| `--date`    | str   | None   | 文件名日期前缀         |

### 视频处理参数

| 参数          | 类型 | 默认值 | 说明                  |
| ------------- | ---- | ------ | --------------------- |
| `--sw`        | flag | False  | 使用软编码（libx264） |
| `--fps`       | int  | 60     | 输出视频帧率          |
| `--smart-fps` | flag | True   | 自适应帧率调整        |
| `--canvas`    | str  | None   | 画布尺寸设置          |

### 性能优化参数

| 参数               | 类型 | 默认值     | 说明                     |
| ------------------ | ---- | ---------- | ------------------------ |
| `--jobs`           | int  | 1          | 并发处理数量             |
| `--fast-mode`      | flag | False      | 快速模式（关闭色彩扰动） |
| `--filter-threads` | int  | CPU 核数/2 | 滤镜处理线程数           |

### AI 增强参数

| 参数                     | 类型 | 默认值 | 说明             |
| ------------------------ | ---- | ------ | ---------------- |
| `--ai-scene-detection`   | flag | False  | 启用 AI 场景检测 |
| `--enable-deduplication` | flag | False  | 启用剪辑点去重   |

## 使用示例

### 基础使用

```bash
# 最简单的使用方式
drama-processor process /path/to/dramas

# 指定输出数量和时长
drama-processor process /path/to/dramas --count 5 --min-sec 600 --max-sec 1200
```

### 高级功能

```bash
# 启用AI功能
drama-processor process /path/to/dramas \
  --ai-scene-detection \
  --enable-deduplication \
  --count 8 \
  --jobs 3

# 快速处理模式
drama-processor process /path/to/dramas \
  --fast-mode \
  --jobs 4 \
  --filter-threads 8 \
  --verbose
```

### 飞书集成

```bash
# 自动处理飞书表格中的待剪辑剧目
fscut run --ai-scene-detection --enable-deduplication

# 选择性处理特定剧目
fscut select --status "待剪辑" --count 3

# 预览待处理剧目（替代原 sync --dry-run）
fscut select --status "待剪辑"  # 查看列表后取消

# 全自动处理（替代原 sync --auto-update）
fscut run --ai-scene-detection --enable-deduplication
```

### 完整配置示例

```bash
# 生产环境推荐配置（使用 fscut run）
fscut run \
  --status "待剪辑" \
  --ai-scene-detection \
  --enable-deduplication \
  --count 10 \
  --min-sec 480 \
  --max-sec 900 \
  --jobs 3 \
  --smart-fps \
  --fast-mode \
  --temp-dir /tmp/drama_work \
  --out-dir ./output \
  --verbose
```

## 配置文件支持

所有命令都支持通过配置文件设置默认参数，配置文件位置：

- `~/.drama_processor/config.yaml`
- 项目目录下的 `config.yaml`

示例配置：

```yaml
# 基础设置
count: 10
min_sec: 480
max_sec: 900

# AI功能
enable_deduplication: true

# 性能设置
jobs: 3
fast_mode: true
filter_threads: 8

# 飞书配置
feishu:
  app_id: "your_app_id"
  app_secret: "your_app_secret"
  table_id: "your_table_id"
```

## 注意事项

1. **AI 功能需要额外资源**：启用 AI 场景检测会增加处理时间和内存使用
2. **去重功能持久化**：剪辑点去重数据会保存到磁盘，确保有足够存储空间
3. **并发设置**：`--jobs` 参数建议设置为 2-4，过高可能导致系统负载过大
4. **飞书配置**：使用飞书相关命令前需要正确配置飞书应用信息
5. **临时目录**：处理大量剧集时确保临时目录有足够空间

---

_最后更新：2024 年_
