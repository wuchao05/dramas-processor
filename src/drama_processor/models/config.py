"""Configuration models."""

import ntpath
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Union, Tuple
from pydantic import BaseModel, Field, validator
from .feishu import FeishuConfig


class BrandTextRange(BaseModel):
    """Brand text range configuration."""

    range: str = Field(
        description="Material number range (e.g., '01-03', '01,02,03', '01')"
    )
    text: str = Field(description="Brand text for this range")


class BrandTextMapping(BaseModel):
    """Advanced brand text mapping configuration."""

    mode: str = Field(default="range", description="Mapping mode: 'range' or 'cycle'")
    ranges: Optional[List[BrandTextRange]] = Field(
        default=None, description="Range mappings for 'range' mode"
    )
    cycle_texts: Optional[List[str]] = Field(
        default=None, description="Texts for 'cycle' mode"
    )
    default_text: str = Field(
        default="小红看剧", description="Default text when no range matches"
    )

    def parse_range(self, range_str: str) -> List[int]:
        """Parse range string to list of material numbers."""
        numbers = []

        # Handle comma-separated numbers: "01,02,03"
        if "," in range_str:
            parts = [part.strip() for part in range_str.split(",")]
            for part in parts:
                try:
                    numbers.append(int(part))
                except ValueError:
                    continue

        # Handle range: "01-03"
        elif "-" in range_str:
            try:
                start, end = range_str.split("-", 1)
                start_num = int(start.strip())
                end_num = int(end.strip())
                numbers.extend(range(start_num, end_num + 1))
            except ValueError:
                pass

        # Handle single number: "01"
        else:
            try:
                numbers.append(int(range_str.strip()))
            except ValueError:
                pass

        return numbers

    def get_text_for_material(self, material_idx: int) -> str:
        """Get brand text for specific material index."""
        if self.mode == "range" and self.ranges:
            # Range mapping mode
            for range_config in self.ranges:
                valid_numbers = self.parse_range(range_config.range)
                if material_idx in valid_numbers:
                    return range_config.text
            # No range matched, use default
            return self.default_text

        elif self.mode == "cycle" and self.cycle_texts:
            # Cycle mode
            text_index = (material_idx - 1) % len(self.cycle_texts)
            return self.cycle_texts[text_index]

        # Fallback to default
        return self.default_text


class DisplayTextOverride(BaseModel):
    """Override text configuration for brand/douyin display position."""

    text: Optional[str] = Field(
        default=None,
        description="Override text content; when set, replaces default brand/douyin text",
    )
    font_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="Override text font size; falls back to brand settings when empty",
    )
    color: Optional[str] = Field(
        default=None,
        description="Override text color; falls back to default color when empty",
    )
    start_minute: float = Field(
        default=0.0,
        ge=0.0,
        description="Start showing from the Nth minute of the material; 0 means always show",
    )


class VideoConfig(BaseModel):
    """Video encoding configuration."""

    hw_codec: str = Field(
        default="auto", description="Hardware video codec (auto-detect if 'auto')"
    )
    sw_codec: str = Field(default="libx264", description="Software video codec")
    bitrate: str = Field(default="1104k", description="Video bitrate")
    max_rate: str = Field(default="1104k", description="Maximum bitrate")
    buffer_size: str = Field(default="2208k", description="Buffer size")
    soft_crf: str = Field(default="24", description="Software encoding CRF")
    preset: str = Field(default="veryfast", description="Encoding preset")
    profile: str = Field(default="high", description="H.264 profile")
    level: str = Field(default="3.1", description="H.264 level")
    hw_level: str = Field(default="3.1", description="Hardware encoding level")
    sw_level: str = Field(default="3.1", description="Software encoding level")
    tag: str = Field(default="avc1", description="Video tag")
    pixel_format: str = Field(default="yuv420p", description="Pixel format")
    faststart: bool = Field(
        default=False,
        description="Enable faststart for web streaming (slower output, not needed for platform uploads)",
    )


class AudioConfig(BaseModel):
    """Audio encoding configuration."""

    codec: str = Field(default="aac", description="Audio codec")
    bitrate: str = Field(default="128k", description="Audio bitrate")
    sample_rate: int = Field(default=48000, description="Audio sample rate")


