# 剪辑点去重功能使用指南

## 功能概述

剪辑点去重功能可以避免在多次运行剪辑脚本时生成重复的素材内容。该功能通过持久化存储每部剧的已使用剪辑点，确保后续运行时避开这些区域。

## 启用方式

在命令行中添加 `--enable-deduplication` 参数：

```bash
# 启用去重功能
python -m drama_processor.cli process /path/to/dramas --enable-deduplication

# 同时启用AI场景检测和去重
python -m drama_processor.cli process /path/to/dramas --ai-scene-detection --enable-deduplication

# 完整示例
python -m drama_processor.cli process /path/to/dramas \
  --count 5 \
  --ai-scene-detection \
  --enable-deduplication \
  --temp-dir /tmp/drama_work
```

## 工作原理

### 1. 持久化存储

- 剪辑点数据存储在 `{temp_dir}/cut_points_history/` 目录下
- 每部剧对应一个 JSON 文件，文件名格式：`{hash}_{drama_name}.json`
- 文件包含剧集名、更新时间和已使用的剪辑点列表

### 2. 去重机制

- **排除半径**：30 秒（可配置）
- **冲突检测**：新剪辑点与已使用剪辑点距离小于排除半径时被跳过
- **智能回退**：当所有 AI 剪辑点都被使用时，自动回退到随机生成方式

### 3. 处理流程

1. **加载历史**：处理开始时从文件加载该剧的历史剪辑点
2. **生成筛选**：生成新剪辑点时自动过滤冲突位置
3. **实时记录**：每个新剪辑点被立即记录到内存
4. **持久保存**：处理完成后将新剪辑点保存到文件

## 存储格式

剪辑点文件示例 (`3aadbec6_测试剧集.json`)：

```json
{
  "drama_name": "测试剧集",
  "last_updated": "2025-09-07T23:27:06.735783",
  "used_cut_points": [
    {
      "episode_idx": 0,
      "timestamp": 120.5
    },
    {
      "episode_idx": 0,
      "timestamp": 350.2
    },
    {
      "episode_idx": 1,
      "timestamp": 200.8
    }
  ]
}
```

## 配置参数

### CLI 参数

- `--enable-deduplication`: 启用去重功能（默认关闭）
- `--temp-dir`: 临时目录，去重数据存储位置（默认 `/tmp`）

### 内部配置

- `exclusion_radius`: 排除半径，默认 30 秒
- `max_attempts`: 随机生成最大尝试次数，默认 `count * 10`

## 使用场景

### 1. 批量生产

```bash
# 第一次运行：生成10个素材
python -m drama_processor.cli process /dramas --count 10 --enable-deduplication

# 第二次运行：生成另外10个不重复的素材
python -m drama_processor.cli process /dramas --count 10 --enable-deduplication
```

### 2. 与 AI 场景检测结合

```bash
# AI选择最佳剪辑点，同时避免重复
python -m drama_processor.cli process /dramas \
  --ai-scene-detection \
  --enable-deduplication \
  --count 15
```

### 3. 长期项目管理

```bash
# 设置专用临时目录，便于管理去重数据
python -m drama_processor.cli process /dramas \
  --enable-deduplication \
  --temp-dir /project/drama_cache \
  --count 20
```

## 日志输出

启用去重功能时，会看到如下日志：

```
🔄 启用去重模式，加载历史剪辑点：测试剧集
✅ 已加载 3 个历史剪辑点
🎯 开始生成 5 个起始点
✅ AI选择剪辑点: 第1集, 180.5s
💾 保存新增的 2 个剪辑点
```

## 注意事项

1. **存储位置**：确保 `temp_dir` 有足够空间和写权限
2. **文件管理**：去重文件会持续累积，建议定期清理旧项目的数据
3. **性能影响**：启用去重会略微增加处理时间（文件 I/O 操作）
4. **兼容性**：与现有的随机起点和 AI 场景检测功能完全兼容

## 故障排除

### 问题：无法保存剪辑点文件

**解决方案**：检查 `temp_dir` 权限和磁盘空间

### 问题：去重效果不明显

**解决方案**：检查排除半径设置，确保足够大以避免相似内容

### 问题：生成的剪辑点数量不足

**解决方案**：历史剪辑点过多时会导致可选位置减少，考虑清理旧数据或增加排除半径

## 技术实现

该功能在 `AIEnhancedProcessor` 中实现，主要组件：

- `_load_used_cut_points()`: 加载历史剪辑点
- `_save_used_cut_points()`: 保存剪辑点到文件
- `_is_cut_point_excluded()`: 检查剪辑点冲突
- `generate_start_points()`: 重写起始点生成逻辑
- `process_project_materials()`: 集成到处理流程

## 更新日志

- **v1.0**: 基础去重功能实现
- **v1.1**: 集成 AI 场景检测支持
- **v1.2**: 添加持久化存储和跨会话支持
