"""Configuration models."""

import os
import re
from datetime import datetime
from typing import List, Optional, Union, Tuple
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


class VideoConfig(BaseModel):
    """Video encoding configuration."""

    hw_codec: str = Field(
        default="auto", description="Hardware video codec (auto-detect if 'auto')"
    )
    sw_codec: str = Field(default="libx264", description="Software video codec")
    bitrate: str = Field(default="9000k", description="Video bitrate")
    max_rate: str = Field(default="9000k", description="Maximum bitrate")
    buffer_size: str = Field(default="14000k", description="Buffer size")
    soft_crf: str = Field(default="22", description="Software encoding CRF")
    preset: str = Field(default="veryfast", description="Encoding preset")
    profile: str = Field(default="high", description="H.264 profile")
    level: str = Field(default="4.2", description="H.264 level")
    hw_level: str = Field(default="4.2", description="Hardware encoding level")
    sw_level: str = Field(default="4.1", description="Software encoding level")
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

    # 当前激活的用户配置
    active_user: Optional[str] = Field(
        default=None, description="当前激活的用户配置名称（如 xh, xl, xx）"
    )

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
        default="xl", description="Identifier used in exported filenames"
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

    # Hook text settings (opening text that appears for first 3 seconds)
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
        default=3.0, description="Hook text display duration in seconds"
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
    storage_type: Optional[str] = Field(
        default=None,
        description="Storage type: 'ssd' or 'hdd'. If set, optimizes temp directories accordingly."
    )
    temp_dir: Optional[str] = Field(default=None, description="Temporary directory")
    output_dir: str = Field(default="../导出素材", description="Output directory")
    tail_cache_dir: Optional[str] = Field(
        default=None, description="Tail cache directory"
    )
    tail_file: Optional[str] = Field(
        default="assets/tail.mp4", description="Default tail video file"
    )
    refresh_tail_cache: bool = Field(default=False, description="Refresh tail cache")

    # Font settings
    font_file: Optional[str] = Field(default=None, description="Font file path")

    # Watermark settings
    watermark_path: Optional[str] = Field(
        default="assets/watermark-xiaohong.png", description="Watermark image path"
    )
    enable_watermark: bool = Field(
        default=False, description="Enable watermark overlay"
    )
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
        code = (self.material_code or "xl").strip()
        if not code:
            return "xl"
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

    def get_export_base_dir(self) -> str:
        """Get the base directory for exports based on actual source directory."""
        actual_source = self.get_actual_source_dir()
        # Go up one level from the source directory to get the base directory
        return os.path.dirname(actual_source)
    
    def get_optimized_temp_dir(self) -> Optional[str]:
        """Get optimized temp directory based on storage type.
        
        Returns:
            - If storage_type is 'ssd': Use source dir's disk for temp (all operations on SSD)
            - If storage_type is 'hdd': Use system temp (leverage system SSD for processing)
            - If temp_dir is explicitly set: Use that (manual override)
            - Otherwise: Use system default (None)
        """
        if self.temp_dir is not None:
            # Explicit configuration takes precedence
            return self.temp_dir
        
        if self.storage_type:
            storage_type_lower = self.storage_type.lower()
            if storage_type_lower == "ssd":
                # Use same disk as source for all operations (fast disk)
                base_dir = self.get_export_base_dir()
                return os.path.join(base_dir, "临时文件")
            elif storage_type_lower == "hdd":
                # Use system temp (usually on system SSD) for fast processing
                return None  # None means use system default
        
        return None  # Default: use system temp
    
    def get_optimized_tail_cache_dir(self) -> Optional[str]:
        """Get optimized tail cache directory based on storage type.
        
        Returns:
            - If storage_type is 'ssd': Use source dir's disk for cache (all operations on SSD)
            - If storage_type is 'hdd': Use system temp (leverage system SSD for processing)
            - If tail_cache_dir is explicitly set: Use that (manual override)
            - Otherwise: Use system default (None)
        """
        if self.tail_cache_dir is not None:
            # Explicit configuration takes precedence
            return self.tail_cache_dir
        
        if self.storage_type:
            storage_type_lower = self.storage_type.lower()
            if storage_type_lower == "ssd":
                # Use same disk as source for cache (fast disk)
                base_dir = self.get_export_base_dir()
                return os.path.join(base_dir, "尾部缓存")
            elif storage_type_lower == "hdd":
                # Use system temp (usually on system SSD) for fast processing
                return None  # None means use system default
        
        return None  # Default: use system temp

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
