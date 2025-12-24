# GUI 打包说明

## 问题修复

### ModuleNotFoundError: No module named 'drama_processor.core.encoder'

**原因：** PyInstaller 未自动发现所有子模块，导致打包时遗漏了 `encoder.py` 等模块。

**解决方案：** 已在 `pyinstaller_gui_onefile.spec` 中显式添加所有子模块到 `hiddenimports`。

## 重新打包步骤

### Windows 环境

```powershell
# 1. 进入项目目录
cd D:\dramas-processor

# 2. 激活虚拟环境（如果有）
.\venv\Scripts\activate

# 3. 确保安装了 PyInstaller
pip install pyinstaller

# 4. 清理旧的打包文件
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

# 5. 重新打包
pyinstaller packaging/pyinstaller_gui_onefile.spec

# 6. 测试生成的 exe
.\dist\dramas-processor-gui.exe
```

### Linux/WSL 环境

```bash
# 1. 进入项目目录
cd ~/projects/dramas-processor

# 2. 激活虚拟环境（如果有）
source venv/bin/activate

# 3. 确保安装了 PyInstaller
pip install pyinstaller

# 4. 清理旧的打包文件
rm -rf build dist

# 5. 重新打包
pyinstaller packaging/pyinstaller_gui_onefile.spec

# 6. 测试生成的 exe（需要在 Windows 中测试）
```

## 打包输出

成功打包后，会在 `dist/` 目录生成：
- `dramas-processor-gui.exe` - 单文件可执行程序

## 验证打包

### 1. 检查文件大小

```powershell
# 正常情况下应该 > 100 MB（包含所有依赖）
Get-Item dist\dramas-processor-gui.exe | Select-Object Name,Length
```

### 2. 运行测试

```powershell
# 直接运行
.\dist\dramas-processor-gui.exe

# 应该打开 GUI 界面，没有报错
```

### 3. 检查日志

如果运行报错，查看控制台输出或创建日志文件：

```powershell
# 带控制台输出运行（调试用）
# 临时修改 spec 文件：console=True

# 或捕获错误
.\dist\dramas-processor-gui.exe > log.txt 2>&1
type log.txt
```

## 常见问题

### 1. 打包太慢

**原因：** PyInstaller 需要分析所有依赖

**解决：**
- 使用 SSD
- 关闭杀毒软件
- 首次打包需要 5-10 分钟，后续会快一些

### 2. 缺少模块

**症状：** `ModuleNotFoundError: No module named 'xxx'`

**解决：** 在 spec 文件的 `hiddenimports` 中添加缺失的模块：

```python
hiddenimports += [
    "missing_module_name",
]
```

### 3. 打包文件过大

**原因：** 包含了不必要的依赖

**解决：** 在 spec 文件的 `excludes` 中排除不需要的模块：

```python
a = Analysis(
    ...
    excludes=[
        "tkinter",      # 如果不用 tkinter
        "matplotlib",   # 如果不用绘图
        "scipy",        # 如果不用科学计算
    ],
)
```

### 4. Windows Defender 误报

**症状：** 杀毒软件删除或阻止 exe 运行

**解决：**
1. 临时关闭 Windows Defender
2. 将 `dist/` 目录添加到排除列表
3. 使用代码签名证书签名 exe（生产环境）

### 5. UPX 压缩失败

**症状：** 打包时 UPX 报错

**解决：** 在 spec 文件中禁用 UPX：

```python
exe = EXE(
    ...
    upx=False,  # 改为 False
)
```

## 发布准备

### 1. 版本号

在 `pyproject.toml` 或 `__init__.py` 中更新版本号：

```python
__version__ = "1.0.0"
```

### 2. 测试清单

- [ ] GUI 正常启动
- [ ] 配置文件加载正常
- [ ] 资源文件（assets）可访问
- [ ] 剪辑功能正常
- [ ] 飞书集成正常
- [ ] 硬件编码检测正常
- [ ] 在不同 Windows 版本测试（Win 10/11）

### 3. 文档准备

确保以下文档存在并更新：
- `README.md` - 项目说明
- `COMMANDS_USAGE_GUIDE.md` - 使用指南
- `docs/HARDWARE_ENCODER_TROUBLESHOOTING.md` - 故障排查

### 4. 压缩分发

```powershell
# 创建发布包
Compress-Archive -Path dist\dramas-processor-gui.exe -DestinationPath dramas-processor-gui-v1.0.0.zip

# 包含文档
Compress-Archive -Path dist\dramas-processor-gui.exe,README.md,docs\ -DestinationPath dramas-processor-gui-v1.0.0-full.zip
```

## 自动化打包脚本

### Windows (PowerShell)

```powershell
# build.ps1
param(
    [string]$Version = "dev"
)

Write-Host "清理旧文件..." -ForegroundColor Yellow
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

Write-Host "开始打包 v$Version..." -ForegroundColor Green
pyinstaller packaging/pyinstaller_gui_onefile.spec

if ($LASTEXITCODE -eq 0) {
    Write-Host "打包成功！" -ForegroundColor Green
    
    # 测试运行
    Write-Host "测试运行..." -ForegroundColor Yellow
    Start-Process -FilePath ".\dist\dramas-processor-gui.exe" -Wait
    
    # 创建发布包
    $ZipName = "dramas-processor-gui-v$Version.zip"
    Compress-Archive -Path dist\dramas-processor-gui.exe -DestinationPath $ZipName -Force
    Write-Host "发布包已创建: $ZipName" -ForegroundColor Green
} else {
    Write-Host "打包失败！" -ForegroundColor Red
    exit 1
}
```

使用方法：
```powershell
.\packaging\build.ps1 -Version "1.0.0"
```

### Linux/Mac (bash)

```bash
#!/bin/bash
# build.sh

VERSION=${1:-"dev"}

echo "清理旧文件..."
rm -rf build dist

echo "开始打包 v$VERSION..."
pyinstaller packaging/pyinstaller_gui_onefile.spec

if [ $? -eq 0 ]; then
    echo "打包成功！"
    
    # 创建发布包
    ZIP_NAME="dramas-processor-gui-v$VERSION.zip"
    zip -j "$ZIP_NAME" dist/dramas-processor-gui.exe
    echo "发布包已创建: $ZIP_NAME"
else
    echo "打包失败！"
    exit 1
fi
```

使用方法：
```bash
chmod +x packaging/build.sh
./packaging/build.sh 1.0.0
```

## 调试技巧

### 1. 启用控制台输出

临时修改 spec 文件进行调试：

```python
exe = EXE(
    ...
    console=True,  # 改为 True 显示控制台
    debug=True,    # 启用调试模式
)
```

### 2. 查看打包内容

```powershell
# 使用 PyInstaller 的归档查看器
pyi-archive_viewer dist\dramas-processor-gui.exe

# 在交互界面中：
# - 输入 'l' 查看文件列表
# - 输入 'x module_name' 提取特定模块
# - 输入 'q' 退出
```

### 3. 分析依赖

```bash
# 生成依赖关系图
pyinstaller --debug=all packaging/pyinstaller_gui_onefile.spec 2>&1 | grep "Adding"
```

## 参考资源

- [PyInstaller 官方文档](https://pyinstaller.org/)
- [PyInstaller Spec 文件说明](https://pyinstaller.org/en/stable/spec-files.html)
- [常见问题解答](https://pyinstaller.org/en/stable/common-problems-and-solutions.html)

