# 打包指南 / Packaging Guide

当前打包流程默认产出一个统一的通用运行时包，供 Electron 客户端的“素材剪辑”页面导入，不再按达人分别打包。

## Windows 打包

### 方式 1：PowerShell 交互入口（推荐）

```powershell
.\package-tool.ps1
```

### 方式 2：PowerShell 命令行

```powershell
.\package.ps1 -OutputDir "D:\Package-Output"
```

## Mac/Linux 打包

### 方式 1：Shell 脚本（推荐）

```bash
./package.sh
```

### 方式 2：指定输出目录

```bash
./package.sh ~/Desktop/Package-Output
```

### 方式 3：PowerShell Core

```bash
pwsh ./package.ps1 -OutputDir "~/Desktop/Package-Output"
```

## 打包后的文件结构

```text
drama-processor-runtime-20260120_XXXXXX/
├── run-install.bat            ← Windows 环境安装入口
└── drama-processor/           ← 统一运行时目录
    ├── install.ps1            ← 安装脚本
    ├── src/                   ← 源代码
    ├── configs/
    │   ├── default.yaml       ← 通用默认配置（不绑定 active_user）
    │   └── users/             ← 空目录，保留结构兼容
    ├── assets/                ← 资源文件
    ├── bin/                   ← 可选运行时工具（如 ffmpeg）
    ├── requirements.txt       ← Python 依赖
    ├── requirements_ai.txt    ← AI 相关依赖
    └── pyproject.toml         ← 项目元数据
```

## 使用方式

1. 运行打包命令，得到 `drama-processor-runtime-*.zip`
2. 打开 Electron 客户端的“素材剪辑”页面
3. 点击“导入运行时”，选择这个 zip 包
4. 导入后点击“自动安装”准备 Python / FFmpeg / 依赖环境
5. 环境就绪后，在客户端内继续配置并执行剪辑

## 说明

- 当前通用运行时包不会再生成达人专属的 `start-feishu-watch.bat`
- 当前通用运行时包不会复制 `configs/users/*.yaml`，也不会在打包时改写某个达人为 `active_user`
- 如果后续仍需达人级差异，请在 Electron 客户端页面或运行时配置中显式传入，而不是依赖打包阶段固化

## 文件命名说明

所有批处理文件和 PowerShell 脚本继续使用英文文件名，避免 Windows / Mac 编码兼容问题：

| 文件名             | 用途                   |
| ------------------ | ---------------------- |
| `package-tool.ps1` | Windows 通用打包入口   |
| `package.ps1`      | 通用运行时打包核心脚本 |
| `package.sh`       | Mac/Linux 通用打包入口 |
| `install.ps1`      | 运行时安装脚本         |
| `run-install.bat`  | Windows 运行时安装入口 |
| `drama-processor/` | 运行时根目录           |
