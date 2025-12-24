"""短剧批量剪辑 GUI（NiceGUI 现代化版本）- Material Design 风格。"""

import asyncio
import logging
import os
import queue
import sys
import tempfile
import threading
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from difflib import SequenceMatcher

from nicegui import ui, app as nicegui_app
import yaml

from ..config.defaults import get_default_config
from ..config.loader import load_config
from ..core.processor import DramaProcessor
from ..models.config import BrandTextMapping, BrandTextRange, FeishuWatcherConfig, ProcessingConfig
from ..utils.files import scan_drama_dirs
from ..utils.logging import setup_logging
from ..utils.system import resolve_asset_path
from ..utils.cancel import CancelledError


LogItem = Tuple[str, str]


class DramaStatus(Enum):
    """剧目处理状态"""
    PENDING = "pending"      # 待处理（初始状态）
    QUEUED = "queued"        # 待剪辑（已加入处理队列）
    PROCESSING = "processing" # 剪辑中（正在处理）
    COMPLETED = "completed"   # 已完成
    
    @property
    def label(self) -> str:
        """中文标签"""
        labels = {
            self.PENDING: "待处理",
            self.QUEUED: "待剪辑",
            self.PROCESSING: "剪辑中",
            self.COMPLETED: "已完成"
        }
        return labels[self]
    
    @property
    def color(self) -> str:
        """Quasar颜色"""
        colors = {
            self.PENDING: "grey",
            self.QUEUED: "blue",
            self.PROCESSING: "orange",
            self.COMPLETED: "green"
        }
        return colors[self]


class GuiLogHandler(logging.Handler):
    """将日志写入队列，供 UI 消费。"""

    def __init__(self, log_queue: "queue.Queue[LogItem]") -> None:
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            if not msg:
                return
            for line in msg.splitlines():
                self.log_queue.put(("log", line))
        except Exception:
            self.handleError(record)


class StreamRedirector:
    """接管 stdout/stderr，避免 print 输出丢失。"""

    def __init__(self, log_queue: "queue.Queue[LogItem]", tag: str) -> None:
        self.log_queue = log_queue
        self.tag = tag
        self._buffer = ""

    def write(self, text: str) -> int:
        if not text:
            return 0
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.rstrip("\r")
            self.log_queue.put((self.tag, line))
        return len(text)

    def flush(self) -> None:
        if self._buffer:
            self.log_queue.put((self.tag, self._buffer.rstrip("\r")))
            self._buffer = ""

    def isatty(self) -> bool:
        return False


def _is_windows() -> bool:
    return os.name == "nt"


def _find_windows_font() -> Optional[str]:
    win_dir = os.environ.get("WINDIR", r"C:\Windows")
    font_dir = Path(win_dir) / "Fonts"
    candidates = [
        "msyh.ttc",
        "msyhbd.ttc",
        "msyh.ttf",
        "simhei.ttf",
        "simsun.ttc",
    ]
    for name in candidates:
        candidate = font_dir / name
        if candidate.is_file():
            return str(candidate)
    return None


