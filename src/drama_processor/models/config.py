"""Configuration models."""

import os
from datetime import datetime
from typing import List, Optional, Union, Tuple
from pydantic import BaseModel, Field, validator
from .feishu import FeishuConfig


class VideoConfig(BaseModel):
    """Video encoding configuration."""
    
    hw_codec: str = Field(default="h264_videotoolbox", description="Hardware video codec")
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


class AudioConfig(BaseModel):
    """Audio encoding configuration."""
    
    codec: str = Field(default="aac", description="Audio codec")
    bitrate: str = Field(default="128k", description="Audio bitrate")
    sample_rate: int = Field(default=48000, description="Audio sample rate")



class ProcessingConfig(BaseModel):
    """Main processing configuration."""
    
    # Basic settings
    target_fps: int = Field(default=60, description="Target FPS")
    smart_fps: bool = Field(default=True, description="Enable smart FPS adaptation")
    fast_mode: bool = Field(default=False, description="Enable fast mode")
    filter_threads: int = Field(default=max(2, (os.cpu_count() or 4)//2), description="Filter processing threads")
    verbose: bool = Field(default=False, description="Enable verbose logging with detailed FFmpeg commands")
    
    # Duration settings
    min_duration: float = Field(default=480.0, description="Minimum duration in seconds")
    max_duration: float = Field(default=900.0, description="Maximum duration in seconds")
    
    # Material generation settings
    count: int = Field(default=1, description="Number of materials per drama")
    date_str: Optional[str] = Field(default=None, description="Date string for filenames")
    
    # Text overlay settings
    title_font_size: int = Field(default=36, description="Title font size")
    bottom_font_size: int = Field(default=28, description="Bottom text font size")
    side_font_size: int = Field(default=28, description="Side text font size")
    footer_text: str = Field(default="热门短剧 休闲必看", description="Footer text")
    side_text: str = Field(default="剧情纯属虚构 请勿模仿", description="Side text")
    title_colors: List[str] = Field(
        default=[
            "#FFA500", "#FFB347", "#FF8C00", 
            "#FFD580", "#E69500", "#FFAE42"
        ],
        description="Title color options"
    )
    
    # Processing settings
    random_start: bool = Field(default=True, description="Use random start points")
    seed: Optional[int] = Field(default=None, description="Random seed")
    use_hardware: bool = Field(default=True, description="Prefer hardware encoding")
    keep_temp: bool = Field(default=False, description="Keep temporary files")
    jobs: int = Field(default=1, description="Concurrent jobs per drama")
    
    # Canvas/Resolution settings
    canvas: Optional[str] = Field(default=None, description="Canvas size (WxH or 'first')")
    reference_resolution: Optional[Tuple[int, int]] = Field(default=None, description="Reference resolution")
    
    # Directory settings
    default_source_dir: str = Field(default="/Volumes/爆爆盘/短剧剪辑/源素材视频", description="Default source drama directory")
    backup_source_dir: str = Field(default="/Volumes/机械盘/短剧剪辑/源素材视频", description="Backup source drama directory")
    temp_dir: Optional[str] = Field(default=None, description="Temporary directory")
    output_dir: str = Field(default="../导出素材", description="Output directory")
    tail_cache_dir: str = Field(default="/tmp/tails_cache", description="Tail cache directory")
    tail_file: Optional[str] = Field(default="assets/tail.mp4", description="Default tail video file")
    refresh_tail_cache: bool = Field(default=False, description="Refresh tail cache")
    
    # Font settings
    font_file: Optional[str] = Field(default=None, description="Font file path")
    
    # Selection settings
    include: Optional[List[str]] = Field(default=None, description="Include specific dramas")
    exclude: Optional[List[str]] = Field(default=None, description="Exclude specific dramas")
    full: bool = Field(default=False, description="Process all dramas")
    no_interactive: bool = Field(default=False, description="Disable interactive selection")
    
    # Cover settings - REMOVED
    
    # Encoding configs
    video: VideoConfig = Field(default_factory=VideoConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    
    # 飞书API配置
    feishu: Optional[FeishuConfig] = Field(default=None, description="飞书API配置")
    
    # 飞书通知配置
    feishu_webhook_url: Optional[str] = Field(
        default="https://open.feishu.cn/open-apis/bot/v2/hook/6d2e64c2-a5b4-4f2e-b518-a8e314c4c355",
        description="飞书群通知webhook地址"
    )
    enable_feishu_notification: bool = Field(default=True, description="启用飞书群通知")
    
    def get_date_str(self) -> str:
        """Get date string for filename generation."""
        if self.date_str:
            return self.date_str
        now = datetime.now()
        return f"{now.month}.{now.day}"
    
    def get_default_font(self) -> str:
        """Get default font file path."""
        if self.font_file:
            return self.font_file
        
        # Try to find system font
        from ..utils.files import find_font
        font_path = find_font("Kaiti")
        if font_path:
            return font_path
        
        # Fallback
        fallback = "/Users/wuchao/Library/Application Support/com.electron.lark.font_workaround/PingFang.ttc"
        return fallback if os.path.exists(fallback) else ""
    
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

