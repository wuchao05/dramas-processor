# 📁 项目目录结构说明

## 🎯 优化后的目录结构

```
dramas_process/
├── src/                          # 源代码目录
│   └── drama_processor/          # 主包
│       ├── cli/                  # 命令行接口
│       ├── core/                 # 核心处理逻辑
│       ├── models/               # 数据模型
│       ├── utils/                # 工具函数
│       └── config/               # 配置管理
├── configs/                      # 配置文件
│   └── default.yaml             # 默认配置
├── assets/                       # 资源文件
│   ├── tail.mp4                 # 默认尾部视频
│   └── fonts/                   # 字体文件 (可选)
├── tests/                        # 测试文件
├── docs/                         # 文档
├── scripts/                      # 脚本工具
│   └── legacy/                  # 遗留脚本
│       └── dramas_process.py    # 旧版脚本
├── pyproject.toml               # 项目配置
├── requirements.txt             # 依赖管理
├── README.md                    # 项目说明
└── .gitignore                   # Git忽略文件
```

## 🔄 主要变更

### ✅ 已优化

- 消除了 `drama_processor/src/drama_processor/` 的双重嵌套
- 将 `tail.mp4` 移动到 `assets/` 目录
- 将旧版脚本移动到 `scripts/legacy/`
- 配置文件统一到根级 `configs/` 目录
- 项目文件提升到根目录

### 🔧 路径更新

- 尾部视频默认路径：`assets/tail.mp4`
- 配置文件路径：`configs/default.yaml`
- 源码路径：`src/drama_processor/`

## 🚀 使用方式

### 开发模式安装

```bash
# 进入项目目录
cd dramas_process

# 安装为可编辑包
pip install -e .

# 运行程序
drama-processor --help
```

### 使用默认配置

```bash
drama-processor process /path/to/dramas
```

### 使用自定义配置

```bash
drama-processor process /path/to/dramas --config configs/custom.yaml
```

## 📋 目录职责

| 目录       | 职责     | 说明                 |
| ---------- | -------- | -------------------- |
| `src/`     | 核心源码 | 所有 Python 包代码   |
| `configs/` | 配置管理 | YAML 配置文件        |
| `assets/`  | 静态资源 | 视频、字体等资源文件 |
| `tests/`   | 测试代码 | 单元测试和集成测试   |
| `docs/`    | 项目文档 | API 文档、使用指南等 |
| `scripts/` | 工具脚本 | 构建、部署、遗留脚本 |

## 🎯 优势

1. **清晰的结构**：消除嵌套混乱，层次分明
2. **标准化**：符合 Python 项目最佳实践
3. **易于维护**：文件位置直观，便于查找
4. **版本控制友好**：合理的 gitignore 配置
5. **扩展性好**：为未来功能预留了合理空间
