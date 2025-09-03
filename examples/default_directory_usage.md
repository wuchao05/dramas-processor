# 默认源目录功能使用指南

## 功能概述

默认源目录功能允许您在不指定源目录路径的情况下处理短剧，系统会自动使用配置文件中设置的默认目录。

## 配置方法

### 方法 1：修改配置文件

编辑 `configs/default.yaml`：

```yaml
# Directory settings
default_source_dir: "/Volumes/爆爆盘/短剧剪辑/源素材视频" # 您的默认源素材目录
```

### 方法 2：通过环境变量（可选）

```bash
export DRAMA_SOURCE_DIR="/Volumes/爆爆盘/短剧剪辑/源素材视频"
```

## 使用示例

### 基础使用

```bash
# 原来需要这样：
drama-processor process /Volumes/爆爆盘/短剧剪辑/源素材视频

# 现在可以简化为：
drama-processor process
```

### 结合其他参数

```bash
# 使用默认目录，生成3条素材
drama-processor process --count 3

# 使用默认目录，配合日期组织
drama-processor process --date "9.3" --count 2

# 使用默认目录，完全定制参数
drama-processor process \
  --count 2 \
  --min-sec 300 \
  --max-sec 600 \
  --date "9.3" \
  --jobs 2 \
  --fast-mode
```

### 覆盖默认目录

```bash
# 仍然可以指定其他目录，优先级更高
drama-processor process /path/to/other/dramas
```

## 目录验证

系统会在运行时验证默认目录：

1. **目录存在性检查**：确保目录路径有效
2. **权限检查**：确保具有读取权限
3. **错误提示**：如果目录不存在或无权限访问，会给出明确的错误信息

### 错误处理示例

```bash
$ drama-processor process
错误：默认源素材目录不存在：/Volumes/爆爆盘/短剧剪辑/源素材视频
请指定一个有效的源目录路径，或检查配置文件中的 default_source_dir 设置
```

## 团队协作

### 配置文件分发

1. 团队成员共享相同的 `configs/default.yaml`
2. 每个人根据自己的环境调整 `default_source_dir`
3. 使用版本控制时，可以将个人配置加入 `.gitignore`

### 推荐目录结构

```
项目根目录/
├── configs/
│   ├── default.yaml        # 通用配置
│   ├── local.yaml          # 个人配置（在.gitignore中）
│   └── production.yaml     # 生产环境配置
├── dramas_process/         # 项目代码
└── 源素材视频/             # 默认源目录（可选）
```

## 最佳实践

### 1. 目录组织建议

```
/Volumes/爆爆盘/短剧剪辑/
├── 源素材视频/             # 默认源目录
│   ├── 短剧1/
│   ├── 短剧2/
│   └── ...
├── 导出素材/               # 输出目录
└── 源素材封面/             # 封面目录
```

### 2. 批处理脚本

```bash
#!/bin/bash
# 批量处理脚本示例

# 处理今天的内容
drama-processor process --date "$(date +%m.%d)" --count 2

# 处理指定内容
drama-processor process --include "特定短剧名" --count 3
```

### 3. 配置文件管理

```bash
# 使用不同配置
drama-processor -c configs/production.yaml process
drama-processor -c configs/local.yaml process
```

## 注意事项

1. **路径格式**：建议使用绝对路径，避免相对路径的歧义
2. **权限设置**：确保目录具有适当的读写权限
3. **网络目录**：如果使用网络存储，确保网络连接稳定
4. **空间检查**：确保输出目录有足够的存储空间

## 故障排除

### 常见问题

1. **目录不存在**

   - 检查路径是否正确
   - 确认外部存储设备是否挂载

2. **权限问题**

   ```bash
   chmod -R 755 /Volumes/爆爆盘/短剧剪辑/源素材视频
   ```

3. **配置不生效**
   - 确认配置文件语法正确
   - 检查是否使用了正确的配置文件

### 调试模式

```bash
# 启用调试模式查看详细信息
drama-processor --log-level DEBUG process
```
