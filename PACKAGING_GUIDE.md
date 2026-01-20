# 打包指南 / Packaging Guide

## Windows 打包

### 方式 1：PowerShell 交互式（推荐）
```powershell
.\package-tool.ps1
```

### 方式 2：PowerShell 命令行
```powershell
.\package.ps1 -Name "lm" -OutputDir "D:\Package-Output"
```

## Mac/Linux 打包

### 方式 1：Shell 脚本（推荐）
```bash
./package.sh
```

### 方式 2：PowerShell Core
```bash
pwsh ./package.ps1 -Name "lm" -OutputDir "~/Desktop/Package-Output"
```

## 打包后的文件结构

```
短剧剪辑工具-lm-20260120_XXXXXX/
├── run-install.bat            ← 达人双击安装环境
├── start-feishu-watch.bat     ← 安装后双击启动飞书监控
└── drama-processor/           ← 项目文件目录
    ├── install.ps1            ← 安装脚本
    ├── src/                   ← 源代码
    ├── configs/               ← 配置文件
    │   ├── default.yaml
    │   └── users/
    │       └── lm.yaml        ← 达人专属配置
    ├── assets/                ← 资源文件
    └── requirements.txt       ← Python 依赖
```

## 文件命名说明

所有批处理文件和PowerShell脚本都使用**英文文件名**，彻底避免 Windows/Mac 编码兼容性问题：

| 旧文件名（中文） | 新文件名（英文） | 用途 |
|----------------|----------------|-----|
| 打包工具.bat | `package-tool.bat` | Windows 打包入口 |
| 一键安装.ps1 | `install.ps1` | 达人安装脚本 |
| 打包给达人.ps1 | `package.ps1` | 打包核心脚本 |
| 运行一键安装.bat | `run-install.bat` | 达人安装入口 |
| 启动飞书监控.bat | `start-feishu-watch.bat` | 飞书监控入口 |
| 项目文件/ | `drama-processor/` | 项目目录 |

## 编码说明

- **批处理文件** (`.bat`)：纯英文内容，ASCII 编码
- **PowerShell 脚本** (`.ps1`)：UTF-8 without BOM，跨平台兼容
- **配置文件** (`.yaml`)：UTF-8 with BOM，支持中文
