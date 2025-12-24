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

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


block_cipher = None

# PyInstaller 执行 spec 时不一定提供 __file__，但会提供 SPECPATH（spec 所在目录）
# 本 spec 位于 packaging/ 下，因此项目根目录为 SPECPATH 的上一级
_spec_dir = Path(globals().get("SPECPATH", ".")).resolve()
project_root = _spec_dir.parent

datas = []

# 收集 nicegui 运行所需数据文件/动态库/隐藏导入
# 注意：PyInstaller 6.17 下 collect_all() 返回的 datas 结构与 Analysis(datas=...) 期望格式不一致
datas += collect_data_files("nicegui")
binaries = []
binaries += collect_dynamic_libs("nicegui")
hiddenimports = []
hiddenimports += collect_submodules("nicegui")

# pywebview（Windows native 模式需要）
datas += collect_data_files("webview")
binaries += collect_dynamic_libs("webview")
# webview 的 submodules 中可能包含 android/ios 等平台，显式列 Windows 常用即可
hiddenimports += [
    "webview",
    "webview.platforms",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "webview.platforms.mshtml",
]

# 显式添加 drama_processor 所有子模块（解决 ModuleNotFoundError）
hiddenimports += collect_submodules("drama_processor")
hiddenimports += [
    "drama_processor.core",
    "drama_processor.core.encoder",
    "drama_processor.core.processor",
    "drama_processor.core.analyzer",
    "drama_processor.core.segments",
    "drama_processor.core.overlay",
    "drama_processor.models",
    "drama_processor.models.config",
    "drama_processor.models.project",
    "drama_processor.models.episode",
    "drama_processor.models.feishu",
    "drama_processor.models.history",
    "drama_processor.utils",
    "drama_processor.utils.files",
    "drama_processor.utils.video",
    "drama_processor.utils.logging",
    "drama_processor.utils.system",
    "drama_processor.utils.text",
    "drama_processor.utils.time",
    "drama_processor.utils.interactive",
    "drama_processor.utils.cancel",
    "drama_processor.utils.history",
    "drama_processor.utils.date_deduplication",
    "drama_processor.config",
    "drama_processor.config.loader",
    "drama_processor.config.manager",
    "drama_processor.config.defaults",
    "drama_processor.integrations",
    "drama_processor.integrations.feishu_client",
    "drama_processor.integrations.feishu_notification",
    "drama_processor.cli",
    "drama_processor.cli.main",
    "drama_processor.cli.commands",
    "drama_processor.gui",
    "drama_processor.gui.nicegui_app",
]

# 内置默认配置（只打 default.yaml）
default_yaml = project_root / "configs" / "default.yaml"
if default_yaml.exists():
    datas.append((str(default_yaml), "configs"))

# 内置 assets（包含 tail.mp4、watermark、字体等）
# 注意：PyInstaller 6.17 的 Analysis(datas=...) 期望 (src, dest_dir) 二元组；
# Tree(...) 产生三元组，容易触发 “too many values to unpack (expected 2)”
assets_dir = project_root / "assets"
if assets_dir.exists():
    for p in assets_dir.rglob("*"):
        if not p.is_file():
            continue
        rel_parent = p.relative_to(assets_dir).parent  # e.g. "." / "fonts"
        dest_dir = str(Path("assets") / rel_parent) if str(rel_parent) != "." else "assets"
        datas.append((str(p), dest_dir))

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


