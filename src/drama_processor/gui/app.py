"""短剧批量剪辑 GUI（Tkinter）。"""

import logging
import os
import queue
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from ..config.loader import load_config_with_fallback
from ..core.processor import DramaProcessor
from ..models.config import ProcessingConfig
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


class DramaProcessorGUI(tk.Tk):
    """Tkinter GUI 主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.title("短剧批量剪辑工具")
        self.geometry("980x720")
        self.minsize(860, 640)

        self._log_queue: "queue.Queue[LogItem]" = queue.Queue()
        self._running = False
        self._total_dramas = 0
        self._completed_dramas = 0
        self._drama_names: List[str] = []
        self._processing_root: Optional[str] = None
        self._cancel_event = threading.Event()

        self._ui_bg = "#f5f5f5"
        self._ui_fg = "#222222"
        self._entry_bg = "#ffffff"
        self._log_bg = "#ffffff"
        self._log_fg = "#222222"

        self._init_vars()
        self._apply_theme()
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

        self.var_count = tk.StringVar()
        self.var_min_duration = tk.StringVar()
        self.var_max_duration = tk.StringVar()
        self.var_jobs = tk.StringVar()

        self.var_use_hw = tk.BooleanVar(value=True)
        self.var_fast_mode = tk.BooleanVar(value=True)
        self.var_keep_temp = tk.BooleanVar(value=False)
        self.var_verbose = tk.BooleanVar(value=False)

        self.var_status = tk.StringVar(value="就绪")
        self.var_progress = tk.StringVar(value="0/0")

    def _apply_theme(self) -> None:
        style = ttk.Style(self)
        themes = style.theme_names()

        if _is_windows() and "vista" in themes:
            theme = "vista"
        else:
            theme = "clam" if "clam" in themes else style.theme_use()

        try:
            style.theme_use(theme)
        except tk.TclError:
            pass

        if sys.platform == "darwin":
            # mac 深色模式下 ttk 容易黑底黑字，强制亮色外观
            try:
                self.tk.call(
                    "tk",
                    "unsupported::MacWindowStyle",
                    "appearance",
                    self._w,
                    "light",
                )
            except tk.TclError:
                pass
            self._ui_bg = "#f7f7f7"
            self._ui_fg = "#1f1f1f"
            self._entry_bg = "#ffffff"
            self._log_bg = "#ffffff"
            self._log_fg = "#1f1f1f"
        else:
            bg = style.lookup("TFrame", "background") or "#f5f5f5"
            fg = style.lookup("TLabel", "foreground") or "#222222"
            self._ui_bg = bg
            self._ui_fg = fg
            self._entry_bg = "#ffffff"
            self._log_bg = "#ffffff"
            self._log_fg = fg
        style.configure(".", background=self._ui_bg, foreground=self._ui_fg)
        style.configure("TFrame", background=self._ui_bg)
        style.configure("TLabelframe", background=self._ui_bg)
        style.configure("TLabelframe.Label", background=self._ui_bg, foreground=self._ui_fg)
        style.configure("TLabel", background=self._ui_bg, foreground=self._ui_fg)
        style.configure("TCheckbutton", background=self._ui_bg, foreground=self._ui_fg)
        style.configure("TEntry", fieldbackground=self._entry_bg, foreground=self._ui_fg)
        style.configure("TButton", background=self._ui_bg, foreground=self._ui_fg)
        style.configure("TProgressbar", troughcolor="#dcdcdc")
        self.configure(background=self._ui_bg)

    def _build_ui(self) -> None:
        main = ttk.Frame(self, padding=12)
        main.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        form = ttk.LabelFrame(main, text="基础设置", padding=10)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="素材目录").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.var_root).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(form, text="选择", command=self._choose_root).grid(row=0, column=2)

        ttk.Label(form, text="配置文件").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.var_config).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(form, text="选择", command=self._choose_config).grid(row=1, column=2)

        ttk.Label(form, text="输出目录").grid(row=2, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.var_output).grid(row=2, column=1, sticky="ew", padx=6)
        ttk.Button(form, text="选择", command=self._choose_output).grid(row=2, column=2)

        ttk.Label(form, text="字体文件").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.var_font_file).grid(row=3, column=1, sticky="ew", padx=6)
        ttk.Button(form, text="选择", command=self._choose_font).grid(row=3, column=2)

        drama_frame = ttk.LabelFrame(main, text="剧目选择", padding=10)
        drama_frame.grid(row=1, column=0, sticky="nsew")
        drama_frame.columnconfigure(0, weight=1)
        drama_frame.rowconfigure(1, weight=1)

        ttk.Label(drama_frame, text="从素材目录中选择要处理的剧目（支持多选）").grid(
            row=0, column=0, sticky="w"
        )

        list_frame = ttk.Frame(drama_frame)
        list_frame.grid(row=1, column=0, sticky="nsew", pady=6)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.drama_listbox = tk.Listbox(
            list_frame,
            selectmode="extended",
            height=6,
            activestyle="none",
            background=self._log_bg,
            foreground=self._log_fg,
            selectbackground="#c7ddff",
            selectforeground="#1f1f1f",
        )
        self.drama_listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.drama_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.drama_listbox.configure(yscrollcommand=scrollbar.set)

        list_actions = ttk.Frame(drama_frame)
        list_actions.grid(row=2, column=0, sticky="w")
        ttk.Button(list_actions, text="刷新列表", command=self._refresh_drama_list).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(list_actions, text="全选", command=self._select_all_dramas).grid(
            row=0, column=1, sticky="w", padx=6
        )
        ttk.Button(list_actions, text="清空选择", command=self._clear_drama_selection).grid(
            row=0, column=2, sticky="w"
        )

        opts = ttk.LabelFrame(main, text="处理参数", padding=10)
        opts.grid(row=2, column=0, sticky="ew", pady=10)
        opts.columnconfigure(1, weight=1)

        ttk.Label(opts, text="素材条数").grid(row=0, column=0, sticky="w")
        ttk.Entry(opts, textvariable=self.var_count, width=10).grid(row=0, column=1, sticky="w")

        ttk.Label(opts, text="最小时长(秒)").grid(row=0, column=2, sticky="w", padx=(16, 0))
        ttk.Entry(opts, textvariable=self.var_min_duration, width=10).grid(row=0, column=3, sticky="w")

        ttk.Label(opts, text="最大时长(秒)").grid(row=0, column=4, sticky="w", padx=(16, 0))
        ttk.Entry(opts, textvariable=self.var_max_duration, width=10).grid(row=0, column=5, sticky="w")

        ttk.Label(opts, text="并发数").grid(row=0, column=6, sticky="w", padx=(16, 0))
        ttk.Entry(opts, textvariable=self.var_jobs, width=8).grid(row=0, column=7, sticky="w")

        ttk.Checkbutton(opts, text="硬件编码", variable=self.var_use_hw).grid(row=1, column=0, sticky="w", pady=6)
        ttk.Checkbutton(opts, text="快速模式", variable=self.var_fast_mode).grid(
            row=1, column=1, sticky="w", pady=6
        )
        ttk.Checkbutton(opts, text="保留临时文件", variable=self.var_keep_temp).grid(
            row=1, column=2, sticky="w", pady=6
        )
        ttk.Checkbutton(opts, text="详细日志", variable=self.var_verbose).grid(row=1, column=3, sticky="w", pady=6)

        actions = ttk.Frame(main)
        actions.grid(row=3, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)

        self.btn_start = ttk.Button(actions, text="开始处理", command=self._start_processing)
        self.btn_start.grid(row=0, column=0, sticky="w")
        self.btn_cancel = ttk.Button(actions, text="取消处理", command=self._cancel_processing)
        self.btn_cancel.grid(row=0, column=1, sticky="w", padx=8)
        ttk.Button(actions, text="清空日志", command=self._clear_logs).grid(row=0, column=2, sticky="w", padx=8)

        progress = ttk.Frame(main)
        progress.grid(row=4, column=0, sticky="ew", pady=8)
        progress.columnconfigure(1, weight=1)

        ttk.Label(progress, textvariable=self.var_status).grid(row=0, column=0, sticky="w")
        self.progress_bar = ttk.Progressbar(progress, mode="indeterminate")
        self.progress_bar.grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Label(progress, textvariable=self.var_progress).grid(row=0, column=2, sticky="e")

        log_frame = ttk.LabelFrame(main, text="日志", padding=8)
        log_frame.grid(row=5, column=0, sticky="nsew")
        main.rowconfigure(5, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = ScrolledText(
            log_frame,
            height=20,
            state="disabled",
            wrap="word",
            background=self._log_bg,
            foreground=self._log_fg,
            insertbackground=self._log_fg,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

    def _apply_default_values(self) -> None:
        config = self._load_config(None)
        self._apply_config_to_form(config)

    def _choose_root(self) -> None:
        path = filedialog.askdirectory()
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
        path = filedialog.askdirectory()
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
        if config.output_dir:
            self.var_output.set(str(config.output_dir))
        if config.font_file:
            self.var_font_file.set(str(config.font_file))

    def _clear_logs(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _refresh_drama_list(self) -> None:
        root_dir = self.var_root.get().strip()
        self.drama_listbox.delete(0, "end")
        self._drama_names = []
        self._processing_root = None

        if not root_dir or not Path(root_dir).is_dir():
            return

        processing_root, preselect = self._resolve_list_root(root_dir)
        self._processing_root = processing_root

        drama_dirs = scan_drama_dirs(processing_root)
        names = [Path(p).name for p in drama_dirs]
        self._drama_names = names

        for name in names:
            self.drama_listbox.insert("end", name)

        if preselect and preselect in names:
            idx = names.index(preselect)
            self.drama_listbox.selection_set(idx)
            self.drama_listbox.see(idx)

    def _resolve_list_root(self, root_dir: str) -> Tuple[str, Optional[str]]:
        root_path = Path(root_dir)
        if self._dir_has_mp4(root_path):
            parent = root_path.parent
            if parent != root_path:
                self.var_root.set(str(parent))
                return str(parent), root_path.name
        return root_dir, None

    def _select_all_dramas(self) -> None:
        self.drama_listbox.selection_set(0, "end")

    def _clear_drama_selection(self) -> None:
        self.drama_listbox.selection_clear(0, "end")

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_running_ui(self, running: bool) -> None:
        self.btn_start.configure(state="disabled" if running else "normal")
        self.btn_cancel.configure(state="normal" if running else "disabled")
        if running:
            self.progress_bar.configure(mode="indeterminate", maximum=100)
            self.progress_bar.start(10)
        else:
            self.progress_bar.stop()
            self.progress_bar.configure(value=0)

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
        indices = list(self.drama_listbox.curselection())
        if not indices:
            return []
        names = []
        for idx in indices:
            if 0 <= idx < len(self._drama_names):
                names.append(self._drama_names[idx])
        return names

    def _collect_overrides(self) -> Dict[str, object]:
        count = _parse_int(self.var_count.get().strip(), "素材条数")
        min_dur = _parse_float(self.var_min_duration.get().strip(), "最小时长")
        max_dur = _parse_float(self.var_max_duration.get().strip(), "最大时长")
        jobs = _parse_int(self.var_jobs.get().strip(), "并发数")

        if count <= 0:
            raise ValueError("素材条数必须大于 0")
        if jobs <= 0:
            raise ValueError("并发数必须大于 0")
        if min_dur <= 0 or max_dur <= 0:
            raise ValueError("时长必须大于 0")
        if min_dur > max_dur:
            raise ValueError("最小时长不能大于最大时长")

        overrides: Dict[str, object] = {
            "count": count,
            "min_duration": min_dur,
            "max_duration": max_dur,
            "jobs": jobs,
            "use_hardware": bool(self.var_use_hw.get()),
            "fast_mode": bool(self.var_fast_mode.get()),
            "keep_temp": bool(self.var_keep_temp.get()),
            "verbose": bool(self.var_verbose.get()),
        }

        output_dir = self.var_output.get().strip()
        if output_dir:
            overrides["output_dir"] = output_dir

        font_file = self.var_font_file.get().strip()
        if font_file:
            overrides["font_file"] = font_file

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
            return load_config_with_fallback(config_path)
        default_config = resolve_asset_path("configs/default.yaml")
        return load_config_with_fallback(default_config)

    def _apply_overrides(self, config: ProcessingConfig, overrides: Dict[str, object]) -> None:
        for key, value in overrides.items():
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

        if not config.temp_dir:
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
        elif _is_windows():
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
            self.progress_bar.configure(
                mode="determinate", maximum=self._total_dramas, value=self._completed_dramas
            )
            self.var_progress.set(f"{self._completed_dramas}/{self._total_dramas}")
        else:
            self.progress_bar.configure(mode="indeterminate", maximum=100)
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
