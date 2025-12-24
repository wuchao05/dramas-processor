"""Windows 打包入口：用于 PyInstaller onefile 生成可双击运行的 GUI。"""

from drama_processor.gui.nicegui_app import run_gui


if __name__ == "__main__":
    # 固定使用 native 模式，生成桌面窗口（无需浏览器）
    run_gui(native=True)


