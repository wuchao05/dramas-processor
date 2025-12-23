"""短剧批量剪辑 GUI（NiceGUI 现代化版本）- Material Design 风格。"""

import asyncio
import logging
import os
import queue
import sys
import tempfile
import threading
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
        
        # 参数配置
        self.count = "10"
        self.min_duration = "480"
        self.max_duration = "900"
        self.jobs = "6"
        self.material_code = ""
        self.title_colors = ""
        self.brand_default = "热门短剧"
        self.brand_ranges = ""
        
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
        self.is_watcher_running = False
        self.total_dramas = 0
        self.completed_dramas = 0
        self.status_text = "就绪"
        
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
        level = logging.DEBUG if verbose else logging.INFO
        setup_logging(level=level)
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        gui_handler = GuiLogHandler(self.log_queue)
        gui_handler.setLevel(level)
        formatter = logging.Formatter('%(message)s')
        gui_handler.setFormatter(formatter)
        root_logger.addHandler(gui_handler)
        root_logger.setLevel(level)

    def build_ui(self):
        """构建 UI 界面"""
        # 设置深色主题和 Material Design 风格
        ui.colors(
            primary='#3F51B5',      # Indigo
            secondary='#E91E63',    # Pink
            accent='#00BCD4',       # Cyan
            positive='#4CAF50',     # Green
            negative='#F44336',     # Red
            info='#2196F3',         # Blue
            warning='#FF9800'       # Orange
        )
        
        # 主容器 - 使用滚动区域
        with ui.column().classes('w-full p-4 gap-4'):
            # Header
            with ui.card().classes('w-full'):
                with ui.row().classes('w-full items-center justify-between'):
                    ui.label('🎬 短剧批量剪辑处理器').classes('text-h4 text-primary')
                    self.status_label = ui.label(self.status_text).classes('text-h6')
            
            # 基础设置区域
            self._build_basic_settings()
            
            # 剧目选择区域
            self._build_drama_selection()
            
            # 参数配置和飞书配置（两列布局）
            with ui.row().classes('w-full gap-4'):
                with ui.column().classes('flex-1'):
                    self._build_params_config()
                with ui.column().classes('flex-1'):
                    self._build_feishu_config()
            
            # 操作按钮和进度
            self._build_operations()
            
            # 日志输出
            self._build_log_panel()
        
        # 启动日志轮询
        ui.timer(0.1, self._poll_log_queue)
        
        # 应用默认值
        self._apply_default_values()
    
    def _build_basic_settings(self):
        """构建基础设置区域"""
        with ui.card().classes('w-full'):
            ui.label('⚙️ 基础设置').classes('text-h6 text-primary mb-2')
            
            with ui.grid(columns=2).classes('w-full gap-2'):
                # 素材目录
                ui.label('素材目录:').classes('self-center')
                with ui.row().classes('flex-1 gap-2'):
                    ui.input(placeholder='选择素材根目录').classes('flex-1') \
                        .bind_value(self, 'root_dir') \
                        .on('change', self._on_root_dir_change)
                    ui.button('浏览', on_click=self._choose_root) \
                        .props('outline color=primary')
                
                # 配置文件
                ui.label('配置文件:').classes('self-center')
                with ui.row().classes('flex-1 gap-2'):
                    ui.input(placeholder='选择配置文件（可选）').classes('flex-1') \
                        .bind_value(self, 'config_path')
                    ui.button('浏览', on_click=self._choose_config) \
                        .props('outline color=primary')
                
                # 输出目录
                ui.label('输出目录:').classes('self-center')
                with ui.row().classes('flex-1 gap-2'):
                    ui.input(placeholder='输出目录').classes('flex-1') \
                        .bind_value(self, 'output_dir')
                    ui.button('浏览', on_click=self._choose_output) \
                        .props('outline color=primary')
                
                # 字体文件
                ui.label('字体文件:').classes('self-center')
                with ui.row().classes('flex-1 gap-2'):
                    ui.input(placeholder='字体文件路径（可选）').classes('flex-1') \
                        .bind_value(self, 'font_file')
                    ui.button('浏览', on_click=self._choose_font) \
                        .props('outline color=primary')
                
                # 剪辑日期
                ui.label('剪辑日期:').classes('self-center')
                with ui.column().classes('flex-1'):
                    ui.input(placeholder='如: 12.24（可选）').classes('w-full') \
                        .bind_value(self, 'date_str')
                    ui.label('填写后导出到: 输出目录/{日期}导出/') \
                        .classes('text-caption text-grey-6')
    
    def _build_drama_selection(self):
        """构建剧目选择区域"""
        with ui.card().classes('w-full'):
            ui.label('🎭 剧目选择').classes('text-h6 text-primary mb-2')
            
            # 搜索框和刷新按钮
            with ui.row().classes('w-full gap-2 mb-2'):
                self.drama_search_input = ui.input(
                    placeholder='搜索剧目（支持粘贴多行批量选择）'
                ).classes('flex-1').on('input', self._on_drama_filter_change)
                ui.button('刷新列表', on_click=self._refresh_drama_list) \
                    .props('outline color=primary icon=refresh')
            
            # 已选剧目标签
            with ui.row().classes('w-full gap-2 flex-wrap mb-2'):
                ui.label('已选剧目:').classes('font-bold')
                self.selected_chips_container = ui.row().classes('gap-1 flex-wrap')
            
            # 剧目表格
            self.drama_table = ui.table(
                columns=[
                    {'name': 'name', 'label': '剧名', 'field': 'name', 'align': 'left'},
                ],
                rows=[],
                selection='multiple',
                row_key='name'
            ).classes('w-full').props('flat bordered')
            # 使用 update:selected 事件而不是 selection
            self.drama_table.on('update:selected', self._on_drama_selection_change)
    
    def _build_params_config(self):
        """构建参数配置区域"""
        with ui.card().classes('w-full h-full'):
            ui.label('🎚️ 参数配置').classes('text-h6 text-primary mb-2')
            
            with ui.column().classes('w-full gap-2'):
                # 素材设置
                ui.label('素材设置').classes('font-bold text-subtitle2')
                ui.number('素材条数', value=10, min=1, max=100) \
                    .classes('w-full').bind_value(self, 'count', forward=lambda v: str(int(v)), backward=lambda v: int(v) if v else 10)
                ui.number('最小时长(秒)', value=480, min=60, max=3600) \
                    .classes('w-full').bind_value(self, 'min_duration', forward=lambda v: str(int(v)), backward=lambda v: int(v) if v else 480)
                ui.number('最大时长(秒)', value=900, min=60, max=3600) \
                    .classes('w-full').bind_value(self, 'max_duration', forward=lambda v: str(int(v)), backward=lambda v: int(v) if v else 900)
                ui.number('并发数', value=6, min=1, max=32) \
                    .classes('w-full').bind_value(self, 'jobs', forward=lambda v: str(int(v)), backward=lambda v: int(v) if v else 6)
                
                ui.separator()
                
                # 字体设置
                ui.label('字体设置').classes('font-bold text-subtitle2')
                ui.number('标题字号', value=55, min=20, max=100) \
                    .classes('w-full').bind_value(self, 'title_font_size', forward=lambda v: str(int(v)), backward=lambda v: int(v) if v else 55)
                ui.number('侧边字号', value=35, min=10, max=80) \
                    .classes('w-full').bind_value(self, 'side_font_size', forward=lambda v: str(int(v)), backward=lambda v: int(v) if v else 35)
                ui.number('底部字号', value=30, min=10, max=80) \
                    .classes('w-full').bind_value(self, 'bottom_font_size', forward=lambda v: str(int(v)), backward=lambda v: int(v) if v else 30)
                
                ui.separator()
                
                # 品牌文案
                ui.label('品牌文案').classes('font-bold text-subtitle2')
                ui.input('默认文案').classes('w-full') \
                    .bind_value(self, 'brand_default')
                ui.input('范围映射（如: 01-03:小红看剧）').classes('w-full') \
                    .bind_value(self, 'brand_ranges')
                
                ui.separator()
                
                # 开关选项
                ui.label('其他选项').classes('font-bold text-subtitle2')
                ui.switch('硬件加速').bind_value(self, 'use_hw')
                ui.switch('快速模式').bind_value(self, 'fast_mode')
                ui.switch('保留临时文件').bind_value(self, 'keep_temp')
                ui.switch('详细日志').bind_value(self, 'verbose')
    
    def _build_feishu_config(self):
        """构建飞书配置区域"""
        with ui.card().classes('w-full h-full'):
            ui.label('🚀 飞书配置').classes('text-h6 text-primary mb-2')
            
            with ui.column().classes('w-full gap-2'):
                # 启用开关
                ui.switch('启用飞书功能').bind_value(self, 'enable_feishu')
                
                ui.separator()
                
                # API 配置
                ui.label('API 配置').classes('font-bold text-subtitle2')
                ui.input('App ID').classes('w-full') \
                    .bind_value(self, 'feishu_app_id')
                ui.input('App Secret', password=True, password_toggle_button=True).classes('w-full') \
                    .bind_value(self, 'feishu_app_secret')
                ui.input('App Token').classes('w-full') \
                    .bind_value(self, 'feishu_app_token')
                ui.input('Table ID').classes('w-full') \
                    .bind_value(self, 'feishu_table_id')
                
                ui.separator()
                
                # 操作按钮
                ui.label('飞书操作').classes('font-bold text-subtitle2')
                ui.button('📥 从飞书拉取剧目', on_click=self._fetch_dramas_from_feishu) \
                    .props('color=positive').classes('w-full')
                ui.label('提示：在基础设置中填写日期后，点击此按钮获取该日期的待剪辑剧目') \
                    .classes('text-caption text-grey-6')
                
                with ui.row().classes('w-full gap-2'):
                    self.start_watcher_button = ui.button(
                        '🔄 启动轮询',
                        on_click=self._start_watcher
                    ).props('color=info').classes('flex-1')
                    self.stop_watcher_button = ui.button(
                        '⏹️ 停止轮询',
                        on_click=self._stop_watcher
                    ).props('color=warning outline').classes('flex-1')
                
                ui.label('提示：启动后将持续监控飞书表格，自动处理新增的待剪辑剧目') \
                    .classes('text-caption text-grey-6')
    
    def _build_operations(self):
        """构建操作区域"""
        with ui.card().classes('w-full'):
            ui.label('▶️ 操作').classes('text-h6 text-primary mb-2')
            
            # 按钮
            with ui.row().classes('w-full gap-4 mb-4'):
                self.start_button = ui.button(
                    '开始处理',
                    on_click=self._start_processing
                ).props('size=lg color=primary icon=play_arrow').classes('flex-1')
                
                self.cancel_button = ui.button(
                    '取消',
                    on_click=self._cancel_processing
                ).props('size=lg color=negative outline icon=stop').classes('flex-1')
            
            # 进度显示
            with ui.column().classes('w-full gap-2'):
                self.progress_label = ui.label('进度: 0/0').classes('font-bold')
                self.progress_bar = ui.linear_progress(value=0).classes('w-full')
    
    def _build_log_panel(self):
        """构建日志面板"""
        with ui.expansion('📋 日志输出', icon='description').classes('w-full'):
            with ui.card().classes('w-full bg-grey-9'):
                self.log_container = ui.log(max_lines=1000).classes('w-full h-96 text-white')
    
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
    
    async def _choose_config(self):
        """选择配置文件"""
        try:
            from tkinter import filedialog
            import tkinter as tk
            
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            result = filedialog.askopenfilename(
                title='选择配置文件',
                filetypes=[('YAML files', '*.yaml *.yml'), ('All files', '*.*')]
            )
            root.destroy()
            
            if result:
                self.config_path = result
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
        self.all_drama_names = []
        self.filtered_drama_names = []
        self.selected_drama_names = set()
        self.processing_root = None
        
        if not self.root_dir or not Path(self.root_dir).is_dir():
            ui.notify('请先选择有效的素材目录', type='warning')
            return
        
        processing_root, preselect = self._resolve_list_root(self.root_dir)
        self.processing_root = processing_root
        
        drama_dirs = scan_drama_dirs(processing_root)
        names = [Path(p).name for p in drama_dirs]
        self.all_drama_names = names
        self.filtered_drama_names = names.copy()
        
        if preselect:
            self.selected_drama_names = {preselect}
        
        self._update_drama_table()
        ui.notify(f'已扫描到 {len(names)} 部剧目', type='positive')
    
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
    
    def _update_drama_table(self):
        """更新剧目表格"""
        if self.drama_table is None:
            return
        
        rows = [
            {'name': name}
            for name in self.filtered_drama_names
        ]
        self.drama_table.rows = rows
        self.drama_table.selected = [
            row for row in rows if row['name'] in self.selected_drama_names
        ]
        self.drama_table.update()
        self._update_selected_chips()
    
    def _update_selected_chips(self):
        """更新已选剧目标签"""
        if self.selected_chips_container is None:
            return
        
        self.selected_chips_container.clear()
        with self.selected_chips_container:
            for name in sorted(self.selected_drama_names):
                with ui.chip(name, removable=True, on_remove=lambda n=name: self._remove_drama(n)):
                    pass
    
    def _remove_drama(self, name: str):
        """移除已选剧目"""
        self.selected_drama_names.discard(name)
        self._update_drama_table()
    
    def _on_drama_selection_change(self, e):
        """剧目选择变化"""
        # e.args 包含选中的行数据
        if hasattr(e, 'args') and e.args:
            self.selected_drama_names = {row['name'] for row in e.args}
        else:
            # 如果事件参数不对，从 table.selected 获取
            if self.drama_table and hasattr(self.drama_table, 'selected'):
                self.selected_drama_names = {row['name'] for row in self.drama_table.selected}
            else:
                self.selected_drama_names = set()
        self._update_selected_chips()
    
    def _on_drama_filter_change(self, e):
        """剧目过滤变化"""
        search_text = e.value.strip()
        
        # 检查是否是批量粘贴（多行）
        if '\n' in search_text:
            self._batch_select_dramas(search_text)
            if self.drama_search_input:
                self.drama_search_input.value = ''
            return
        
        # 普通过滤
        if not search_text:
            self.filtered_drama_names = self.all_drama_names.copy()
        else:
            search_lower = search_text.lower()
            self.filtered_drama_names = [
                name for name in self.all_drama_names
                if search_lower in name.lower()
            ]
        
        self._update_drama_table()
    
    def _batch_select_dramas(self, text: str):
        """批量选择剧目"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            return
        
        matched = set()
        unmatched = []
        
        for line in lines:
            # 精确匹配
            if line in self.all_drama_names:
                matched.add(line)
                continue
            
            # 模糊匹配
            best_match = None
            best_ratio = 0.6
            for name in self.all_drama_names:
                ratio = SequenceMatcher(None, line, name).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = name
            
            if best_match:
                matched.add(best_match)
            else:
                unmatched.append(line)
        
        self.selected_drama_names.update(matched)
        self._update_drama_table()
        
        if matched:
            ui.notify(f'已选择 {len(matched)} 部剧目', type='positive')
        if unmatched:
            ui.notify(f'未匹配到: {", ".join(unmatched[:3])}{"..." if len(unmatched) > 3 else ""}', type='warning')
    
    async def _start_processing(self):
        """开始处理"""
        if self.is_running:
            ui.notify('任务正在运行中', type='warning')
            return
        
        if not self.selected_drama_names:
            ui.notify('请先选择要处理的剧目', type='warning')
            return
        
        if not self.processing_root:
            ui.notify('请先选择素材目录', type='warning')
            return
        
        try:
            # 收集配置
            overrides = self._collect_overrides()
            
            # 启动处理
            self.is_running = True
            self.cancel_event.clear()
            self._set_ui_running(True)
            
            selected = list(self.selected_drama_names)
            
            # 在后台线程运行
            self.processing_thread = threading.Thread(
                target=self._run_processing,
                args=(self.processing_root, self.config_path or None, overrides, selected),
                daemon=True
            )
            self.processing_thread.start()
            
        except Exception as e:
            self.is_running = False
            self._set_ui_running(False)
            ui.notify(f'启动失败: {e}', type='negative')
    
    def _cancel_processing(self):
        """取消处理"""
        if not self.is_running:
            return
        
        self.cancel_event.set()
        ui.notify('正在取消...', type='info')
    
    def _collect_overrides(self) -> Dict:
        """收集配置覆盖"""
        count = _parse_int(self.count, "素材条数")
        min_dur = _parse_float(self.min_duration, "最小时长")
        max_dur = _parse_float(self.max_duration, "最大时长")
        jobs = _parse_int(self.jobs, "并发数")
        title_font_size = _parse_int(self.title_font_size, "标题字号")
        side_font_size = _parse_int(self.side_font_size, "侧边字号")
        bottom_font_size = _parse_int(self.bottom_font_size, "底部字号")
        
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
        """解析品牌文案范围"""
        if not self.brand_ranges:
            return []
        
        ranges = []
        for item in self.brand_ranges.split(','):
            item = item.strip()
            if ':' not in item:
                continue
            parts = item.split(':', 1)
            if len(parts) != 2:
                continue
            range_str, text = parts[0].strip(), parts[1].strip()
            if range_str and text:
                ranges.append({"range": range_str, "text": text})
        
        return ranges
    
    def _run_processing(self, root_dir: str, config_path: Optional[str], 
                       overrides: Dict, selected_dramas: List[str]):
        """在后台线程运行处理"""
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        try:
            # 加载配置
            config = self._load_config(config_path)
            self._apply_overrides(config, overrides)
            
            processing_root, single_drama_name, base_root = self._resolve_processing_root(root_dir)
            
            if not selected_dramas and single_drama_name:
                selected_dramas = [single_drama_name]
            
            self._adjust_config_for_gui(config, base_root, selected_dramas)
            
            # 配置日志
            self._configure_logging(config.verbose)
            sys.stdout = StreamRedirector(self.log_queue, "stdout")
            sys.stderr = StreamRedirector(self.log_queue, "stderr")
            
            if single_drama_name and selected_dramas:
                self.log_queue.put(("log", f"检测到单剧目录，已默认勾选：{single_drama_name}"))
            
            # 计算总数
            total = self._calculate_total_dramas(processing_root, config)
            self.log_queue.put(("total", str(total)))
            if total == 0:
                self.log_queue.put(("status", "未发现可处理剧目"))
                self.log_queue.put(("done", "未发现可处理剧目，已结束。"))
                return
            
            # 开始处理
            processor = DramaProcessor(config, cancel_event=self.cancel_event)
            made, _ = processor.process_all_dramas(processing_root)
            self.log_queue.put(("status", "处理完成"))
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
            return load_config(config_path)
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
        if self.start_button:
            self.start_button.enabled = not running
        if self.cancel_button:
            self.cancel_button.enabled = running
        if self.start_watcher_button:
            self.start_watcher_button.enabled = not running and not self.is_watcher_running
    
    def _poll_log_queue(self):
        """轮询日志队列"""
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                
                if kind in {"log", "stdout", "stderr"}:
                    if payload and self.log_container:
                        self.log_container.push(payload)
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
                self._update_drama_table()
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
        if self.start_watcher_button:
            self.start_watcher_button.enabled = not running
        if self.stop_watcher_button:
            self.stop_watcher_button.enabled = running
        if self.start_button:
            self.start_button.enabled = not running
    
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

