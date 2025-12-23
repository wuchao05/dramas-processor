"""GUI 模块入口 - NiceGUI 版本。"""

# 使用绝对导入以支持 python -m drama_processor.gui 运行
from drama_processor.gui.nicegui_app import run_gui


if __name__ == "__main__":
    run_gui()
