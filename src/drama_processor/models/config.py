"""Configuration models."""

import os
import re
from datetime import datetime
from typing import List, Optional, Union, Tuple
from pydantic import BaseModel, Field, validator
from .feishu import FeishuConfig


class BrandTextRange(BaseModel):
    """Brand text range configuration."""
    
    range: str = Field(description="Material number range (e.g., '01-03', '01,02,03', '01')")
    text: str = Field(description="Brand text for this range")


class BrandTextMapping(BaseModel):
    """Advanced brand text mapping configuration."""
    
    mode: str = Field(default="range", description="Mapping mode: 'range' or 'cycle'")
    ranges: Optional[List[BrandTextRange]] = Field(default=None, description="Range mappings for 'range' mode")
    cycle_texts: Optional[List[str]] = Field(default=None, description="Texts for 'cycle' mode")
    default_text: str = Field(default="小红看剧", description="Default text when no range matches")
    
    def parse_range(self, range_str: str) -> List[int]:
        """Parse range string to list of material numbers."""
        numbers = []
        
        # Handle comma-separated numbers: "01,02,03"
        if ',' in range_str:
            parts = [part.strip() for part in range_str.split(',')]
            for part in parts:
                try:
                    numbers.append(int(part))
                except ValueError:
                    continue
        
        # Handle range: "01-03" 
        elif '-' in range_str:
            try:
                start, end = range_str.split('-', 1)
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
    
    hw_codec: str = Field(default="auto", description="Hardware video codec (auto-detect if 'auto')")
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
    filter_threads: int = Field(default=max(4, min(8, (os.cpu_count() or 4) * 3 // 4)), description="Filter processing threads")
    verbose: bool = Field(default=False, description="Enable verbose logging with detailed FFmpeg commands")
    
    # Duration settings
    min_duration: float = Field(default=480.0, description="Minimum duration in seconds")
    max_duration: float = Field(default=900.0, description="Maximum duration in seconds")
    
    # Material generation settings
    count: int = Field(default=1, description="Number of materials per drama")
    date_str: Optional[str] = Field(default=None, description="Date string for filenames")
    
    # Start point selection settings
    exclude_last_episodes: int = Field(default=10, description="Exclude the last N episodes when selecting start points")
    
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
    default_source_dir: str = Field(default="/mnt/e/短剧剪辑/源素材视频", description="Default source drama directory")
    backup_source_dir: str = Field(default="/mnt/e/短剧剪辑/源素材视频", description="Backup source drama directory")
    temp_dir: Optional[str] = Field(default=None, description="Temporary directory")
    output_dir: str = Field(default="../导出素材", description="Output directory")
    tail_cache_dir: str = Field(default="/tmp/tails_cache", description="Tail cache directory")
    tail_file: Optional[str] = Field(default="assets/tail.mp4", description="Default tail video file")
    refresh_tail_cache: bool = Field(default=False, description="Refresh tail cache")
    
    # Font settings
    font_file: Optional[str] = Field(default=None, description="Font file path")
    
    # Watermark settings
    watermark_path: Optional[str] = Field(default="assets/watermark-xiaohong.png", description="Watermark image path")
    enable_watermark: bool = Field(default=False, description="Enable watermark overlay")
    enable_brand_text: bool = Field(default=True, description="Enable brand text overlay")
    brand_text: str = Field(default="小红看剧", description="Brand text content (default text, backward compatible)")
    brand_text_mapping: Optional['BrandTextMapping'] = Field(default=None, description="Advanced brand text mapping configuration")
    
    # Selection settings
    include: Optional[List[str]] = Field(default=None, description="Include specific dramas")
    exclude: Optional[List[str]] = Field(default=None, description="Exclude specific dramas")
    full: bool = Field(default=False, description="Process all dramas")
    no_interactive: bool = Field(default=False, description="Disable interactive selection")
    
    # Deduplication settings
    enable_deduplication: bool = Field(default=False, description="Enable cut point deduplication")
    
    # Cover settings - REMOVED
    
    # Encoding configs
    video: VideoConfig = Field(default_factory=VideoConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    
    # 飞书功能开关
    enable_feishu_features: bool = Field(default=True, description="启用所有飞书相关功能")
    
    # 飞书API配置
    feishu: Optional[FeishuConfig] = Field(default=None, description="飞书API配置")
    
    # 飞书通知配置
    feishu_webhook_url: Optional[str] = Field(
        default="https://open.feishu.cn/open-apis/bot/v2/hook/6d2e64c2-a5b4-4f2e-b518-a8e314c4c355",
        description="飞书群通知webhook地址"
    )
    enable_feishu_notification: bool = Field(default=True, description="启用飞书群通知")
    
    def is_feishu_features_enabled(self) -> bool:
        """Check if Feishu features are enabled."""
        return bool(self.enable_feishu_features)
    
    def is_feishu_api_enabled(self) -> bool:
        """Check if Feishu API integration can be used."""
        return bool(self.enable_feishu_features and self.feishu)
    
    def is_feishu_notification_enabled(self) -> bool:
        """Check if Feishu notifications can be sent."""
        return bool(self.enable_feishu_features and self.enable_feishu_notification and self.feishu_webhook_url)
    
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
        from ..utils.system import find_font
        font_path = find_font("wqy")
        if font_path:
            return font_path
        
        # WSL Linux fallback fonts
        fallback_fonts = [
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
        ]
        
        for font in fallback_fonts:
            if os.path.exists(font):
                return font
        
        return ""
    
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
