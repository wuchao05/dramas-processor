"""Default configuration values."""

import os
from pathlib import Path
from typing import Optional

from ..models.config import ProcessingConfig
from ..utils.system import find_font


def get_default_font() -> Optional[str]:
    """Get default font path."""
    # Try to find Kaiti font first
    font_path = find_font("Kaiti")
    if font_path:
        return font_path
    
    # Fallback to system fonts
    fallback_paths = [
        "/Users/wuchao/Library/Application Support/com.electron.lark.font_workaround/PingFang.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    
    for path in fallback_paths:
        if Path(path).exists():
            return path
    
    return None


def get_default_config() -> ProcessingConfig:
    """Get default processing configuration."""
    config = ProcessingConfig()
    
    # Set default font
    default_font = get_default_font()
    if default_font:
        config.font_file = default_font
    
    # Set filter threads based on CPU count (75% of cores, min 4, max 8)
    cpu_count = os.cpu_count() or 4
    config.filter_threads = max(4, min(8, cpu_count * 3 // 4))
    
    return config

