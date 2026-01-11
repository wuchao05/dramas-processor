# WSL 专用脚本（已废弃）

## ⚠️ 重要说明

项目已改造为 Windows 原生运行，以下脚本仅适用于 WSL 环境，**Windows 原生环境无需使用**。

## 废弃的脚本列表

### WSL 环境管理
- `wsl_memory_guard.sh` - WSL 内存监控（Windows 原生环境不需要）
- `check_wsl_setup.sh` - WSL 环境检查
- `wsl2_nvenc_check.sh` - WSL2 NVENC 检查

### WSL 打包脚本
- `make_lite_release_wsl.sh` - WSL 环境 Lite 版本打包
- `make_pro_release_wsl.sh` - WSL 环境 Pro 版本打包

### WSL 工具脚本
- `keep-show-wsl.sh` - WSL 专用的白名单清理脚本（已有 Python 版本替代）

## Windows 用户替代方案

### 1. 环境检查
```powershell
# 使用 Python 测试脚本
python scripts/test_windows.py
```

### 2. 打包
```powershell
# 使用 Windows 打包脚本
.\packaging\build_windows.ps1
```

### 3. 内存监控
Windows 系统自带任务管理器，内存管理更优秀，无需额外监控脚本。

### 4. 白名单清理
```bash
# 使用 Python 版本（跨平台）
python scripts/keep_show.py
```

## 保留脚本（仍然有效）

以下脚本可在 Windows 和 WSL 环境下使用：

- `check_encoders.py` - FFmpeg 编码器检查（Python，跨平台）
- `license_tool.py` - License 工具（Python，跨平台）
- `cli_entry.py` - CLI 入口（Python，跨平台）
- `gui_entry.py` - GUI 入口（Python，跨平台）

## 如果你仍在使用 WSL

如果你仍在 WSL 环境下运行项目，这些脚本依然可用。但我们推荐：

1. **迁移到 Windows 原生环境** - 性能更好，兼容性更强
2. 参考 `docs/WINDOWS_QUICKSTART.md` 了解如何在 Windows 原生环境运行

## 技术支持

- Windows 原生运行指南: [`docs/WINDOWS_QUICKSTART.md`](../docs/WINDOWS_QUICKSTART.md)
- 改造文档: [`docs/WINDOWS_NATIVE_MIGRATION.md`](../docs/WINDOWS_NATIVE_MIGRATION.md)
- 主文档: [`README.md`](../README.md)
