"""Windows 打包入口：用于 PyInstaller onefile 生成可双击运行的 GUI。"""

import multiprocessing

from drama_processor.gui.nicegui_app import run_gui


if __name__ == "__main__":
    # PyInstaller onefile + multiprocessing 兼容
    multiprocessing.freeze_support()

    # 不要修改 sys.argv（会干扰 PyInstaller 的 multiprocessing 子进程参数解析）
    run_gui(native=True)