def _parse_int(value: str, label: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{label} 必须是整数") from exc


def _parse_float(value: str, label: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{label} 必须是数字") from exc


class DramaProcessorGUI:
    """短剧处理器 GUI 应用（NiceGUI 版本）"""

    def __init__(self):
        # 状态变量
        self.root_dir = ""
        self.config_path = ""
        self.output_dir = ""
        self.font_file = ""
        self.date_str = ""
        
        # 剧目相关
        self.all_drama_names: List[str] = []
        self.filtered_drama_names: List[str] = []
        self.selected_drama_names: Set[str] = set()
        self.processing_root: Optional[str] = None
        
        # UI 容器引用（在 build_ui 中初始化）
        self.available_dramas_container = None
        self.selected_dramas_container = None
        
        # 参数配置
        self.count = "1"
        self.min_duration = "480"
        self.max_duration = "900"
        self.jobs = "1"
        self.material_code = "xh"  # 默认素材用户名
        self.title_colors = ""
        self.brand_default = "小红看剧"  # 默认品牌文案
        self.brand_ranges = ""  # 素材范围映射
        
        self.title_font_size = "55"
        self.side_font_size = "35"
        self.bottom_font_size = "30"
        
        self.use_hw = True
        self.fast_mode = True
        self.keep_temp = False
        self.verbose = False
        
        # 飞书配置
        self.enable_feishu = False
        self.feishu_app_id = ""
        self.feishu_app_secret = ""
        self.feishu_app_token = ""
        self.feishu_table_id = ""
        
        # 处理状态
        self.is_running = False
        self.log_count = 0
        self.is_watcher_running = False
        self.total_dramas = 0
        self.completed_dramas = 0
        self.status_text = "就绪"
        
        # 剧目状态管理（新增）
        self.drama_status_map: Dict[str, DramaStatus] = {}  # {剧名: 状态}
        self.drama_queue: List[str] = []  # 处理队列
        self.current_processing_drama: Optional[str] = None  # 当前正在处理的剧目
        self.export_path_display: str = ""  # 当前导出路径
        
        # 后台任务
        self.log_queue: "queue.Queue[LogItem]" = queue.Queue()
        self.cancel_event = threading.Event()
        self.watcher_stop_event = threading.Event()
        self.watcher_thread: Optional[threading.Thread] = None
        self.processing_thread: Optional[threading.Thread] = None
        
        # UI 组件引用（将在构建时设置）
        self.drama_table = None
        self.selected_chips_container = None
        self.progress_bar = None
        self.progress_label = None
        self.status_label = None
        self.log_container = None
        self.start_button = None
        self.cancel_button = None
        self.start_watcher_button = None
        self.stop_watcher_button = None
        self.drama_search_input = None
        
        self._base_brand_text = "热门短剧"
        
    def _configure_logging(self, verbose: bool = False) -> None:
        """配置日志系统"""
        # setup_logging 需要字符串类型的 level
        level_str = "DEBUG" if verbose else "INFO"
        level_num = logging.DEBUG if verbose else logging.INFO
        setup_logging(level=level_str)
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        gui_handler = GuiLogHandler(self.log_queue)
        gui_handler.setLevel(level_num)
        formatter = logging.Formatter('%(message)s')
        gui_handler.setFormatter(formatter)
        root_logger.addHandler(gui_handler)
        root_logger.setLevel(level_num)

    def build_ui(self):
        """构建现代化 UI 界面"""
        # 设置页面背景色和主题
        ui.query('body').style('background-color: #F8FAFC') # Slate-50
        ui.colors(
            primary='#6366F1',      # Indigo-500
            secondary='#EC4899',    # Pink-500
            accent='#06B6D4',       # Cyan-500
            positive='#10B981',     # Emerald-500
            negative='#EF4444',     # Red-500
            info='#3B82F6',         # Blue-500
            warning='#F59E0B'       # Amber-500
        )

        # 1. 顶部导航栏
        with ui.header().classes('bg-white text-gray-800 border-b border-gray-100 h-16 px-6 flex items-center justify-between shadow-sm'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('movie_filter', color='primary').classes('text-3xl')
                ui.label('爆剧爆剪').classes('text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-500 to-pink-500')
                ui.label('v2.0').classes('text-xs text-gray-400 border border-gray-200 rounded px-1')
            
            with ui.row().classes('gap-3'):
                self.status_badge = ui.badge('就绪', color='green').props('rounded outline')
                ui.button('查看日志', icon='assignment', on_click=lambda: self.log_dialog.open()) \
                    .classes('text-gray-700 hover:text-indigo-600 font-medium')
                ui.button('设置', icon='settings', on_click=self._open_settings_dialog) \
                    .classes('text-gray-700 hover:text-indigo-600 font-medium')

        # 2. 日志弹窗 (替代原来的抽屉)
        with ui.dialog() as self.log_dialog:
            with ui.card().classes('w-[90vw] max-w-6xl h-[85vh] p-0 flex flex-col shadow-2xl'):
                # Header
                with ui.row().classes('w-full bg-gradient-to-r from-gray-900 to-gray-800 text-white p-4 items-center justify-between shadow-md'):
                    with ui.row().classes('items-center gap-3'):
                        ui.icon('terminal', color='positive').classes('text-3xl animate-pulse')
                        ui.label('运行日志监控').classes('text-xl font-bold font-mono tracking-wide')
                        self.log_status_badge = ui.badge('0 条', color='grey').props('outline')
                    
                    with ui.row().classes('gap-2'):
                        ui.button('清空日志', icon='delete_sweep', on_click=self._clear_logs) \
                            .classes('bg-red-500 hover:bg-red-600 text-white shadow-sm')
                        ui.button('关闭', icon='close', on_click=self.log_dialog.close) \
                            .classes('bg-gray-700 hover:bg-gray-600 text-white shadow-sm')
                
                # Content - 使用 ui.log 自带的滚动功能
                self.log_container = ui.log(max_lines=5000).classes('w-full flex-1') \
                    .style('background-color: #0a0a0a; color: #4ade80; padding: 1.5rem; font-family: monospace; font-size: 0.875rem; line-height: 1.5;')

        # 3. 主内容区域
        with ui.column().classes('w-full max-w-7xl mx-auto p-6 gap-6'):
            
            # 状态横幅
            self._render_status_banner()

            # 剧目选择区域 - 左右分栏
            ui.label('剧目选择').classes('text-xl font-bold mb-4')
            
            # 顶部操作栏
            with ui.row().classes('w-full items-center justify-between mb-3'):
                ui.button(icon='refresh', on_click=self._refresh_drama_list).props('flat round color=grey').tooltip('刷新列表')
                
                with ui.row().classes('gap-2'):
                    self.cancel_btn = ui.button('取消', icon='stop', on_click=self._cancel_processing) \
                        .classes('bg-red-500 text-white shadow-md hover:bg-red-600')
                    self.process_btn = ui.button('开始处理选中', icon='play_arrow', on_click=self._on_start_processing_click) \
                        .classes('bg-indigo-600 text-white shadow-md hover:bg-indigo-700')
                
                # 初始隐藏取消按钮
                self.cancel_btn.set_visibility(False)
            
            # 左右分栏容器 - 使用 flex 布局
            with ui.row().classes('w-full gap-4').style('min-height: 500px; display: flex;'):
                # 左侧：可选剧目列表
                with ui.column().classes('gap-2').style('flex: 1; min-width: 0;'):
                    ui.label('可选剧目').classes('text-sm font-bold text-gray-600')
                    
                    # 搜索框
                    self.drama_search_input = ui.input(placeholder='搜索剧目...') \
                        .props('outlined dense clearable') \
                        .classes('w-full') \
                        .on('input', self._on_drama_filter_change)
                    
                    # 剧目列表（滚动区域）- 原生模式下 q-scroll-area 可能不渲染内容，改用原生滚动容器兜底
                    with ui.column().classes('flex-1 border border-gray-200 rounded p-2').style(
                        'min-height: 400px; max-height: 400px; overflow-y: auto;'
                    ):
                        self.available_dramas_container = ui.column().classes('w-full gap-2')
                
                # 右侧：已选剧目
                with ui.column().classes('gap-2').style('flex: 1; min-width: 0;'):
                    with ui.row().classes('w-full items-center justify-between'):
                        ui.label('已选剧目').classes('text-sm font-bold text-gray-600')
                        ui.badge().bind_text_from(self, 'selected_drama_names', 
                                                 backward=lambda s: str(len(s)))
                    
                    # 已选剧目列表（带状态）- 同上，使用原生滚动容器兜底
                    with ui.column().classes('flex-1 border border-gray-200 rounded p-2').style(
                        'min-height: 400px; max-height: 400px; overflow-y: auto;'
                    ):
                        self.selected_dramas_container = ui.column().classes('w-full gap-2')

        # 启动日志轮询
        ui.timer(0.1, self._poll_log_queue)
        
        # 应用默认值
        self._apply_default_values()
        
        # 初始渲染剧目列表
        self._render_available_dramas()
        self._render_selected_dramas()

    def _render_status_banner(self):
        """渲染状态横幅"""
        with ui.row().classes('w-full bg-blue-50 border border-blue-100 p-4 rounded-xl items-center justify-between shadow-sm') as self.status_banner:
            with ui.row().classes('items-center gap-4'):
                self.status_icon = ui.icon('cloud_off', color='grey').classes('text-4xl')
                with ui.column().classes('gap-1'):
                    self.status_title = ui.label('飞书自动监控未启动').classes('font-bold text-gray-800 text-lg')
                    self.status_desc = ui.label('点击右侧按钮启动监控，自动处理飞书表格中的待剪辑剧目').classes('text-sm text-gray-500')
                    
                    # 导出路径（仅在处理中显示）
                    self.export_path_label = ui.label('').classes('text-xs text-gray-400 font-mono') \
                        .bind_visibility_from(self, 'is_running')
            
            with ui.row().classes('items-center gap-4'):
                self.watcher_btn = ui.button('启动自动监控', on_click=self._toggle_watcher_from_banner) \
                    .classes('bg-blue-600 text-white shadow-md hover:bg-blue-700 rounded-lg')
    
    def _update_status_banner_export_path(self):
        """更新状态横幅中的导出路径"""
        if hasattr(self, 'export_path_label') and self.export_path_display:
            self.export_path_label.text = f'📁 导出: {self.export_path_display}'

    def _render_available_dramas(self):
        """渲染可选剧目列表到容器"""
        # 注意：NiceGUI 的 Element 在某些版本/模式下可能会被 bool() 判定为 False
        # 这里必须使用 is None 判断，否则会导致渲染逻辑被错误跳过（列表空白）
        if self.available_dramas_container is None:
            return
        # 清空容器
        self.available_dramas_container.clear()
        
        with self.available_dramas_container:
            # 如果没有选择目录
            if not self.root_dir:
                with ui.column().classes('w-full py-8 items-center text-center'):
                    ui.icon('folder_off', color='grey').classes('text-5xl mb-3 opacity-50')
                    ui.label('请先在设置中选择素材目录').classes('text-gray-400')
                return
            
            # 如果选择了目录但没有剧目
            if not self.filtered_drama_names:
                with ui.column().classes('w-full py-8 items-center text-center'):
                    ui.icon('search_off', color='grey').classes('text-5xl mb-3 opacity-50')
                    ui.label('未找到剧目').classes('text-gray-400')
                    ui.label(f'目录: {self.root_dir}').classes('text-xs text-gray-300 mt-2')
                return
            
            # 显示剧目数量
            ui.label(f'共 {len(self.filtered_drama_names)} 部剧目').classes('text-sm text-gray-500 mb-2')
            
            # 渲染剧目列表
            for name in self.filtered_drama_names:
                is_selected = name in self.selected_drama_names
                
                with ui.card().classes('w-full mb-2 p-3 cursor-pointer hover:shadow-md transition-shadow'):
                    with ui.row().classes('w-full items-center justify-between gap-3'):
                        # 剧目图标
                        ui.icon('movie', color='grey').classes('text-2xl')
                        
                        # 剧名
                        ui.label(name).classes('flex-1 font-medium text-sm')
                        
                        if is_selected:
                            ui.icon('check_circle', color='positive').classes('text-green-500')
                        else:
                            ui.button('选择', on_click=lambda n=name: self._add_drama(n)) \
                                .props('flat dense size=sm color=primary')

    def _render_selected_dramas(self):
        """渲染已选剧目列表到容器"""
        # 同上：必须使用 is None 判断，避免 bool(Element)==False 导致渲染被跳过
        if self.selected_dramas_container is None:
            return
        # 清空容器
        self.selected_dramas_container.clear()
        
        with self.selected_dramas_container:
            if not self.selected_drama_names:
                ui.label('未选择剧目').classes('text-gray-400 text-center py-8')
                return
            
            for name in sorted(self.selected_drama_names):
                status = self.drama_status_map.get(name, DramaStatus.PENDING)
                
                with ui.card().classes('w-full mb-2 p-3'):
                    with ui.row().classes('w-full items-center gap-3'):
                        # 状态徽章
                        ui.badge(status.label, color=status.color) \
                            .props('outline' if status != DramaStatus.PROCESSING else '')
                        
                        # 剧名
                        ui.label(name).classes('flex-1 font-medium text-sm')
                        
                        # 删除按钮（仅在 pending 状态可删除）
                        if status == DramaStatus.PENDING:
                            ui.button(icon='delete', on_click=lambda n=name: self._remove_drama(n)) \
                                .props('flat dense round size=sm color=negative')
                        
                        # 处理中动画
                        if status == DramaStatus.PROCESSING:
                            ui.spinner(size='sm', color='orange')

    def _open_settings_dialog(self):
        """打开设置弹窗"""
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-3xl p-0 overflow-hidden'):
            # 弹窗 Header
            with ui.row().classes('w-full bg-gray-50 p-4 border-b border-gray-200 items-center justify-between'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('tune', color='primary')
                    ui.label('全局设置').classes('text-lg font-bold text-gray-800')
                ui.button(icon='close', on_click=dialog.close).props('flat round dense').classes('text-gray-500 hover:text-gray-700').tooltip('关闭')
            
            # 弹窗 Content
            with ui.scroll_area().classes('h-[60vh] w-full p-6'):
                with ui.column().classes('w-full gap-6'):
                    
                    # 1. 路径设置
                    with ui.column().classes('w-full gap-4'):
                        ui.label('📁 路径配置').classes('text-base font-bold text-gray-700')
                        
                        # 素材目录
                        ui.label('素材根目录').classes('text-sm text-gray-500')
                        with ui.row().classes('w-full gap-2'):
                            ui.input(placeholder='选择素材存放的文件夹').classes('flex-1').props('outlined dense') \
                                .bind_value(self, 'root_dir').on('change', self._on_root_dir_change)
                            ui.button('浏览', on_click=self._choose_root).classes('bg-gray-100 text-gray-700 shadow-sm border border-gray-200')

                        # 输出目录
                        ui.label('输出目录').classes('text-sm text-gray-500')
                        with ui.row().classes('w-full gap-2'):
                            ui.input(placeholder='处理完成后保存的位置').classes('flex-1').props('outlined dense') \
                                .bind_value(self, 'output_dir')
                            ui.button('浏览', on_click=self._choose_output).classes('bg-gray-100 text-gray-700 shadow-sm border border-gray-200')
                        
                        # 字体文件
                        ui.label('字体文件').classes('text-sm text-gray-500')
                        with ui.row().classes('w-full gap-2'):
                            ui.input(placeholder='自定义字体文件 (.ttf/.ttc)').classes('flex-1').props('outlined dense') \
                                .bind_value(self, 'font_file')
                            ui.button('浏览', on_click=self._choose_font).classes('bg-gray-100 text-gray-700 shadow-sm border border-gray-200')

                        # 剪辑日期
                        ui.label('剪辑日期 (可选)').classes('text-sm text-gray-500')
                        ui.input(placeholder='例如: 12.24').classes('w-full').props('outlined dense') \
                            .bind_value(self, 'date_str')

                    ui.separator()

                    # 2. 参数设置
                    with ui.column().classes('w-full gap-4'):
                        ui.label('⚡️ 处理参数').classes('text-base font-bold text-gray-700')
                        
                        with ui.grid(columns=2).classes('w-full gap-4'):
                            ui.input('素材条数').props('outlined dense type=number').bind_value(self, 'count')
                            ui.input('并发数量').props('outlined dense type=number').bind_value(self, 'jobs')
                            ui.input('最小时长 (秒)').props('outlined dense type=number').bind_value(self, 'min_duration')
                            ui.input('最大时长 (秒)').props('outlined dense type=number').bind_value(self, 'max_duration')
                        
                        # 素材用户名
                        ui.label('素材用户名标识').classes('text-sm text-gray-500 mt-2')
                        ui.input(placeholder='例如: xh, xl (用于导出文件名)').props('outlined dense').bind_value(self, 'material_code').classes('w-full')

                        with ui.row().classes('w-full gap-6 mt-2'):
                            ui.switch('硬件加速').bind_value(self, 'use_hw').props('color=primary')
                            ui.switch('快速模式').bind_value(self, 'fast_mode').props('color=primary')

                        # 字体大小设置
                        ui.label('字体大小设置').classes('text-sm font-bold text-gray-500 mt-2')
                        with ui.grid(columns=3).classes('w-full gap-4'):
                            ui.number('标题字号', min=10).props('outlined dense').bind_value(self, 'title_font_size', forward=lambda v: str(int(v)), backward=lambda v: int(v) if v else 55)
                            ui.number('侧边字号', min=10).props('outlined dense').bind_value(self, 'side_font_size', forward=lambda v: str(int(v)), backward=lambda v: int(v) if v else 35)
                            ui.number('底部字号', min=10).props('outlined dense').bind_value(self, 'bottom_font_size', forward=lambda v: str(int(v)), backward=lambda v: int(v) if v else 30)
                        
                        # 品牌文案配置
                        ui.label('品牌文案配置').classes('text-sm font-bold text-gray-500 mt-4')
                        ui.input('默认品牌文案').props('outlined dense').bind_value(self, 'brand_default').classes('w-full')
                        ui.label('素材范围映射 (可选)').classes('text-xs text-gray-400 mt-1')
                        ui.textarea(placeholder='每行一个映射，格式: 文案名=素材范围\n例如:\n萍通剧坊=01-03\n小红看剧=04-06').props('outlined rows=3').bind_value(self, 'brand_ranges').classes('w-full')

                    ui.separator()

                    # 3. 飞书配置
                    with ui.column().classes('w-full gap-4'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('cloud', color='primary')
                            ui.label('飞书集成').classes('text-base font-bold text-gray-700')
                            ui.switch().bind_value(self, 'enable_feishu').props('color=primary')
                        
                        with ui.column().classes('w-full gap-3 pl-6 border-l-2 border-gray-100').bind_visibility_from(self, 'enable_feishu'):
                            ui.input('App ID').props('outlined dense type=password').bind_value(self, 'feishu_app_id').classes('w-full')
                            ui.input('App Secret').props('outlined dense type=password').bind_value(self, 'feishu_app_secret').classes('w-full')
                            ui.input('App Token').props('outlined dense type=password').bind_value(self, 'feishu_app_token').classes('w-full')
                            ui.input('Table ID').props('outlined dense type=password').bind_value(self, 'feishu_table_id').classes('w-full')

            # 弹窗 Footer
            with ui.row().classes('w-full bg-gray-50 p-4 border-t border-gray-200 justify-end gap-2'):
                ui.button('关闭', on_click=dialog.close).classes('bg-white text-gray-700 border border-gray-300 shadow-sm hover:bg-gray-50')
                ui.button('保存配置', on_click=lambda: [self._save_config_manually(), dialog.close()]).classes('bg-indigo-600 text-white shadow-md hover:bg-indigo-700')
            
            dialog.open()

    def _save_config_manually(self):
        """手动保存配置"""
        ui.notify('配置已暂存', type='positive')
    
    def _clear_logs(self):
        """清空日志"""
        if self.log_container:
            self.log_container.clear()
        self.log_count = 0
        if hasattr(self, 'log_status_badge'):
            self.log_status_badge.text = '0 条'
        ui.notify('日志已清空', type='info')

    def _add_drama(self, name: str):
        """添加剧目到已选列表"""
        if name in self.selected_drama_names:
            return
        
        self.selected_drama_names.add(name)
        
        # 根据当前是否在处理中决定初始状态
        if self.is_running:
            # 自动追加模式：直接设为 queued 并加入队列
            self.drama_status_map[name] = DramaStatus.QUEUED
            self.drama_queue.append(name)
            ui.notify(f'已追加 {name} 到处理队列', type='positive')
        else:
            # 正常模式：设为 pending
            self.drama_status_map[name] = DramaStatus.PENDING
        
        # 刷新UI
        self._render_available_dramas()
        self._render_selected_dramas()
        self._update_process_btn_state()

    def _remove_drama(self, name: str):
        """从已选列表移除剧目"""
        if name not in self.selected_drama_names:
            return
        
        status = self.drama_status_map.get(name, DramaStatus.PENDING)
        
        # 只允许删除 pending 状态的剧目
        if status != DramaStatus.PENDING:
            ui.notify(f'无法删除：{name} 已在处理中或已完成', type='warning')
            return
        
        self.selected_drama_names.discard(name)
        self.drama_status_map.pop(name, None)
        
        # 刷新UI
        self._render_available_dramas()
        self._render_selected_dramas()
        self._update_process_btn_state()

    def _batch_change_status(self, dramas: List[str], new_status: DramaStatus):
        """批量修改剧目状态"""
        for name in dramas:
            if name in self.selected_drama_names:
                self.drama_status_map[name] = new_status
        
        self._render_selected_dramas()

    def _update_process_btn_state(self):
        """更新处理按钮状态"""
        count = len(self.selected_drama_names)
        if hasattr(self, 'process_btn'):
            self.process_btn.text = f'开始处理选中 ({count})'
            if count > 0:
                self.process_btn.enable()
            else:
                self.process_btn.disable()

    def _toggle_watcher_from_banner(self):
        """从横幅切换监控状态"""
        if self.is_watcher_running:
            self._stop_watcher()
        else:
            self._start_watcher()
    
    
    # ========== 事件处理方法 ==========
    
    async def _choose_root(self):
        """选择素材根目录"""
        # 在浏览器模式下，使用 tkinter 文件对话框
        try:
            from tkinter import filedialog
            import tkinter as tk
            
            # 创建隐藏的 tk 根窗口
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            result = filedialog.askdirectory(title='选择素材根目录')
            root.destroy()
            
            if result:
                self.root_dir = result
                self._on_root_dir_change()
        except Exception as e:
            ui.notify(f'文件选择失败: {e}\n请手动输入路径', type='warning')
    
    async def _choose_output(self):
        """选择输出目录"""
        try:
            from tkinter import filedialog
            import tkinter as tk
            
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            result = filedialog.askdirectory(title='选择输出目录')
            root.destroy()
            
            if result:
                self.output_dir = result
        except Exception as e:
            ui.notify(f'文件选择失败: {e}\n请手动输入路径', type='warning')
    
    async def _choose_font(self):
        """选择字体文件"""
        try:
            from tkinter import filedialog
            import tkinter as tk
            
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            result = filedialog.askopenfilename(
                title='选择字体文件',
                filetypes=[('Font files', '*.ttf *.ttc *.otf'), ('All files', '*.*')]
            )
            root.destroy()
            
            if result:
                self.font_file = result
        except Exception as e:
            ui.notify(f'文件选择失败: {e}\n请手动输入路径', type='warning')
    
    def _on_root_dir_change(self):
        """素材目录变化时刷新剧目列表"""
        if self.root_dir:
            self._refresh_drama_list()
    
    def _refresh_drama_list(self):
        """刷新剧目列表"""
        if not self.root_dir or not Path(self.root_dir).is_dir():
            self.all_drama_names = []
            self.filtered_drama_names = []
            self.selected_drama_names = set()
            self.drama_status_map = {}
            self.processing_root = None
            ui.notify('请先选择有效的素材目录', type='warning')
            self._render_available_dramas()
            self._render_selected_dramas()
            return
        
        processing_root, preselect = self._resolve_list_root(self.root_dir)
        self.processing_root = processing_root
        
        try:
            drama_dirs = scan_drama_dirs(processing_root)
            names = sorted([Path(p).name for p in drama_dirs])
            
            # 先保存旧的选择（如果不清空的话）
            # 这里我们清空以确保状态一致
            self.all_drama_names = names
            self.filtered_drama_names = names.copy()
            self.selected_drama_names = set()
            self.drama_status_map = {}
            
            if preselect:
                self._add_drama(preselect)  # 使用 _add_drama 以正确初始化状态
            
            # 强制刷新 UI
            self._render_available_dramas()
            self._render_selected_dramas()
            self._update_process_btn_state()
            
            # 显示扫描结果（带详细信息）
            if names:
                ui.notify(f'✅ 已扫描到 {len(names)} 部剧目', type='positive')
            else:
                ui.notify(f'⚠️ 目录 {processing_root} 中未找到剧目', type='warning')
        except Exception as e:
            self.all_drama_names = []
            self.filtered_drama_names = []
            ui.notify(f'❌ 扫描失败: {e}', type='negative')
            self._render_available_dramas()
            self._render_selected_dramas()

    def _resolve_list_root(self, root_dir: str) -> Tuple[str, Optional[str]]:
        """解析列表根目录"""
        path = Path(root_dir)
        if not path.is_dir():
            return root_dir, None
        
        subdirs = [p for p in path.iterdir() if p.is_dir() and not p.name.startswith('.')]
        if len(subdirs) == 1:
            single_dir = subdirs[0]
            video_files = list(single_dir.glob('*.mp4')) + list(single_dir.glob('*.mkv')) + list(single_dir.glob('*.avi'))
            if video_files:
                return root_dir, single_dir.name
        
        return root_dir, None

    def _on_drama_filter_change(self, e):
        """剧目搜索过滤"""
        value = e.value
        if not value:
            self.filtered_drama_names = self.all_drama_names.copy()
        else:
            # 支持多行粘贴（自动分割）
            search_terms = {t.strip().lower() for t in value.replace('\n', ' ').split() if t.strip()}
            
            if not search_terms:
                self.filtered_drama_names = self.all_drama_names.copy()
            else:
                self.filtered_drama_names = []
                for name in self.all_drama_names:
                    name_lower = name.lower()
                    # 只要匹配任一关键词即可（批量选择模式）
                    if any(term in name_lower for term in search_terms):
                        self.filtered_drama_names.append(name)
                        # 如果是精确匹配（通常是粘贴），自动选中
                        if name_lower in search_terms:
                            self._add_drama(name)
        
        self._render_available_dramas()
        self._render_selected_dramas()
        self._update_process_btn_state()

    
    
    def _cancel_processing(self):
        """取消处理"""
        if not self.is_running:
            return
        
        self.cancel_event.set()
        ui.notify('正在取消...', type='info')
    
    def _collect_overrides(self) -> Dict:
        """收集配置覆盖"""
        # 注意：ui.number 绑定的值已经是数字类型，无需再解析
        count = int(self.count) if isinstance(self.count, (int, float)) else _parse_int(str(self.count), "素材条数")
        min_dur = float(self.min_duration) if isinstance(self.min_duration, (int, float)) else _parse_float(str(self.min_duration), "最小时长")
        max_dur = float(self.max_duration) if isinstance(self.max_duration, (int, float)) else _parse_float(str(self.max_duration), "最大时长")
        jobs = int(self.jobs) if isinstance(self.jobs, (int, float)) else _parse_int(str(self.jobs), "并发数")
        title_font_size = int(self.title_font_size) if isinstance(self.title_font_size, (int, float)) else _parse_int(str(self.title_font_size), "标题字号")
        side_font_size = int(self.side_font_size) if isinstance(self.side_font_size, (int, float)) else _parse_int(str(self.side_font_size), "侧边字号")
        bottom_font_size = int(self.bottom_font_size) if isinstance(self.bottom_font_size, (int, float)) else _parse_int(str(self.bottom_font_size), "底部字号")
        
        if count <= 0:
            raise ValueError("素材条数必须大于 0")
        if jobs <= 0:
            raise ValueError("并发数必须大于 0")
        if min_dur <= 0 or max_dur <= 0:
            raise ValueError("时长必须大于 0")
        if min_dur > max_dur:
            raise ValueError("最小时长不能大于最大时长")
        
        overrides = {
            "count": count,
            "min_duration": min_dur,
            "max_duration": max_dur,
            "jobs": jobs,
            "use_hardware": self.use_hw,
            "fast_mode": self.fast_mode,
            "keep_temp": self.keep_temp,
            "verbose": self.verbose,
            "enable_feishu_features": self.enable_feishu,
            "enable_feishu_notification": self.enable_feishu,
            "title_font_size": title_font_size,
            "side_font_size": side_font_size,
            "bottom_font_size": bottom_font_size,
        }
        
        # 添加素材用户名标识
        if self.material_code:
            overrides["material_code"] = self.material_code
        
        # 添加源素材目录
        if self.processing_root:
            overrides["default_source_dir"] = self.processing_root
            overrides["backup_source_dir"] = self.processing_root
        
        # 添加日期
        if self.date_str:
            overrides["date_str"] = self.date_str
        
        # 添加输出目录
        if self.output_dir:
            overrides["output_dir"] = self.output_dir
        
        # 添加字体文件
        if self.font_file:
            overrides["font_file"] = self.font_file
        
        # 添加品牌文案
        if self.brand_ranges:
            brand_ranges = self._parse_brand_ranges()
            if brand_ranges:
                overrides["brand_text_mapping"] = {
                    "mode": "range",
                    "ranges": brand_ranges,
                    "default_text": self.brand_default or self._base_brand_text,
                }
                overrides["brand_text"] = self.brand_default or self._base_brand_text
                overrides["enable_brand_text"] = True
        elif self.brand_default:
            overrides["brand_text_mapping"] = None
            overrides["brand_text"] = self.brand_default
            overrides["enable_brand_text"] = True
        
        # 飞书配置
        if not self.enable_feishu:
            overrides["feishu_watcher"] = {"enabled": False}
        else:
            feishu_config = {}
            if self.feishu_app_id:
                feishu_config["app_id"] = self.feishu_app_id
            if self.feishu_app_secret:
                feishu_config["app_secret"] = self.feishu_app_secret
            if self.feishu_app_token:
                feishu_config["app_token"] = self.feishu_app_token
            if self.feishu_table_id:
                feishu_config["table_id"] = self.feishu_table_id
            
            if feishu_config:
                overrides["feishu"] = feishu_config
        
        return overrides
    
    def _parse_brand_ranges(self) -> List[Dict]:
        """解析品牌文案范围
        
        支持两种格式：
        1. 换行格式（推荐）：每行一个 "文案名=素材范围"
           例如：
           萍通剧坊=01-03
           小红看剧=04-06
        
        2. 逗号格式（兼容）：逗号分隔的 "素材范围:文案名"
           例如：01-03:萍通剧坊,04-06:小红看剧
        """
        if not self.brand_ranges:
            return []
        
        ranges = []
        text = self.brand_ranges.strip()
        
        # 检测格式：如果包含换行符，使用换行格式；否则使用逗号格式
        if '\n' in text or '=' in text:
            # 换行格式: 文案名=范围
            for line in text.split('\n'):
                line = line.strip()
                if not line or '=' not in line:
                    continue
                parts = line.split('=', 1)
                if len(parts) != 2:
                    continue
                text_name = parts[0].strip()
                range_str = parts[1].strip()
                if text_name and range_str:
                    ranges.append({"range": range_str, "text": text_name})
        else:
            # 逗号格式: 范围:文案（兼容旧格式）
            for item in text.split(','):
                item = item.strip()
                if ':' not in item:
                    continue
                parts = item.split(':', 1)
                if len(parts) != 2:
                    continue
                range_str, text_name = parts[0].strip(), parts[1].strip()
                if range_str and text_name:
                    ranges.append({"range": range_str, "text": text_name})
        
        return ranges
    
    async def _on_start_processing_click(self):
        """点击开始处理按钮"""
        if not self.selected_drama_names:
            ui.notify('请先选择剧目', type='warning')
            return
        
        # 初始化队列（仅包含 pending 状态的剧目）
        pending_dramas = [
            name for name in self.selected_drama_names 
            if self.drama_status_map.get(name, DramaStatus.PENDING) == DramaStatus.PENDING
        ]
        
        if not pending_dramas:
            ui.notify('没有待处理的剧目', type='warning')
            return
        
        # 将所有 pending 改为 queued
        self._batch_change_status(pending_dramas, DramaStatus.QUEUED)
        self.drama_queue.extend(pending_dramas)
        
        # 准备配置
        overrides = self._collect_overrides()
        selected_list = list(self.selected_drama_names)
        
        # 启动后台线程
        self.is_running = True
        self.cancel_event.clear()
        self.completed_dramas = 0
        self.total_dramas = 0
        self._set_ui_running(True)
        
        self.processing_thread = threading.Thread(
            target=self._run_processing_with_queue,
            args=(self.root_dir, self.config_path, overrides, selected_list),
            daemon=True
        )
        self.processing_thread.start()
        
        ui.notify('开始处理队列中的剧目...', type='positive')

    def _run_processing_with_queue(self, root_dir: str, config_path: Optional[str], 
                                   overrides: Dict, selected_dramas: List[str]):
        """带队列支持的处理方法（在后台线程运行）"""
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        try:
            # 加载配置
            config = self._load_config(config_path)
            self._apply_overrides(config, overrides)
            
            processing_root, single_drama_name, base_root = self._resolve_processing_root(root_dir)
            
            # 设置导出路径并通知UI
            exports_root = config.output_dir if os.path.isabs(config.output_dir) else os.path.join(root_dir, "exports")
            if config.date_str:
                exports_root = os.path.join(exports_root, f"{config.date_str}导出")
            self.export_path_display = exports_root
            self.log_queue.put(("export_path", exports_root))
            
            self._adjust_config_for_gui(config, base_root, selected_dramas)
            
            # 配置日志
            self._configure_logging(config.verbose)
            sys.stdout = StreamRedirector(self.log_queue, "stdout")
            sys.stderr = StreamRedirector(self.log_queue, "stderr")
            
            # 创建带回调的 Processor
            processor = DramaProcessor(config, cancel_event=self.cancel_event)
            
            # 注册状态回调
            def on_drama_start(drama_name: str):
                self.current_processing_drama = drama_name
                self.log_queue.put(("drama_start", drama_name))
            
            def on_drama_complete(drama_name: str):
                self.log_queue.put(("drama_complete", drama_name))
            
            # 处理队列中的所有剧目
            made, _ = processor.process_all_dramas(
                processing_root,
                on_drama_start=on_drama_start,
                on_drama_complete=on_drama_complete
            )
            
            self.log_queue.put(("done", f"处理完成，共生成 {made} 条素材。"))
            
        except CancelledError:
            self.log_queue.put(("cancelled", "已取消处理"))
        except Exception as exc:
            self.log_queue.put(("error", str(exc)))
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            self.log_queue.put(("finish", ""))
    
    def _load_config(self, config_path: Optional[str]) -> ProcessingConfig:
        """加载配置"""
        if config_path:
            # 用户指定了配置文件，使用指定的配置
            return load_config(config_path)
        
        # 尝试自动加载 default.yaml
        default_config_paths = [
            Path("configs/default.yaml"),
            Path("config/default.yaml"),
            Path.cwd() / "configs" / "default.yaml",
            Path.cwd() / "config" / "default.yaml",
        ]
        
        for config_file in default_config_paths:
            if config_file.exists():
                return load_config(str(config_file))
        
        # 如果找不到 default.yaml，使用内置默认配置
        return get_default_config()
    
    def _apply_overrides(self, config: ProcessingConfig, overrides: Dict):
        """应用配置覆盖"""
        from ..models.feishu import FeishuConfig
        
        for key, value in overrides.items():
            if key == "brand_text_mapping" and isinstance(value, dict):
                value = BrandTextMapping(**value)
            elif key == "feishu_watcher" and isinstance(value, dict):
                value = FeishuWatcherConfig(**value)
            elif key == "feishu" and isinstance(value, dict):
                if config.feishu:
                    for feishu_key, feishu_value in value.items():
                        setattr(config.feishu, feishu_key, feishu_value)
                    continue
                else:
                    value = FeishuConfig(**value)
            setattr(config, key, value)
    
    def _resolve_processing_root(self, root_dir: str) -> Tuple[str, Optional[str], str]:
        """解析处理根目录"""
        path = Path(root_dir)
        if not path.is_dir():
            return root_dir, None, root_dir
        
        subdirs = [p for p in path.iterdir() if p.is_dir() and not p.name.startswith('.')]
        if len(subdirs) == 1:
            single_dir = subdirs[0]
            video_files = list(single_dir.glob('*.mp4')) + list(single_dir.glob('*.mkv')) + list(single_dir.glob('*.avi'))
            if video_files:
                return root_dir, single_dir.name, root_dir
        
        return root_dir, None, root_dir
    
    def _adjust_config_for_gui(self, config: ProcessingConfig, base_root: str, selected_dramas: List[str]):
        """调整配置以适应 GUI"""
        config.full = True
        config.no_interactive = True
        
        if selected_dramas:
            config.include = selected_dramas
            config.exclude = None
            if config.output_dir and not os.path.isabs(config.output_dir):
                config.output_dir = os.path.abspath(os.path.join(base_root, "exports"))
        
        if _is_windows():
            if not config.temp_dir or config.temp_dir.startswith("/tmp"):
                config.temp_dir = tempfile.gettempdir()
    
    def _calculate_total_dramas(self, processing_root: str, config: ProcessingConfig) -> int:
        """计算待处理剧目总数"""
        all_dirs = scan_drama_dirs(processing_root)
        return len(self._filter_dramas(all_dirs, config))
    
    def _filter_dramas(self, drama_dirs: List[str], config: ProcessingConfig) -> List[str]:
        """过滤剧目"""
        filtered = []
        for drama_dir in drama_dirs:
            name = Path(drama_dir).name
            
            if config.include:
                if name not in config.include:
                    continue
            
            if config.exclude:
                if name in config.exclude:
                    continue
            
            filtered.append(drama_dir)
        
        return filtered
    
    def _set_ui_running(self, running: bool):
        """设置 UI 运行状态"""
        if hasattr(self, 'process_btn'):
            self.process_btn.set_visibility(not running)
        if hasattr(self, 'cancel_btn'):
            self.cancel_btn.set_visibility(running)
            # 初始状态下 props('hidden') 可能导致 visible 属性不同步，这里强制移除 hidden
            if running:
                self.cancel_btn.props(remove='hidden')
        
        if hasattr(self, 'watcher_btn'):
            # 如果正在手动处理，禁用轮询按钮
            self.watcher_btn.enabled = not running and not self.is_watcher_running
    
    def _poll_log_queue(self):
        """轮询日志队列"""
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                
                if kind in {"log", "stdout", "stderr"}:
                    if payload and self.log_container:
                        self.log_container.push(payload)
                        self.log_count += 1
                        if hasattr(self, 'log_status_badge'):
                            self.log_status_badge.text = f'{self.log_count} 条'
                        if "本剧完成" in payload:
                            self.completed_dramas += 1
                            self._update_progress()
                
                elif kind == "total":
                    try:
                        self.total_dramas = int(payload)
                    except ValueError:
                        self.total_dramas = 0
                    self._update_progress(reset=True)
                
                elif kind == "status":
                    self.status_text = payload
                    if self.status_label:
                        self.status_label.text = payload
                
                elif kind == "done":
                    if self.log_container:
                        self.log_container.push(payload)
                
                elif kind == "error":
                    if self.log_container:
                        self.log_container.push(f"❌ {payload}")
                    self.status_text = "处理失败"
                    if self.status_label:
                        self.status_label.text = "处理失败"
                
                elif kind == "cancelled":
                    if self.log_container:
                        self.log_container.push(payload)
                    self.status_text = "已取消"
                    if self.status_label:
                        self.status_label.text = "已取消"
                
                elif kind == "finish":
                    self.is_running = False
                    self._set_ui_running(False)
                    if self.status_text in {"处理完成", "处理失败", "未发现可处理剧目", "已取消"}:
                        ui.notify(self.status_text, type='info')
                
                elif kind == "watcher_stopped":
                    self.is_watcher_running = False
                    self._set_watcher_ui(False)
                    self.status_text = "轮询已停止"
                    if self.status_label:
                        self.status_label.text = "轮询已停止"
                    ui.notify("飞书轮询已停止", type='info')
                
                elif kind == "watcher_error":
                    self.is_watcher_running = False
                    self._set_watcher_ui(False)
                    self.status_text = "轮询出错"
                    if self.status_label:
                        self.status_label.text = "轮询出错"
                    ui.notify(f"轮询出错: {payload}", type='negative')
                
                elif kind == "export_path":
                    # 更新导出路径显示
                    self.export_path_display = payload
                    self._update_status_banner_export_path()
                
                elif kind == "drama_start":
                    # 剧目开始处理：pending/queued → processing
                    drama_name = payload
                    self.drama_status_map[drama_name] = DramaStatus.PROCESSING
                    self.current_processing_drama = drama_name
                    self._render_selected_dramas()
                
                elif kind == "drama_complete":
                    # 剧目完成处理：processing → completed
                    drama_name = payload
                    self.drama_status_map[drama_name] = DramaStatus.COMPLETED
                    if drama_name in self.drama_queue:
                        self.drama_queue.remove(drama_name)
                    self.current_processing_drama = None
                    self._render_selected_dramas()
                    
        except queue.Empty:
            pass
    
    def _update_progress(self, reset: bool = False):
        """更新进度"""
        if reset:
            self.completed_dramas = 0
        
        if self.progress_label:
            self.progress_label.text = f'进度: {self.completed_dramas}/{self.total_dramas}'
        
        if self.progress_bar and self.total_dramas > 0:
            progress = self.completed_dramas / self.total_dramas
            self.progress_bar.value = progress
    
    def _fetch_dramas_from_feishu(self):
        """从飞书拉取剧目"""
        if not self.enable_feishu:
            ui.notify('请先启用飞书功能', type='warning')
            return
        
        if not all([self.feishu_app_id, self.feishu_app_secret, 
                    self.feishu_app_token, self.feishu_table_id]):
            ui.notify('请填写完整的飞书配置', type='warning')
            return
        
        date_str = self.date_str.strip()
        if not date_str:
            ui.notify('请先填写剪辑日期', type='warning')
            return
        
        try:
            from ..integrations.feishu_client import FeishuClient, _convert_date_format
            from ..models.feishu import FeishuConfig
            
            # 转换日期格式
            converted_date = _convert_date_format(date_str)
            
            # 创建 Feishu 客户端
            feishu_config = FeishuConfig(
                app_id=self.feishu_app_id,
                app_secret=self.feishu_app_secret,
                app_token=self.feishu_app_token,
                table_id=self.feishu_table_id
            )
            client = FeishuClient(feishu_config)
            
            # 获取剧目
            dramas = client.get_pending_dramas_with_dates(date_filter=converted_date)
            
            if not dramas:
                ui.notify(f'未找到日期 {date_str} 的待剪辑剧目', type='info')
                return
            
            # 匹配本地剧目
            matched = set()
            unmatched = []
            
            for drama_name in dramas.keys():
                if drama_name in self.all_drama_names:
                    matched.add(drama_name)
                else:
                    unmatched.append(drama_name)
            
            # 更新选择
            if matched:
                self.selected_drama_names.update(matched)
                self._render_drama_list_refreshable.refresh()
                self._update_process_btn_state()
                ui.notify(f'从飞书拉取成功：{len(matched)} 部剧目已选择', type='positive')
            
            if unmatched:
                unmatched_str = ', '.join(unmatched[:3])
                if len(unmatched) > 3:
                    unmatched_str += f' 等{len(unmatched)}部'
                self.log_queue.put(("log", f"⚠️ 以下剧目在本地未找到: {unmatched_str}"))
            
        except Exception as e:
            ui.notify(f'从飞书拉取失败: {e}', type='negative')
    
    def _start_watcher(self):
        """启动飞书轮询"""
        if self.is_watcher_running:
            ui.notify('轮询已在运行中', type='info')
            return
        
        if self.is_running:
            ui.notify('请等待当前处理任务完成', type='warning')
            return
        
        if not self.enable_feishu:
            ui.notify('请先启用飞书功能', type='warning')
            return
        
        if not all([self.feishu_app_id, self.feishu_app_secret, 
                    self.feishu_app_token, self.feishu_table_id]):
            ui.notify('请填写完整的飞书配置', type='warning')
            return
        
        try:
            # 收集配置
            config_path = self.config_path or None
            config = self._load_config(config_path)
            
            # 应用覆盖
            overrides = self._collect_overrides()
            self._apply_overrides(config, overrides)
            
            # 启动轮询
            self.is_watcher_running = True
            self.watcher_stop_event.clear()
            self.status_text = "轮询中..."
            if self.status_label:
                self.status_label.text = "轮询中..."
            self._set_watcher_ui(True)
            
            self.log_queue.put(("log", "🚀 启动飞书轮询剪辑..."))
            self.log_queue.put(("log", f"⏱️  轮询间隔: {config.feishu_watcher.poll_interval}秒"))
            
            # 在后台线程运行
            self.watcher_thread = threading.Thread(
                target=self._run_watcher,
                args=(config,),
                daemon=True
            )
            self.watcher_thread.start()
            
        except Exception as e:
            self.is_watcher_running = False
            self._set_watcher_ui(False)
            ui.notify(f'启动轮询失败: {e}', type='negative')
    
    def _stop_watcher(self):
        """停止飞书轮询"""
        if not self.is_watcher_running:
            return
        
        self.log_queue.put(("log", "⏹️ 正在停止轮询..."))
        self.status_text = "正在停止轮询..."
        if self.status_label:
            self.status_label.text = "正在停止轮询..."
        self.watcher_stop_event.set()
    
    def _run_watcher(self, config: ProcessingConfig):
        """在后台线程中运行轮询任务"""
        try:
            from ..integrations.feishu_watcher import FeishuWatcher
            
            # 创建轮询器
            watcher = FeishuWatcher(
                config=config,
                poll_interval=config.feishu_watcher.poll_interval,
                max_dates_per_cycle=config.feishu_watcher.max_dates_per_cycle,
                settle_seconds=config.feishu_watcher.settle_seconds,
                settle_rounds=config.feishu_watcher.settle_rounds,
                date_whitelist=config.feishu_watcher.date_whitelist,
                date_blacklist=config.feishu_watcher.date_blacklist,
                status_filter=config.feishu_watcher.status_filter,
                idle_exit_minutes=config.feishu_watcher.idle_exit_minutes,
                state_dir=config.feishu_watcher.state_dir,
                echo=lambda msg: self.log_queue.put(("log", msg))
            )
            
            # 注入停止检查
            original_stop = watcher._stop
            
            def check_stop():
                return original_stop or self.watcher_stop_event.is_set()
            
            class StopWrapper:
                def __bool__(self):
                    return check_stop()
            
            watcher._stop = StopWrapper()
            
            # 运行轮询
            watcher.run(run_once=False)
            
            self.log_queue.put(("log", "✅ 轮询已停止"))
            self.log_queue.put(("watcher_stopped", ""))
            
        except Exception as e:
            self.log_queue.put(("log", f"❌ 轮询出错: {e}"))
            self.log_queue.put(("watcher_error", str(e)))
    
    def _set_watcher_ui(self, running: bool):
        """设置轮询 UI 状态"""
        # 更新横幅样式
        if running:
            self.status_banner.classes(remove='bg-blue-50 border-blue-100', add='bg-green-50 border-green-100')
            self.status_icon.props('name=cloud_sync color=green').classes(remove='text-grey', add='text-green-500')
            self.status_title.text = '飞书自动监控运行中'
            self.status_desc.text = '正在持续监控飞书表格，新剧目将自动下载并处理'
            
            self.watcher_btn.text = '停止自动监控'
            self.watcher_btn.classes(remove='bg-blue-600 hover:bg-blue-700', add='bg-orange-500 hover:bg-orange-600')
            
            # 更新 Badge
            if hasattr(self, 'status_badge'):
                self.status_badge.text = '监控中'
                self.status_badge.props('color=green')
        else:
            self.status_banner.classes(remove='bg-green-50 border-green-100', add='bg-blue-50 border-blue-100')
            self.status_icon.props('name=cloud_off color=grey').classes(remove='text-green-500', add='text-grey')
            self.status_title.text = '飞书自动监控未启动'
            self.status_desc.text = '点击右侧按钮启动监控，自动处理飞书表格中的待剪辑剧目'
            
            self.watcher_btn.text = '启动自动监控'
            self.watcher_btn.classes(remove='bg-orange-500 hover:bg-orange-600', add='bg-blue-600 hover:bg-blue-700')

            # 更新 Badge
            if hasattr(self, 'status_badge'):
                self.status_badge.text = '就绪'
                self.status_badge.props('color=grey')
        
        # 禁用/启用手动开始按钮
        if hasattr(self, 'process_btn'):
            if running:
                self.process_btn.disable()
            else:
                self._update_process_btn_state()

    
    def _apply_default_values(self):
        """应用默认值"""
        # 尝试找到 Windows 字体
        if _is_windows() and not self.font_file:
            font = _find_windows_font()
            if font:
                self.font_file = font


def run_gui():
    """运行 GUI 应用"""
    import sys
    
    # 检查命令行参数
    native_mode = '--native' in sys.argv
    
    # 创建应用实例
    gui = DramaProcessorGUI()
    gui.build_ui()
    
    # 运行应用
    if native_mode:
        ui.run(
            title='短剧批量剪辑处理器',
            native=True,
            window_size=(1400, 900),
            reload=False
        )
    else:
        ui.run(
            title='短剧批量剪辑处理器',
            port=8080,
            reload=False
        )


if __name__ in {"__main__", "__mp_main__"}:
    run_gui()

