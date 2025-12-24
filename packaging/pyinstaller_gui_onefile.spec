# -*- mode: python ; coding: utf-8 -*-
#
# 生成单文件 EXE（Windows）：
#   pyinstaller packaging/pyinstaller_gui_onefile.spec
#
# 产物在 dist/dramas-processor-gui.exe
#
# 说明：
# - 内置 configs/default.yaml（用户无需改配置文件）
# - 内置 assets/（tail.mp4 / watermark / 字体等放这里）
# - 运行时通过 sys._MEIPASS + resolve_asset_path 自动定位资源

from pathlib import Path

from PyInstaller.utils.hooks import collect_all


block_cipher = None

# PyInstaller 执行 spec 时不一定提供 __file__，但会提供 SPECPATH（spec 所在目录）
# 本 spec 位于 packaging/ 下，因此项目根目录为 SPECPATH 的上一级
_spec_dir = Path(globals().get("SPECPATH", ".")).resolve()
project_root = _spec_dir.parent

# 收集 nicegui / pywebview 等动态依赖
nicegui_datas, nicegui_binaries, nicegui_hidden = collect_all("nicegui")
webview_datas, webview_binaries, webview_hidden = collect_all("webview")

datas = []
datas += nicegui_datas + webview_datas

# 内置默认配置（只打 default.yaml）
default_yaml = project_root / "configs" / "default.yaml"
if default_yaml.exists():
    datas.append((str(default_yaml), "configs"))

# 内置 assets（包含 tail.mp4、watermark、字体等）
assets_dir = project_root / "assets"
if assets_dir.exists():
    # Tree 会把整个目录拷贝到包内的 assets/
    from PyInstaller.building.datastruct import Tree

    datas.append(Tree(str(assets_dir), prefix="assets"))

binaries = []
binaries += nicegui_binaries + webview_binaries

hiddenimports = []
hiddenimports += nicegui_hidden + webview_hidden

a = Analysis(
    [str(project_root / "run_gui.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="dramas-processor-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不弹出黑框
)