class FeishuWatcherConfig(BaseModel):
    """Feishu watcher configuration."""

    enabled: bool = Field(default=False, description="是否启用飞书轮询任务")
    poll_interval: int = Field(default=1800, description="轮询飞书的间隔（秒）")
    max_dates_per_cycle: int = Field(
        default=1, description="单次轮询最多同时触发的日期任务数"
    )
    settle_seconds: int = Field(
        default=120, description="同一日期任务在无新剧时继续等待的秒数"
    )
    settle_rounds: int = Field(
        default=2, description="连续空轮次数，超过后认为该日期暂时无新任务"
    )
    idle_exit_minutes: Optional[int] = Field(
        default=None, description="长时间无任务时自动退出（分钟），None 表示一直运行"
    )
    state_dir: str = Field(
        default="history/feishu_watcher", description="轮询状态存储目录"
    )
    date_whitelist: Optional[List[str]] = Field(
        default=None, description="仅监听的日期列表"
    )
    date_blacklist: Optional[List[str]] = Field(
        default=None, description="需要忽略的日期列表"
    )
    status_filter: Optional[str] = Field(
        default=None, description="覆盖默认的状态过滤值"
    )


class ProcessingConfig(BaseModel):
    """Main processing configuration."""

    # Basic settings
    target_fps: int = Field(default=60, description="Target FPS")
    smart_fps: bool = Field(default=True, description="Enable smart FPS adaptation")
    fast_mode: bool = Field(default=False, description="Enable fast mode")
    filter_threads: int = Field(
        default=max(4, min(8, (os.cpu_count() or 4) * 3 // 4)),
        description="Filter processing threads",
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose logging with detailed FFmpeg commands",
    )

    # Duration settings
    min_duration: float = Field(
        default=480.0, description="Minimum duration in seconds"
    )
    max_duration: float = Field(
        default=900.0, description="Maximum duration in seconds"
    )

    # Material generation settings
    count: int = Field(default=1, description="Number of materials per drama")
    material_code: str = Field(
        default="xh", description="Identifier used in exported filenames"
    )
    date_str: Optional[str] = Field(
        default=None, description="Date string for filenames"
    )

    # Start point selection settings
    exclude_last_episodes: int = Field(
        default=10,
        description="Exclude the last N episodes when selecting start points",
    )

    # Text overlay settings
    title_font_size: int = Field(default=36, description="Title font size (top)")
    brand_font_size: int = Field(default=28, description="Brand text font size (bottom first line)")
    disclaimer_font_size: int = Field(default=28, description="Disclaimer text font size (bottom second line)")
    disclaimer_text: str = Field(
        default="剧情纯属虚构 请勿模仿", description="Disclaimer text (bottom second line)"
    )
    enable_brand_text: bool = Field(
        default=True, description="Enable brand text overlay (bottom first line)"
    )
    enable_disclaimer_text: bool = Field(
        default=True, description="Enable disclaimer text overlay (bottom second line)"
    )
    title_opacity: float = Field(
        default=0.9, ge=0.0, le=1.0, description="Title text opacity (0.0-1.0)"
    )
    bottom_opacity: float = Field(
        default=0.85, ge=0.0, le=1.0, description="Bottom text opacity (0.0-1.0)"
    )
    title_position: str = Field(
        default="top", description="Title position: 'top' or 'bottom'"
    )
    title_colors: List[str] = Field(
        default=["#FFA500", "#FFB347", "#FF8C00", "#FFD580", "#E69500", "#FFAE42"],
        description="Title color options",
    )

    # Hook text settings (opening text that appears for first 2 seconds)
    enable_hook_text: bool = Field(
        default=False, description="Enable hook text overlay at the beginning"
    )
    hook_texts: List[str] = Field(
        default=["完结撒花", "全集已更新", "追剧必看", "热播推荐"],
        description="Hook text options (randomly selected)",
    )
    hook_font_size: int = Field(
        default=110, description="Hook text font size (100-140px recommended)"
    )
    hook_duration: float = Field(
        default=2.0, description="Hook text display duration in seconds"
    )
    hook_text_color: str = Field(
        default="#FFE600",
        description="Hook text color (auto-spaced for better readability)",
    )

    # Processing settings
    random_start: bool = Field(default=True, description="Use random start points")
    seed: Optional[int] = Field(default=None, description="Random seed")
    use_hardware: bool = Field(default=True, description="Prefer hardware encoding")
    keep_temp: bool = Field(default=False, description="Keep temporary files")
    jobs: int = Field(default=1, description="Concurrent jobs per drama")

    # Canvas/Resolution settings
    canvas: Optional[str] = Field(
        default=None, description="Canvas size (WxH or 'first')"
    )
    reference_resolution: Optional[Tuple[int, int]] = Field(
        default=None, description="Reference resolution"
    )

    # Directory settings
    default_source_dir: str = Field(
        default="/mnt/e/短剧剪辑/源素材视频",
        description="Default source drama directory",
    )
    backup_source_dir: str = Field(
        default="/mnt/e/短剧剪辑/源素材视频",
        description="Backup source drama directory",
    )
    temp_dir: Optional[str] = Field(
        default=None, 
        description="Temporary directory (None = use system temp for best performance)"
    )
    output_dir: str = Field(default="../导出素材", description="Output directory")
    tail_cache_dir: Optional[str] = Field(
        default=None, 
        description="Tail cache directory (None = use system temp for best performance)"
    )
    tail_file: Optional[str] = Field(
        default="assets/tail.mp4", description="Default tail video file"
    )
    refresh_tail_cache: bool = Field(default=False, description="Refresh tail cache")

    # Font settings
    font_file: Optional[str] = Field(default=None, description="Font file path")

    # Brand text settings
    enable_brand_text: bool = Field(
        default=True, description="Enable brand text overlay"
    )
    brand_text: str = Field(
        default="小红看剧",
        description="Brand text content (default text, backward compatible)",
    )
    brand_text_mapping: Optional["BrandTextMapping"] = Field(
        default=None, description="Advanced brand text mapping configuration"
    )
    display_text_override: Optional["DisplayTextOverride"] = Field(
        default=None,
        description="Override text for the brand/douyin display position",
    )

    # Floating watermark settings (dynamic brand text watermark)
    enable_floating_watermark: bool = Field(
        default=False, description="Enable floating watermark (uses brand text, replaces static brand text)"
    )
    floating_watermark_font_size: int = Field(
        default=32, ge=20, le=60, description="Floating watermark font size"
    )
    floating_watermark_alpha: float = Field(
        default=0.6, ge=0.3, le=1.0, description="Floating watermark opacity (0.3-1.0)"
    )
    floating_watermark_speed_range: List[int] = Field(
        default=[80, 150], description="Speed range in pixels per second [min, max]"
    )

    # Selection settings
    include: Optional[List[str]] = Field(
        default=None, description="Include specific dramas"
    )
    exclude: Optional[List[str]] = Field(
        default=None, description="Exclude specific dramas"
    )
    full: bool = Field(default=False, description="Process all dramas")
    no_interactive: bool = Field(
        default=False, description="Disable interactive selection"
    )

    # Deduplication settings
    enable_deduplication: bool = Field(
        default=False, description="Enable cut point deduplication"
    )
    
    # Source cleanup settings
    auto_delete_source_after_completion: bool = Field(
        default=False, 
        description="自动删除已完成剪辑的源视频目录（仅当所有素材都成功生成时）"
    )

    # Cover settings - REMOVED

    # Encoding configs
    video: VideoConfig = Field(default_factory=VideoConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)

    # 飞书功能开关
    enable_feishu_features: bool = Field(
        default=True, description="启用所有飞书相关功能"
    )

    # 飞书API配置
    feishu: Optional[FeishuConfig] = Field(default=None, description="飞书API配置")
    feishu_watcher: FeishuWatcherConfig = Field(
        default_factory=FeishuWatcherConfig, description="飞书轮询配置"
    )

    # 飞书通知配置
    feishu_webhook_url: Optional[str] = Field(
        default="https://open.feishu.cn/open-apis/bot/v2/hook/6d2e64c2-a5b4-4f2e-b518-a8e314c4c355",
        description="飞书群通知webhook地址",
    )
    enable_feishu_notification: bool = Field(default=True, description="启用飞书群通知")
    highlight_start_points_by_drama: Optional[Dict[str, str]] = Field(
        default=None, description="剧名到高光起始点文本的映射"
    )

    def is_feishu_features_enabled(self) -> bool:
        """Check if Feishu features are enabled."""
        return bool(self.enable_feishu_features)

    def is_feishu_api_enabled(self) -> bool:
        """Check if Feishu API integration can be used."""
        if not self.enable_feishu_features or not self.feishu:
            return False
        # 必须四要素齐全才认为 API 可用（避免空字符串导致后续请求报错）
        return bool(
            (self.feishu.app_id or "").strip()
            and (self.feishu.app_secret or "").strip()
            and (self.feishu.app_token or "").strip()
            and (self.feishu.table_id or "").strip()
        )

    def is_feishu_notification_enabled(self) -> bool:
        """Check if Feishu notifications can be sent."""
        return bool(
            self.enable_feishu_features
            and self.enable_feishu_notification
            and self.feishu_webhook_url
        )

    def is_feishu_watcher_enabled(self) -> bool:
        """Check if Feishu watcher can run."""
        return bool(
            self.is_feishu_api_enabled()
            and self.feishu_watcher
            and self.feishu_watcher.enabled
        )

    def get_date_str(self) -> str:
        """Get date string for filename generation."""
        if self.date_str:
            return self.date_str
        now = datetime.now()
        return f"{now.month}.{now.day}"

    def get_material_code(self) -> str:
        """Get sanitized material code for filenames."""
        code = (self.material_code or "xh").strip()
        if not code:
            return "xh"
        return code

    def get_default_font(self) -> str:
        """获取字体文件路径，支持跨平台自动检测"""
        # 1. 如果配置了字体且存在，直接使用
        if self.font_file and os.path.exists(self.font_file):
            return self.font_file
        
        # 2. 根据平台自动检测
        import platform
        system = platform.system()
        
        if system == "Windows":
            # Windows 常见中文字体（优先使用 TTF 单字体文件，避免 TTC 兼容性问题）
            fonts = [
                "C:\\Windows\\Fonts\\msyh.ttf",      # 微软雅黑（优先 TTF）
                "C:\\Windows\\Fonts\\msyhbd.ttf",    # 微软雅黑粗体
                "C:\\Windows\\Fonts\\simhei.ttf",    # 黑体
                "C:\\Windows\\Fonts\\simkai.ttf",    # 楷体
                "C:\\Windows\\Fonts\\msyh.ttc",      # 微软雅黑 TTC（备选）
                "C:\\Windows\\Fonts\\simsun.ttc",    # 宋体 TTC（备选）
            ]
            for font in fonts:
                if os.path.exists(font):
                    return font
            return "C:\\Windows\\Fonts\\arial.ttf"  # 兜底
        
        elif system == "Linux":
            # Linux 常见中文字体
            fonts = [
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/truetype/arphic/uming.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            ]
            for font in fonts:
                if os.path.exists(font):
                    return font
            return "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        
        else:  # macOS
            return "/System/Library/Fonts/PingFang.ttc"

    def get_actual_source_dir(self) -> str:
        """Get the actual source directory to use, with fallback to backup."""
        if os.path.exists(self.default_source_dir):
            return self.default_source_dir
        elif os.path.exists(self.backup_source_dir):
            return self.backup_source_dir
        else:
            # Return default even if it doesn't exist, let the caller handle the error
            return self.default_source_dir

    def _select_path_module(self, path_value: str):
        """根据路径字符串选择合适的路径模块。"""
        normalized = (path_value or "").strip()
        if re.match(r"^[A-Za-z]:[\\/]", normalized) or "\\" in normalized:
            return ntpath
        return os.path

    def _normalize_dir_path(self, path_value: str) -> str:
        """规范化目录路径，同时保留根目录语义。"""
        normalized = (path_value or "").strip()
        if not normalized:
            return ""

        if re.fullmatch(r"[A-Za-z]:[\\/]*", normalized):
            return f"{normalized[0]}:\\"

        if normalized in ("/", "\\"):
            return normalized

        return normalized.rstrip("\\/")

    def is_absolute_path(self, path_value: str) -> bool:
        """判断路径是否为绝对路径，兼容 Windows 风格路径。"""
        normalized = self._normalize_dir_path(path_value)
        if not normalized:
            return False

        path_module = self._select_path_module(normalized)
        return path_module.isabs(normalized)

    def get_export_base_dir(self, source_dir: Optional[str] = None) -> str:
        """Get the base directory for exports based on actual source directory."""
        actual_source = self._normalize_dir_path(source_dir or self.get_actual_source_dir())
        if not actual_source:
            return ""

        path_module = self._select_path_module(actual_source)
        parent_dir = path_module.dirname(actual_source)
        if parent_dir in ("", "."):
            return actual_source
        return parent_dir

    def resolve_output_dir(
        self,
        output_dir: Optional[str] = None,
        source_dir: Optional[str] = None,
    ) -> str:
        """根据源目录解析最终导出目录。"""
        candidate = self._normalize_dir_path(output_dir or self.output_dir or "")
        if not candidate:
            return ""

        actual_source_dir = self._normalize_dir_path(source_dir or self.get_actual_source_dir())
        export_base = self.get_export_base_dir(actual_source_dir)
        path_module = self._select_path_module(actual_source_dir or candidate)

        if actual_source_dir:
            candidate_norm = path_module.normcase(path_module.normpath(candidate))
            source_norm = path_module.normcase(path_module.normpath(actual_source_dir))
            if candidate_norm == source_norm:
                return export_base

        if export_base and not path_module.isabs(candidate):
            target_name = path_module.basename(candidate) or "导出素材"
            return path_module.join(export_base, target_name)

        return candidate

    def get_default_export_dir(self, source_dir: Optional[str] = None) -> str:
        """返回默认导出目录。"""
        export_base = self.get_export_base_dir(source_dir)
        if not export_base:
            return "导出素材"

        path_module = self._select_path_module(export_base)
        return path_module.join(export_base, "导出素材")
    
    def get_optimized_temp_dir(self) -> Optional[str]:
        """Get optimized temp directory for best performance.
        
        Strategy: Always use system temp (C:\\ on Windows) unless manually overridden.
        
        Why system temp is fastest:
        1. C:\\ is usually NVMe SSD (3500MB/s vs 550MB/s SATA SSD)
        2. I/O isolation: Read from data disk, write temp to system disk
        3. Better system-level cache and optimization
        
        Returns:
            - If temp_dir is explicitly set: Use that (manual override)
            - Otherwise: None (use system default temp for optimal performance)
        """
        return self.temp_dir  # None = use system temp (fastest)
    
    def get_optimized_tail_cache_dir(self) -> Optional[str]:
        """Get optimized tail cache directory for best performance.
        
        Strategy: Always use system temp (C:\\ on Windows) unless manually overridden.
        
        Why system temp is fastest:
        1. C:\\ is usually NVMe SSD (3500MB/s vs 550MB/s SATA SSD)
        2. I/O isolation: Read from data disk, write cache to system disk
        3. Better system-level cache and optimization
        
        Returns:
            - If tail_cache_dir is explicitly set: Use that (manual override)
            - Otherwise: None (use system default temp for optimal performance)
        """
        return self.tail_cache_dir  # None = use system temp (fastest)

    def get_brand_text_for_material(self, material_idx: int) -> str:
        """Get brand text for specific material index."""
        # Use advanced mapping if available
        if self.brand_text_mapping:
            return self.brand_text_mapping.get_text_for_material(material_idx)

        # Fallback to single brand_text (backward compatibility)
        return self.brand_text

    @validator("min_duration", "max_duration")
    def validate_duration(cls, v: float) -> float:
        """Validate duration is positive."""
        if v <= 0:
            raise ValueError("Duration must be positive")
        return v

    @validator("max_duration")
    def validate_max_duration(cls, v: float, values: dict) -> float:
        """Validate max duration is greater than min."""
        min_dur = values.get("min_duration", 0)
        if v <= min_dur:
            raise ValueError("Max duration must be greater than min duration")
        return v
