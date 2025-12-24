"""Windows 打包入口：用于 PyInstaller onefile 生成可双击运行的 GUI。"""

import sys

from drama_processor.gui.nicegui_app import run_gui


if __name__ == "__main__":
    # nicegui_app.run_gui() 通过命令行参数判断是否 native
    if "--native" not in sys.argv:
        sys.argv.append("--native")
    run_gui()


