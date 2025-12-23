"""短剧批量剪辑 GUI（CustomTkinter 现代化版本）。"""

import logging
import os
import queue
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk

import yaml

from ..config.defaults import get_default_config
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
        raise ValueError(f"{label}必须是整数") from exc


def _parse_float(value: str, label: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{label}必须是数字") from exc


class DramaProcessorGUI(ctk.CTk):
    """CustomTkinter GUI 主窗口 - 现代化版本。"""

    def __init__(self) -> None:
        super().__init__()
        
        # 设置主题和外观
        ctk.set_appearance_mode("dark")  # 深色模式: "dark" / "light" / "system"
        ctk.set_default_color_theme("blue")  # 主题色: "blue" / "green" / "dark-blue"
        
        self.title("短剧批量剪辑工具")
        self.geometry("1100x800")
        self.minsize(900, 700)

        self._log_queue: "queue.Queue[LogItem]" = queue.Queue()
        self._running = False
        self._total_dramas = 0
        self._completed_dramas = 0
        self._all_drama_names: List[str] = []
        self._filtered_drama_names: List[str] = []
        self._selected_drama_names: List[str] = []
        self._selected_drama_set: Set[str] = set()
        self._processing_root: Optional[str] = None
        self._cancel_event = threading.Event()
        self._base_brand_text = "热门短剧"
        self._updating_list = False  # 标志位：防止程序内部更新列表时触发选择事件

        self._init_vars()
        self._build_ui()
        self._set_running_ui(False)
        self._apply_default_values()

        self.after(100, self._poll_log_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_vars(self) -> None:
        self.var_root = tk.StringVar()
        self.var_config = tk.StringVar()
        self.var_output = tk.StringVar()
        self.var_font_file = tk.StringVar()
        self.var_filter = tk.StringVar()
        self.var_material_code = tk.StringVar()
        self.var_title_colors = tk.StringVar()
        self.var_brand_default = tk.StringVar()
        self.var_title_font_size = tk.StringVar()
        self.var_side_font_size = tk.StringVar()
        self.var_bottom_font_size = tk.StringVar()

        self.var_count = tk.StringVar()
        self.var_min_duration = tk.StringVar()
        self.var_max_duration = tk.StringVar()
        self.var_jobs = tk.StringVar()

        self.var_use_hw = tk.BooleanVar(value=True)
        self.var_fast_mode = tk.BooleanVar(value=True)
        self.var_keep_temp = tk.BooleanVar(value=False)
        self.var_verbose = tk.BooleanVar(value=False)
        self.var_enable_feishu = tk.BooleanVar(value=False)
        
        # 飞书配置变量
        self.var_feishu_app_id = tk.StringVar()
        self.var_feishu_app_secret = tk.StringVar()
        self.var_feishu_app_token = tk.StringVar()
        self.var_feishu_table_id = tk.StringVar()
        self.var_feishu_date = tk.StringVar()  # 飞书日期（如 12.12）

        self.var_status = tk.StringVar(value="就绪")
        self.var_progress = tk.StringVar(value="0/0")
        
        # 添加过滤器回调
        self.var_filter.trace_add("write", lambda *_: self._apply_drama_filter())

    def _build_ui(self) -> None:
        # 主容器 - 使用网格布局
        main = ctk.CTkScrollableFrame(self, fg_color="transparent")
        main.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # === 基础设置区域 ===
        form_frame = ctk.CTkFrame(main, corner_radius=10)
        form_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        form_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(form_frame, text="⚙️ 基础设置", font=("", 16, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(15, 10)
        )

        self._add_path_row(form_frame, 1, "素材目录", self.var_root, self._choose_root)
        self._add_path_row(form_frame, 2, "配置文件", self.var_config, self._choose_config)
        self._add_path_row(form_frame, 3, "输出目录", self.var_output, self._choose_output)
        self._add_path_row(form_frame, 4, "字体文件", self.var_font_file, self._choose_font, pady_bottom=15)

        # === 剧目选择区域 ===
        drama_frame = ctk.CTkFrame(main, corner_radius=10)
        drama_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 15))
        drama_frame.grid_columnconfigure(0, weight=1)
        drama_frame.grid_rowconfigure(2, weight=1)
        main.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(drama_frame, text="🎬 剧目选择", font=("", 16, "bold")).grid(
            row=0, column=0, sticky="w", padx=15, pady=(15, 10)
        )

        # 搜索框
        filter_frame = ctk.CTkFrame(drama_frame, fg_color="transparent")
        filter_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))
        filter_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(filter_frame, text="🔍 搜索:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.filter_entry = ctk.CTkEntry(
            filter_frame, 
            textvariable=self.var_filter, 
            placeholder_text="输入剧目名称筛选，支持粘贴多行批量选择..."
        )
        self.filter_entry.grid(row=0, column=1, sticky="ew")
        # 绑定粘贴事件处理批量选择
        self.filter_entry.bind("<<Paste>>", self._on_filter_paste)
        # 绑定 Ctrl+V (Command+V on Mac) 作为备用
        self.filter_entry.bind("<Control-v>", self._on_filter_paste)
        self.filter_entry.bind("<Command-v>", self._on_filter_paste)

        # 列表容器
        list_container = ctk.CTkFrame(drama_frame, fg_color="transparent")
        list_container.grid(row=2, column=0, sticky="nsew", padx=15, pady=(0, 10))
        list_container.grid_columnconfigure(0, weight=1)
        list_container.grid_columnconfigure(1, weight=1)
        list_container.grid_rowconfigure(1, weight=1)

        # 可选剧目列表
        ctk.CTkLabel(list_container, text="可选剧目", font=("", 13, "bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 5)
        )
        
        available_list_frame = ctk.CTkFrame(list_container)
        available_list_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        available_list_frame.grid_columnconfigure(0, weight=1)
        available_list_frame.grid_rowconfigure(0, weight=1)
        
        self.drama_listbox = tk.Listbox(
            available_list_frame,
            selectmode="extended",
            height=8,
            activestyle="none",
            bg="#2b2b2b",
            fg="#ffffff",
            selectbackground="#1f6aa5",
            selectforeground="#ffffff",
            font=("", 11),
            borderwidth=0,
            highlightthickness=0,
        )
        self.drama_listbox.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        drama_scrollbar = ctk.CTkScrollbar(available_list_frame, command=self.drama_listbox.yview)
        drama_scrollbar.grid(row=0, column=1, sticky="ns", pady=2)
        self.drama_listbox.configure(yscrollcommand=drama_scrollbar.set)
        # 使用鼠标释放和键盘事件，避免焦点变化导致的误触发
        self.drama_listbox.bind("<ButtonRelease-1>", self._on_drama_list_select)
        self.drama_listbox.bind("<space>", self._on_drama_list_select)
        self.drama_listbox.bind("<Return>", self._on_drama_list_select)

        # 已选剧目列表
        ctk.CTkLabel(list_container, text="已选剧目", font=("", 13, "bold")).grid(
            row=0, column=1, sticky="w", padx=(5, 0)
        )
        
        selected_list_frame = ctk.CTkFrame(list_container)
        selected_list_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 0))
        selected_list_frame.grid_columnconfigure(0, weight=1)
        selected_list_frame.grid_rowconfigure(0, weight=1)
        
        self.selected_listbox = tk.Listbox(
            selected_list_frame,
            selectmode="extended",
            height=8,
            activestyle="none",
            bg="#2b2b2b",
            fg="#ffffff",
            selectbackground="#1f6aa5",
            selectforeground="#ffffff",
            font=("", 11),
            borderwidth=0,
            highlightthickness=0,
        )
        self.selected_listbox.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        selected_scrollbar = ctk.CTkScrollbar(selected_list_frame, command=self.selected_listbox.yview)
        selected_scrollbar.grid(row=0, column=1, sticky="ns", pady=2)
        self.selected_listbox.configure(yscrollcommand=selected_scrollbar.set)

        # 列表操作按钮
        list_actions = ctk.CTkFrame(drama_frame, fg_color="transparent")
        list_actions.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 15))
        
        ctk.CTkButton(list_actions, text="🔄 刷新列表", command=self._refresh_drama_list, width=120).grid(
            row=0, column=0, padx=(0, 10)
        )
        ctk.CTkButton(list_actions, text="✅ 全选", command=self._select_all_dramas, width=100).grid(
            row=0, column=1, padx=(0, 10)
        )
        ctk.CTkButton(list_actions, text="❌ 清空选择", command=self._clear_drama_selection, width=120).grid(
            row=0, column=2, padx=(0, 10)
        )
        ctk.CTkButton(list_actions, text="➖ 移除选中", command=self._remove_selected_dramas, width=120).grid(
            row=0, column=3
        )

        # === 处理参数区域 ===
        opts_frame = ctk.CTkFrame(main, corner_radius=10)
        opts_frame.grid(row=2, column=0, sticky="ew", pady=(0, 15))
        
        ctk.CTkLabel(opts_frame, text="⚡ 处理参数", font=("", 16, "bold")).grid(
            row=0, column=0, columnspan=8, sticky="w", padx=15, pady=(15, 10)
        )

        # 第一行参数
        params_row1 = ctk.CTkFrame(opts_frame, fg_color="transparent")
        params_row1.grid(row=1, column=0, columnspan=8, sticky="ew", padx=15, pady=(0, 10))
        
        self._add_param_field(params_row1, 0, "素材条数", self.var_count, width=80)
        self._add_param_field(params_row1, 2, "最小时长(秒)", self.var_min_duration, width=80)
        self._add_param_field(params_row1, 4, "最大时长(秒)", self.var_max_duration, width=80)
        self._add_param_field(params_row1, 6, "并发数", self.var_jobs, width=60)

        # 第二行 - 复选框
        checks_row = ctk.CTkFrame(opts_frame, fg_color="transparent")
        checks_row.grid(row=2, column=0, columnspan=8, sticky="ew", padx=15, pady=(0, 10))
        
        ctk.CTkCheckBox(checks_row, text="硬件编码", variable=self.var_use_hw).grid(row=0, column=0, padx=(0, 20))
        ctk.CTkCheckBox(checks_row, text="快速模式", variable=self.var_fast_mode).grid(row=0, column=1, padx=(0, 20))
        ctk.CTkCheckBox(checks_row, text="保留临时文件", variable=self.var_keep_temp).grid(row=0, column=2, padx=(0, 20))
        ctk.CTkCheckBox(checks_row, text="详细日志", variable=self.var_verbose).grid(row=0, column=3)

        # 第三行 - 字体大小
        font_row = ctk.CTkFrame(opts_frame, fg_color="transparent")
        font_row.grid(row=3, column=0, columnspan=8, sticky="ew", padx=15, pady=(0, 15))
        
        self._add_param_field(font_row, 0, "标题字号", self.var_title_font_size, width=70)
        self._add_param_field(font_row, 2, "侧边字号", self.var_side_font_size, width=70)
        self._add_param_field(font_row, 4, "底部字号", self.var_bottom_font_size, width=70)

        # === 用户配置区域 ===
        user_frame = ctk.CTkFrame(main, corner_radius=10)
        user_frame.grid(row=3, column=0, sticky="ew", pady=(0, 15))
        user_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(user_frame, text="👤 用户配置", font=("", 16, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(15, 10)
        )

        # 第一行
        user_row1 = ctk.CTkFrame(user_frame, fg_color="transparent")
        user_row1.grid(row=1, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 10))
        user_row1.grid_columnconfigure(1, weight=1)
        user_row1.grid_columnconfigure(3, weight=1)
        
        ctk.CTkLabel(user_row1, text="素材标识:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        ctk.CTkEntry(user_row1, textvariable=self.var_material_code, width=100).grid(row=0, column=1, sticky="w")
        
        ctk.CTkLabel(user_row1, text="标题颜色:").grid(row=0, column=2, sticky="w", padx=(20, 10))
        ctk.CTkEntry(user_row1, textvariable=self.var_title_colors, placeholder_text="如: red, blue, #FF5733").grid(
            row=0, column=3, sticky="ew"
        )

        # 第二行
        user_row2 = ctk.CTkFrame(user_frame, fg_color="transparent")
        user_row2.grid(row=2, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 10))
        user_row2.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(user_row2, text="默认文案:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        ctk.CTkEntry(user_row2, textvariable=self.var_brand_default, placeholder_text="如: 热门短剧").grid(
            row=0, column=1, sticky="ew", padx=(0, 20)
        )
        
        ctk.CTkCheckBox(user_row2, text="启用飞书功能", variable=self.var_enable_feishu).grid(
            row=0, column=2, sticky="w"
        )

        # 多素材文案
        ctk.CTkLabel(user_frame, text="多素材文案(range):").grid(row=3, column=0, sticky="nw", padx=15, pady=(0, 5))
        
        self.brand_ranges_text = ctk.CTkTextbox(user_frame, height=80, wrap="word")
        self.brand_ranges_text.grid(row=4, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 5))
        
        ctk.CTkLabel(
            user_frame,
            text="格式示例：01-03=萍通剧坊（每行一条，支持 01-03 / 01,02 / 01）",
            text_color="gray60",
            font=("", 11)
        ).grid(row=5, column=0, columnspan=3, sticky="w", padx=15, pady=(0, 15))
        
        # 飞书配置区域（当启用飞书功能时显示）
        feishu_frame = ctk.CTkFrame(user_frame, fg_color="transparent")
        feishu_frame.grid(row=6, column=0, columnspan=3, sticky="ew", padx=15, pady=(10, 15))
        feishu_frame.grid_columnconfigure(1, weight=1)
        feishu_frame.grid_columnconfigure(3, weight=1)
        
        ctk.CTkLabel(feishu_frame, text="📱 飞书配置（启用飞书后填写）", font=("", 13, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 10)
        )
        
        # 第一行：app_id 和 app_secret
        ctk.CTkLabel(feishu_frame, text="App ID:").grid(row=1, column=0, sticky="w", padx=(0, 10))
        ctk.CTkEntry(feishu_frame, textvariable=self.var_feishu_app_id, placeholder_text="cli_xxxxx").grid(
            row=1, column=1, sticky="ew", padx=(0, 20)
        )
        
        ctk.CTkLabel(feishu_frame, text="App Secret:").grid(row=1, column=2, sticky="w", padx=(0, 10))
        ctk.CTkEntry(feishu_frame, textvariable=self.var_feishu_app_secret, placeholder_text="密钥", show="*").grid(
            row=1, column=3, sticky="ew"
        )
        
        # 第二行：app_token 和 table_id
        ctk.CTkLabel(feishu_frame, text="App Token:").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=(10, 0))
        ctk.CTkEntry(feishu_frame, textvariable=self.var_feishu_app_token, placeholder_text="表格令牌").grid(
            row=2, column=1, sticky="ew", padx=(0, 20), pady=(10, 0)
        )
        
        ctk.CTkLabel(feishu_frame, text="Table ID:").grid(row=2, column=2, sticky="w", padx=(0, 10), pady=(10, 0))
        ctk.CTkEntry(feishu_frame, textvariable=self.var_feishu_table_id, placeholder_text="tbl_xxxxx").grid(
            row=2, column=3, sticky="ew", pady=(10, 0)
        )
        
        # 第三行：日期和拉取按钮
        ctk.CTkLabel(feishu_frame, text="剪辑日期:").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=(10, 0))
        ctk.CTkEntry(feishu_frame, textvariable=self.var_feishu_date, placeholder_text="如: 12.12", width=100).grid(
            row=3, column=1, sticky="w", pady=(10, 0)
        )
        
        ctk.CTkButton(
            feishu_frame, 
            text="📥 从飞书拉取剧目", 
            command=self._fetch_dramas_from_feishu,
            fg_color="#2e7d32",
            hover_color="#1b5e20"
        ).grid(row=3, column=2, columnspan=2, sticky="ew", padx=(20, 0), pady=(10, 0))
        
        ctk.CTkLabel(
            feishu_frame,
            text="提示：填写日期后点击拉取，将自动从飞书表格获取该日期的待剪辑剧目",
            text_color="gray60",
            font=("", 10)
        ).grid(row=4, column=0, columnspan=4, sticky="w", pady=(5, 0))

        # === 操作按钮区域 ===
        actions_frame = ctk.CTkFrame(main, fg_color="transparent")
        actions_frame.grid(row=4, column=0, sticky="ew", pady=(0, 15))
        
        self.btn_start = ctk.CTkButton(
            actions_frame, 
            text="▶️ 开始处理", 
            command=self._start_processing,
            height=40,
            font=("", 14, "bold"),
            fg_color="#1f6aa5",
            hover_color="#1557b0"
        )
        self.btn_start.grid(row=0, column=0, padx=(0, 10))
        
        self.btn_cancel = ctk.CTkButton(
            actions_frame,
            text="⏹️ 取消处理",
            command=self._cancel_processing,
            height=40,
            font=("", 14, "bold"),
            fg_color="#d32f2f",
            hover_color="#b71c1c"
        )
        self.btn_cancel.grid(row=0, column=1, padx=(0, 10))
        
        ctk.CTkButton(
            actions_frame,
            text="🗑️ 清空日志",
            command=self._clear_logs,
            height=40,
            font=("", 14)
        ).grid(row=0, column=2)

        # === 进度显示区域 ===
        progress_frame = ctk.CTkFrame(main, corner_radius=10)
        progress_frame.grid(row=5, column=0, sticky="ew", pady=(0, 15))
        progress_frame.grid_columnconfigure(1, weight=1)
        
        self.status_label = ctk.CTkLabel(
            progress_frame, 
            textvariable=self.var_status,
            font=("", 13, "bold")
        )
        self.status_label.grid(row=0, column=0, sticky="w", padx=15, pady=12)
        
        self.progress_bar = ctk.CTkProgressBar(progress_frame, mode="indeterminate")
        self.progress_bar.grid(row=0, column=1, sticky="ew", padx=10, pady=12)
        self.progress_bar.set(0)
        
        self.progress_label = ctk.CTkLabel(
            progress_frame,
            textvariable=self.var_progress,
            font=("", 13)
        )
        self.progress_label.grid(row=0, column=2, sticky="e", padx=15, pady=12)

        # === 日志显示区域 ===
        log_frame = ctk.CTkFrame(main, corner_radius=10)
        log_frame.grid(row=6, column=0, sticky="nsew")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)
        main.grid_rowconfigure(6, weight=1)
        
        ctk.CTkLabel(log_frame, text="📋 处理日志", font=("", 16, "bold")).grid(
            row=0, column=0, sticky="w", padx=15, pady=(15, 10)
        )

        self.log_text = ctk.CTkTextbox(log_frame, height=200, wrap="word", font=("Consolas", 10))
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.log_text.configure(state="disabled")

    def _add_path_row(self, parent: ctk.CTkFrame, row: int, label: str, var: tk.StringVar, 
                      command, pady_bottom: int = 10) -> None:
        """添加路径选择行（标签 + 输入框 + 按钮）"""
        ctk.CTkLabel(parent, text=f"{label}:", width=80, anchor="w").grid(
            row=row, column=0, sticky="w", padx=(15, 10), pady=(0, pady_bottom)
        )
        ctk.CTkEntry(parent, textvariable=var).grid(
            row=row, column=1, sticky="ew", padx=(0, 10), pady=(0, pady_bottom)
        )
        ctk.CTkButton(parent, text="浏览", command=command, width=80).grid(
            row=row, column=2, sticky="e", padx=(0, 15), pady=(0, pady_bottom)
        )

    def _add_param_field(self, parent: ctk.CTkFrame, col: int, label: str, 
                        var: tk.StringVar, width: int = 100) -> None:
        """添加参数输入字段"""
        ctk.CTkLabel(parent, text=f"{label}:").grid(row=0, column=col, sticky="w", padx=(0, 5))
        ctk.CTkEntry(parent, textvariable=var, width=width).grid(
            row=0, column=col + 1, sticky="w", padx=(0, 20)
        )

    def _apply_default_values(self) -> None:
        default_config = resolve_asset_path("configs/default.yaml")
        if default_config:
            self.var_config.set(str(default_config))
        config = self._load_config(default_config)
        self._apply_config_to_form(config)

    def _choose_root(self) -> None:
        path = filedialog.askdirectory(title="选择素材目录")
        if path:
            self.var_root.set(path)
            self._refresh_drama_list()

    def _choose_config(self) -> None:
        path = filedialog.askopenfilename(
            title="选择配置文件",
            filetypes=[("YAML", "*.yaml *.yml"), ("所有文件", "*.*")],
        )
        if path:
            self.var_config.set(path)
            config = self._load_config(path)
            self._apply_config_to_form(config)

    def _choose_output(self) -> None:
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.var_output.set(path)

    def _choose_font(self) -> None:
        path = filedialog.askopenfilename(
            title="选择字体文件",
            filetypes=[("字体文件", "*.ttf *.ttc *.otf"), ("所有文件", "*.*")],
        )
        if path:
            self.var_font_file.set(path)

    def _apply_config_to_form(self, config: ProcessingConfig) -> None:
        self.var_count.set(str(config.count))
        self.var_min_duration.set(str(config.min_duration))
        self.var_max_duration.set(str(config.max_duration))
        self.var_jobs.set(str(config.jobs))
        self.var_use_hw.set(bool(config.use_hardware))
        self.var_fast_mode.set(bool(config.fast_mode))
        self.var_keep_temp.set(bool(config.keep_temp))
        self.var_verbose.set(bool(config.verbose))
        self.var_material_code.set(str(config.material_code))
        self.var_title_colors.set(", ".join(config.title_colors or []))
        self.var_enable_feishu.set(bool(config.enable_feishu_features))
        self.var_title_font_size.set(str(config.title_font_size))
        self.var_side_font_size.set(str(config.side_font_size))
        bottom_size = config.bottom_font_size
        if bottom_size == 8:
            bottom_size = 28
        self.var_bottom_font_size.set(str(bottom_size))
        if config.output_dir:
            self.var_output.set(str(config.output_dir))
        font_path = str(config.font_file) if config.font_file else ""
        if _is_windows():
            default_win_font = r"C:\Windows\Fonts\msyh.ttc"
            if not font_path or font_path.startswith("/") or not os.path.isfile(font_path):
                font_path = default_win_font
        if font_path:
            self.var_font_file.set(font_path)
        self._base_brand_text = config.brand_text or "热门短剧"
        default_text = self._base_brand_text
        ranges = None
        if config.brand_text_mapping:
            default_text = config.brand_text_mapping.default_text or default_text
            if config.brand_text_mapping.mode == "range":
                ranges = config.brand_text_mapping.ranges or []
        self.var_brand_default.set(default_text)
        self._set_brand_ranges(ranges or [])
        
        # 加载飞书配置
        if config.feishu:
            self.var_feishu_app_id.set(str(config.feishu.app_id or ""))
            self.var_feishu_app_secret.set(str(config.feishu.app_secret or ""))
            self.var_feishu_app_token.set(str(config.feishu.app_token or ""))
            self.var_feishu_table_id.set(str(config.feishu.table_id or ""))

    def _set_brand_ranges(self, ranges: List[BrandTextRange]) -> None:
        self.brand_ranges_text.delete("1.0", "end")
        for item in ranges:
            self.brand_ranges_text.insert("end", f"{item.range}={item.text}\n")

    def _parse_title_colors(self, raw: str) -> List[str]:
        if not raw.strip():
            return []
        parts: List[str] = []
        for chunk in raw.replace("\n", ",").split(","):
            color = chunk.strip()
            if color:
                parts.append(color)
        return parts

    def _parse_brand_ranges(self) -> List[Dict[str, str]]:
        raw = self.brand_ranges_text.get("1.0", "end").strip()
        if not raw:
            return []
        ranges: List[Dict[str, str]] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if "=" not in line:
                raise ValueError("多素材文案格式错误，请使用 01-03=文案 的格式。")
            range_part, text = line.split("=", 1)
            range_part = range_part.strip()
            text = text.strip()
            if not range_part or not text:
                raise ValueError("多素材文案格式错误，请填写完整的范围和文案。")
            ranges.append({"range": range_part, "text": text})
        return ranges

    def _clear_logs(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _refresh_drama_list(self) -> None:
        root_dir = self.var_root.get().strip()
        self.drama_listbox.delete(0, "end")
        self._all_drama_names = []
        self._filtered_drama_names = []
        self._processing_root = None

        if not root_dir or not Path(root_dir).is_dir():
            self._selected_drama_set = set()
            self._selected_drama_names = []
            self._refresh_selected_listbox()
            return

        processing_root, preselect = self._resolve_list_root(root_dir)
        self._processing_root = processing_root

        drama_dirs = scan_drama_dirs(processing_root)
        names = [Path(p).name for p in drama_dirs]
        self._all_drama_names = names

        if self._selected_drama_names:
            retained = [name for name in self._selected_drama_names if name in names]
            self._selected_drama_set = set(retained)
            self._selected_drama_names = retained
        else:
            self._selected_drama_set = set()
            self._selected_drama_names = []

        if preselect and preselect in names and preselect not in self._selected_drama_set:
            self._selected_drama_set.add(preselect)
            self._selected_drama_names = [name for name in names if name in self._selected_drama_set]

        self._apply_drama_filter()
        self._refresh_selected_listbox()

    def _resolve_list_root(self, root_dir: str) -> Tuple[str, Optional[str]]:
        root_path = Path(root_dir)
        if self._dir_has_mp4(root_path):
            parent = root_path.parent
            if parent != root_path:
                self.var_root.set(str(parent))
                return str(parent), root_path.name
        return root_dir, None

    def _on_filter_paste(self, event: Optional[tk.Event] = None) -> None:
        """处理搜索框粘贴事件，支持批量选择多个剧目"""
        # 延迟执行以便获取粘贴后的内容
        self.after(50, self._process_pasted_content)
        # 返回 None 让默认粘贴行为继续
        return None
    
    def _process_pasted_content(self) -> None:
        """处理粘贴的内容，识别多行剧目并自动选中"""
        content = self.var_filter.get().strip()
        if not content:
            return
        
        # 检查是否包含换行符（多行内容）
        if '\n' in content or '\r' in content:
            # 分割成多行
            lines = content.replace('\r\n', '\n').replace('\r', '\n').split('\n')
            # 清理每行并去除空行
            drama_names = [line.strip() for line in lines if line.strip()]
            
            if drama_names:
                matched_count = self._batch_select_dramas(drama_names)
                # 清空搜索框
                self.var_filter.set("")
                # 显示提示信息
                if matched_count > 0:
                    self._append_log(f"✅ 批量选择：成功匹配并选中 {matched_count} 部剧目")
                    if matched_count < len(drama_names):
                        self._append_log(f"⚠️  有 {len(drama_names) - matched_count} 部剧目未找到匹配")
                else:
                    self._append_log(f"❌ 批量选择：未找到匹配的剧目")
    
    def _batch_select_dramas(self, drama_names: List[str]) -> int:
        """批量选中剧目，支持模糊匹配
        
        Args:
            drama_names: 要选中的剧目名称列表
            
        Returns:
            成功匹配的数量
        """
        matched_count = 0
        
        for target_name in drama_names:
            target_lower = target_name.lower().strip()
            if not target_lower:
                continue
            
            # 尝试精确匹配
            exact_match = None
            for available_name in self._all_drama_names:
                if available_name.lower() == target_lower:
                    exact_match = available_name
                    break
            
            if exact_match:
                # 精确匹配
                if exact_match not in self._selected_drama_set:
                    self._selected_drama_set.add(exact_match)
                    matched_count += 1
            else:
                # 尝试模糊匹配（包含关系）
                fuzzy_matches = [
                    name for name in self._all_drama_names 
                    if target_lower in name.lower()
                ]
                
                if fuzzy_matches:
                    # 如果只有一个模糊匹配，自动选择
                    if len(fuzzy_matches) == 1:
                        match_name = fuzzy_matches[0]
                        if match_name not in self._selected_drama_set:
                            self._selected_drama_set.add(match_name)
                            matched_count += 1
                    else:
                        # 多个模糊匹配，选择最短的（最精确的）
                        best_match = min(fuzzy_matches, key=len)
                        if best_match not in self._selected_drama_set:
                            self._selected_drama_set.add(best_match)
                            matched_count += 1
        
        # 更新选中列表
        if matched_count > 0:
            self._selected_drama_names = [
                name for name in self._all_drama_names if name in self._selected_drama_set
            ]
            self._refresh_selected_listbox()
            self._sync_drama_listbox_selection()
        
        return matched_count
    
    def _unbind_drama_events(self) -> None:
        """解除剧目列表的所有事件绑定"""
        self.drama_listbox.unbind("<ButtonRelease-1>")
        self.drama_listbox.unbind("<space>")
        self.drama_listbox.unbind("<Return>")
    
    def _bind_drama_events(self) -> None:
        """绑定剧目列表的事件"""
        self.drama_listbox.bind("<ButtonRelease-1>", self._on_drama_list_select)
        self.drama_listbox.bind("<space>", self._on_drama_list_select)
        self.drama_listbox.bind("<Return>", self._on_drama_list_select)
    
    def _apply_drama_filter(self) -> None:
        keyword = self.var_filter.get().strip().lower()
        if keyword:
            self._filtered_drama_names = [
                name for name in self._all_drama_names if keyword in name.lower()
            ]
        else:
            self._filtered_drama_names = list(self._all_drama_names)
        self._rebuild_drama_listbox()

    def _rebuild_drama_listbox(self) -> None:
        # 临时解除事件绑定，防止触发选择事件
        self._unbind_drama_events()
        try:
            self.drama_listbox.delete(0, "end")
            for name in self._filtered_drama_names:
                self.drama_listbox.insert("end", name)
            # 同步选择状态（不需要再次 unbind，因为已经在外层 unbind 了）
            self._sync_drama_listbox_selection_internal()
        finally:
            # 重新绑定事件
            self._bind_drama_events()

    def _sync_drama_listbox_selection(self) -> None:
        """同步左侧列表的选择状态（带事件保护）"""
        # 临时解除事件绑定，防止触发选择事件
        self._unbind_drama_events()
        try:
            self._sync_drama_listbox_selection_internal()
        finally:
            # 重新绑定事件
            self._bind_drama_events()
    
    def _sync_drama_listbox_selection_internal(self) -> None:
        """同步左侧列表的选择状态（内部方法，不处理事件绑定）"""
        self.drama_listbox.selection_clear(0, "end")
        for idx, name in enumerate(self._filtered_drama_names):
            if name in self._selected_drama_set:
                self.drama_listbox.selection_set(idx)

    def _on_drama_list_select(self, event: Optional[tk.Event] = None) -> None:
        # 如果是程序内部更新列表，忽略此事件
        if self._updating_list:
            return
        
        # 获取当前左侧列表的选中项
        current_selection = self.drama_listbox.curselection()
        
        # 只有当有实际的交互时才处理（通过检查事件类型）
        # 如果是焦点丢失导致的事件，忽略
        if event and hasattr(event, 'type'):
            # 某些事件类型可能不是用户真实点击
            pass
        
        selected_visible = {
            self._filtered_drama_names[idx]
            for idx in current_selection
            if 0 <= idx < len(self._filtered_drama_names)
        }
        visible_set = set(self._filtered_drama_names)
        
        # 更新选中集合：
        # 1. 移除当前可见范围内已取消选择的项
        # 2. 添加当前可见范围内新选中的项
        self._selected_drama_set = (self._selected_drama_set - visible_set) | selected_visible
        
        # 更新选中列表（按照全部剧目的顺序）
        self._selected_drama_names = [
            name for name in self._all_drama_names if name in self._selected_drama_set
        ]
        self._refresh_selected_listbox()

    def _refresh_selected_listbox(self) -> None:
        self.selected_listbox.delete(0, "end")
        for name in self._selected_drama_names:
            self.selected_listbox.insert("end", name)

    def _select_all_dramas(self) -> None:
        for name in self._filtered_drama_names:
            self._selected_drama_set.add(name)
        self._selected_drama_names = [
            name for name in self._all_drama_names if name in self._selected_drama_set
        ]
        self._refresh_selected_listbox()
        self._sync_drama_listbox_selection()

    def _clear_drama_selection(self) -> None:
        self._selected_drama_set.clear()
        self._selected_drama_names = []
        self._refresh_selected_listbox()
        self._sync_drama_listbox_selection()
    
    def _fetch_dramas_from_feishu(self) -> None:
        """从飞书表格拉取指定日期的待剪辑剧目"""
        # 检查飞书功能是否启用
        if not self.var_enable_feishu.get():
            messagebox.showwarning("未启用飞书", "请先勾选'启用飞书功能'")
            return
        
        # 检查飞书配置是否完整
        app_id = self.var_feishu_app_id.get().strip()
        app_secret = self.var_feishu_app_secret.get().strip()
        app_token = self.var_feishu_app_token.get().strip()
        table_id = self.var_feishu_table_id.get().strip()
        date_str = self.var_feishu_date.get().strip()
        
        if not all([app_id, app_secret, app_token, table_id]):
            messagebox.showerror("配置不完整", "请填写完整的飞书配置（App ID、App Secret、App Token、Table ID）")
            return
        
        if not date_str:
            messagebox.showwarning("未填写日期", "请填写剪辑日期（如: 12.12）")
            return
        
        try:
            # 导入飞书客户端
            from ..integrations.feishu_client import FeishuClient
            from ..models.feishu import FeishuConfig
            
            self._append_log(f"🔄 正在从飞书拉取 {date_str} 的待剪辑剧目...")
            
            # 创建飞书配置
            feishu_config = FeishuConfig(
                app_id=app_id,
                app_secret=app_secret,
                app_token=app_token,
                table_id=table_id,
            )
            
            # 创建飞书客户端
            client = FeishuClient(feishu_config)
            
            # 获取待剪辑剧目（带日期信息）
            dramas_dict = client.get_pending_dramas_with_dates(date_filter=date_str)
            
            if not dramas_dict:
                self._append_log(f"⚠️  未找到 {date_str} 的待剪辑剧目")
                messagebox.showinfo("无待剪辑剧目", f"飞书表格中未找到 {date_str} 的待剪辑剧目")
                return
            
            # 获取剧目名称列表
            fetched_dramas = list(dramas_dict.keys())
            
            # 检查哪些剧目在本地可用
            available_dramas = set(self._all_drama_names)
            matched_dramas = []
            missing_dramas = []
            
            for drama in fetched_dramas:
                if drama in available_dramas:
                    matched_dramas.append(drama)
                else:
                    missing_dramas.append(drama)
            
            # 添加到已选列表
            for drama in matched_dramas:
                if drama not in self._selected_drama_set:
                    self._selected_drama_set.add(drama)
            
            self._selected_drama_names = [
                name for name in self._all_drama_names if name in self._selected_drama_set
            ]
            self._refresh_selected_listbox()
            self._sync_drama_listbox_selection()
            
            # 显示结果
            result_msg = f"✅ 从飞书拉取完成！\n\n"
            result_msg += f"日期: {date_str}\n"
            result_msg += f"飞书待剪辑: {len(fetched_dramas)} 部\n"
            result_msg += f"本地匹配: {len(matched_dramas)} 部\n"
            
            if missing_dramas:
                result_msg += f"\n⚠️  本地未找到 {len(missing_dramas)} 部:\n"
                for drama in missing_dramas[:5]:  # 最多显示5个
                    result_msg += f"  - {drama}\n"
                if len(missing_dramas) > 5:
                    result_msg += f"  ... 还有 {len(missing_dramas) - 5} 部\n"
            
            self._append_log(f"✅ 成功从飞书拉取 {len(matched_dramas)} 部剧目")
            if missing_dramas:
                self._append_log(f"⚠️  有 {len(missing_dramas)} 部剧目在本地未找到")
            
            messagebox.showinfo("拉取完成", result_msg)
            
        except ImportError as e:
            messagebox.showerror("导入错误", f"无法导入飞书客户端模块: {e}")
            self._append_log(f"❌ 导入错误: {e}")
        except Exception as e:
            messagebox.showerror("拉取失败", f"从飞书拉取剧目失败:\n{str(e)}")
            self._append_log(f"❌ 从飞书拉取失败: {e}")

    def _remove_selected_dramas(self) -> None:
        indices = list(self.selected_listbox.curselection())
        if not indices:
            return
        names_to_remove = [
            self._selected_drama_names[idx]
            for idx in indices
            if 0 <= idx < len(self._selected_drama_names)
        ]
        if not names_to_remove:
            return
        for name in names_to_remove:
            self._selected_drama_set.discard(name)
        self._selected_drama_names = [
            name for name in self._all_drama_names if name in self._selected_drama_set
        ]
        self._refresh_selected_listbox()
        self._sync_drama_listbox_selection()

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_running_ui(self, running: bool) -> None:
        self.btn_start.configure(state="disabled" if running else "normal")
        self.btn_cancel.configure(state="normal" if running else "disabled")
        if running:
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
        else:
            self.progress_bar.stop()
            self.progress_bar.set(0)

    def _start_processing(self) -> None:
        if self._running:
            return

        root_dir = self.var_root.get().strip()
        if not root_dir:
            messagebox.showerror("缺少参数", "请先选择素材目录。")
            return

        if not Path(root_dir).is_dir():
            messagebox.showerror("目录无效", "素材目录不存在或不可访问。")
            return

        if self._processing_root is None or self._processing_root != root_dir:
            self._refresh_drama_list()

        selected = self._get_selected_dramas()
        if not selected:
            messagebox.showerror("未选择剧目", "请从列表中选择要处理的剧目。")
            return

        if shutil.which("ffmpeg") is None:
            messagebox.showerror("缺少 FFmpeg", "未检测到 FFmpeg，请先安装并加入 PATH。")
            return

        config_path = self.var_config.get().strip() or None
        if config_path and not Path(config_path).is_file():
            messagebox.showerror("配置无效", "配置文件不存在或不可访问。")
            return

        try:
            overrides = self._collect_overrides()
        except ValueError as exc:
            messagebox.showerror("参数错误", str(exc))
            return

        self._running = True
        self._cancel_event.clear()
        self.var_status.set("处理中...")
        self.var_progress.set("0/0")
        self._completed_dramas = 0
        self._total_dramas = 0
        self._set_running_ui(True)

        worker = threading.Thread(
            target=self._run_processing,
            args=(self._processing_root or root_dir, config_path, overrides, selected),
            daemon=True,
        )
        worker.start()

    def _cancel_processing(self) -> None:
        if not self._running:
            return
        if not messagebox.askyesno("确认取消", "确定要取消当前处理吗？"):
            return
        self._cancel_event.set()
        self.var_status.set("正在取消...")
        self._append_log("🛑 已请求取消，将在当前任务结束后停止。")

    def _get_selected_dramas(self) -> List[str]:
        return list(self._selected_drama_names)

    def _collect_overrides(self) -> Dict[str, object]:
        count = _parse_int(self.var_count.get().strip(), "素材条数")
        min_dur = _parse_float(self.var_min_duration.get().strip(), "最小时长")
        max_dur = _parse_float(self.var_max_duration.get().strip(), "最大时长")
        jobs = _parse_int(self.var_jobs.get().strip(), "并发数")
        material_code = self.var_material_code.get().strip()
        title_colors = self._parse_title_colors(self.var_title_colors.get())
        brand_default = self.var_brand_default.get().strip()
        brand_ranges = self._parse_brand_ranges()
        enable_feishu = bool(self.var_enable_feishu.get())
        title_font_size = _parse_int(self.var_title_font_size.get().strip(), "标题字号")
        side_font_size = _parse_int(self.var_side_font_size.get().strip(), "侧边字号")
        bottom_font_size = _parse_int(self.var_bottom_font_size.get().strip(), "底部字号")

        if count <= 0:
            raise ValueError("素材条数必须大于 0")
        if jobs <= 0:
            raise ValueError("并发数必须大于 0")
        if min_dur <= 0 or max_dur <= 0:
            raise ValueError("时长必须大于 0")
        if min_dur > max_dur:
            raise ValueError("最小时长不能大于最大时长")
        if title_font_size <= 0 or side_font_size <= 0 or bottom_font_size <= 0:
            raise ValueError("字体大小必须大于 0")

        overrides: Dict[str, object] = {
            "count": count,
            "min_duration": min_dur,
            "max_duration": max_dur,
            "jobs": jobs,
            "use_hardware": bool(self.var_use_hw.get()),
            "fast_mode": bool(self.var_fast_mode.get()),
            "keep_temp": bool(self.var_keep_temp.get()),
            "verbose": bool(self.var_verbose.get()),
            "enable_feishu_features": enable_feishu,
            "enable_feishu_notification": enable_feishu,
            "title_font_size": title_font_size,
            "side_font_size": side_font_size,
            "bottom_font_size": bottom_font_size,
        }
        if not enable_feishu:
            overrides["feishu_watcher"] = {"enabled": False}
        else:
            # 如果启用飞书功能，添加飞书配置
            feishu_config = {}
            app_id = self.var_feishu_app_id.get().strip()
            app_secret = self.var_feishu_app_secret.get().strip()
            app_token = self.var_feishu_app_token.get().strip()
            table_id = self.var_feishu_table_id.get().strip()
            
            if app_id:
                feishu_config["app_id"] = app_id
            if app_secret:
                feishu_config["app_secret"] = app_secret
            if app_token:
                feishu_config["app_token"] = app_token
            if table_id:
                feishu_config["table_id"] = table_id
            
            if feishu_config:
                overrides["feishu"] = feishu_config
            
            # 添加日期配置（用于组织导出目录）
            date_str = self.var_feishu_date.get().strip()
            if date_str:
                overrides["date_str"] = date_str

        output_dir = self.var_output.get().strip()
        if output_dir:
            overrides["output_dir"] = output_dir

        font_file = self.var_font_file.get().strip()
        if font_file:
            overrides["font_file"] = font_file
        if material_code:
            overrides["material_code"] = material_code
        if title_colors:
            overrides["title_colors"] = title_colors
        if brand_ranges:
            overrides["brand_text_mapping"] = {
                "mode": "range",
                "ranges": brand_ranges,
                "default_text": brand_default or self._base_brand_text,
            }
            overrides["brand_text"] = brand_default or self._base_brand_text
            overrides["enable_brand_text"] = True
        elif brand_default:
            overrides["brand_text_mapping"] = None
            overrides["brand_text"] = brand_default
            overrides["enable_brand_text"] = True

        return overrides

    def _run_processing(
        self,
        root_dir: str,
        config_path: Optional[str],
        overrides: Dict[str, object],
        selected_dramas: List[str],
    ) -> None:
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        try:
            config = self._load_config(config_path)
            self._apply_overrides(config, overrides)
            processing_root, single_drama_name, base_root = self._resolve_processing_root(
                root_dir
            )
            if not selected_dramas and single_drama_name:
                selected_dramas = [single_drama_name]
            self._adjust_config_for_gui(config, base_root, selected_dramas)

            self._configure_logging(config.verbose)
            sys.stdout = StreamRedirector(self._log_queue, "stdout")
            sys.stderr = StreamRedirector(self._log_queue, "stderr")

            if single_drama_name and selected_dramas:
                self._log_queue.put(
                    ("log", f"检测到单剧目录，已默认勾选：{single_drama_name}")
                )

            total = self._calculate_total_dramas(processing_root, config)
            self._log_queue.put(("total", str(total)))
            if total == 0:
                self._log_queue.put(("status", "未发现可处理剧目"))
                self._log_queue.put(("done", "未发现可处理剧目，已结束。"))
                return

            processor = DramaProcessor(config, cancel_event=self._cancel_event)
            made, _ = processor.process_all_dramas(processing_root)
            self._log_queue.put(("status", "处理完成"))
            self._log_queue.put(("done", f"处理完成，共生成 {made} 条素材。"))
        except CancelledError:
            self._log_queue.put(("cancelled", "已取消处理"))
        except Exception as exc:
            self._log_queue.put(("error", str(exc)))
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            self._log_queue.put(("finish", ""))

    def _load_config(self, config_path: Optional[str]) -> ProcessingConfig:
        if config_path:
            return self._load_config_without_user(config_path)
        default_config = resolve_asset_path("configs/default.yaml")
        return self._load_config_without_user(default_config)

    def _load_config_without_user(self, config_path: Optional[str]) -> ProcessingConfig:
        if not config_path:
            return get_default_config()
        path = Path(config_path)
        if not path.exists():
            return get_default_config()
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
            data["active_user"] = None
            if "enable_feishu_features" not in data:
                data["enable_feishu_features"] = False
            if "enable_feishu_notification" not in data:
                data["enable_feishu_notification"] = False
            return ProcessingConfig(**data)
        except Exception:
            return get_default_config()

    def _apply_overrides(self, config: ProcessingConfig, overrides: Dict[str, object]) -> None:
        for key, value in overrides.items():
            if key == "brand_text_mapping" and isinstance(value, dict):
                value = BrandTextMapping(**value)
            elif key == "feishu_watcher" and isinstance(value, dict):
                value = FeishuWatcherConfig(**value)
            setattr(config, key, value)

    def _adjust_config_for_gui(
        self,
        config: ProcessingConfig,
        base_root: str,
        selected_dramas: List[str],
    ) -> None:
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
        elif not config.temp_dir:
            config.temp_dir = tempfile.gettempdir()
        if not config.tail_cache_dir or config.tail_cache_dir.startswith("/tmp"):
            config.tail_cache_dir = os.path.join(tempfile.gettempdir(), "tails_cache")

        if config.tail_file:
            resolved = resolve_asset_path(config.tail_file)
            if resolved:
                config.tail_file = resolved

        if config.watermark_path:
            resolved = resolve_asset_path(config.watermark_path)
            if resolved:
                config.watermark_path = resolved

        if config.font_file:
            resolved = resolve_asset_path(config.font_file)
            if resolved:
                config.font_file = resolved
        if _is_windows() and (not config.font_file or not os.path.isfile(config.font_file)):
            font_path = _find_windows_font()
            if font_path:
                config.font_file = font_path

    def _configure_logging(self, verbose: bool) -> None:
        level = "DEBUG" if verbose else "INFO"
        setup_logging(level=level, use_rich=False)
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        gui_handler = GuiLogHandler(self._log_queue)
        gui_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%H:%M:%S")
        )
        root_logger.addHandler(gui_handler)
        root_logger.setLevel(getattr(logging, level, logging.INFO))

    def _calculate_total_dramas(self, root_dir: str, config: ProcessingConfig) -> int:
        all_dirs = scan_drama_dirs(root_dir)
        if not all_dirs:
            return 0
        return len(self._filter_dramas(all_dirs, config))

    def _resolve_processing_root(
        self, root_dir: str
    ) -> Tuple[str, Optional[str], str]:
        """识别单剧目录并调整扫描根目录。"""
        root_path = Path(root_dir)
        if self._dir_has_mp4(root_path):
            parent = root_path.parent
            if parent != root_path:
                return str(parent), root_path.name, root_dir
        return root_dir, None, root_dir

    def _dir_has_mp4(self, path: Path) -> bool:
        try:
            for entry in os.scandir(path):
                if entry.is_file() and entry.name.lower().endswith(".mp4"):
                    return True
        except Exception:
            return False
        return False

    def _filter_dramas(self, all_dirs: List[str], config: ProcessingConfig) -> List[str]:
        exclude_set = set(config.exclude or [])
        if config.include:
            include_set = set(config.include)
            return [
                d
                for d in all_dirs
                if os.path.basename(d.rstrip("/")) in include_set
                and os.path.basename(d.rstrip("/")) not in exclude_set
            ]
        if config.full:
            return [
                d
                for d in all_dirs
                if os.path.basename(d.rstrip("/")) not in exclude_set
            ]
        if config.no_interactive:
            return []
        return []

    def _poll_log_queue(self) -> None:
        try:
            while True:
                kind, payload = self._log_queue.get_nowait()
                if kind in {"log", "stdout", "stderr"}:
                    if payload:
                        self._append_log(payload)
                        if "本剧完成" in payload:
                            self._completed_dramas += 1
                            self._update_progress()
                elif kind == "total":
                    try:
                        self._total_dramas = int(payload)
                    except ValueError:
                        self._total_dramas = 0
                    self._update_progress(reset=True)
                elif kind == "status":
                    self.var_status.set(payload)
                elif kind == "done":
                    self._append_log(payload)
                elif kind == "error":
                    self._append_log(f"❌ {payload}")
                    self.var_status.set("处理失败")
                elif kind == "cancelled":
                    self._append_log(payload)
                    self.var_status.set("已取消")
                elif kind == "finish":
                    self._running = False
                    self._set_running_ui(False)
                    if self.var_status.get() in {"处理完成", "处理失败", "未发现可处理剧目", "已取消"}:
                        messagebox.showinfo("处理结束", self.var_status.get())
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)

    def _update_progress(self, reset: bool = False) -> None:
        if reset:
            self._completed_dramas = 0
        if self._total_dramas > 0:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            progress_value = self._completed_dramas / self._total_dramas
            self.progress_bar.set(progress_value)
            self.var_progress.set(f"{self._completed_dramas}/{self._total_dramas}")
        else:
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
            self.var_progress.set("0/0")

    def _on_close(self) -> None:
        if self._running:
            if not messagebox.askyesno("确认退出", "任务仍在运行，确定要退出吗？"):
                return
        self.destroy()


def main() -> None:
    app = DramaProcessorGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
