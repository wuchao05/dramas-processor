"""Text overlay processing module."""

import os
import random
from pathlib import Path
from typing import List, Optional

from ..utils.files import write_text_file


class TextOverlay:
    """Handles text overlay generation for videos."""
    
    def __init__(self, watermark_path: Optional[str] = None, title_colors: Optional[List[str]] = None):
        self.title_colors = title_colors or [
            "#FFA500", "#FFB347", "#FF8C00", "#FFD580", "#E69500", "#FFAE42",
        ]
        self.watermark_path = watermark_path
    
    def to_vertical(self, text: str) -> str:
        """Convert horizontal text to vertical layout."""
        if "\n" in text:
            return text
        return "\n".join(list(text))
    
    def create_text_files(self, workdir: str, drama_name: str, footer_text: str, side_text: str) -> tuple:
        """Create text files for overlay filters."""
        title_txt = os.path.join(workdir, "title.txt")
        bottom_txt = os.path.join(workdir, "bottom.txt")
        side_txtf = os.path.join(workdir, "side.txt")

        write_text_file(title_txt, f"《{drama_name}》")
        write_text_file(bottom_txt, footer_text)
        write_text_file(side_txtf, self.to_vertical(side_text))
        
        return title_txt, bottom_txt, side_txtf
    
    def build_text_overlays(self, fontfile: str, ref_w: int, ref_h: int, 
                           title_txt: str, bottom_txt: str, side_txtf: str,
                           title_font_size: int = 36, bottom_font_size: int = 28, 
                           side_font_size: int = 28) -> List[str]:
        """Build text overlay filter strings."""
        margin = max(12, int(ref_h * 0.037))
        title_color = random.choice(self.title_colors)
        
        overlays = []
        
        # Title overlay (top center)
        dt_top = (
            f"drawtext=fontfile='{fontfile}':textfile='{title_txt}':fontsize={title_font_size}:"
            f"fontcolor={title_color}@0.9:shadowx=1:shadowy=1:box=0:"
            f"x=(w-text_w)/2:y={margin + 20}"
        )
        overlays.append(dt_top)
        
        # Bottom overlay (bottom center)
        dt_bottom = (
            f"drawtext=fontfile='{fontfile}':textfile='{bottom_txt}':fontsize={bottom_font_size}:"
            f"fontcolor=white@0.85:box=0:"
            f"x=(w-text_w)/2:y=h-text_h-{margin + 120}"
        )
        overlays.append(dt_bottom)
        
        # Side overlay (top right, vertical)
        dt_side = (
            f"drawtext=fontfile='{fontfile}':textfile='{side_txtf}':fontsize={side_font_size}:"
            f"fontcolor=white@0.85:box=0:"
            f"x=w-text_w-{margin}:y={margin + 200}"
        )
        overlays.append(dt_side)
        
        return overlays
    
    def build_watermark_overlay(self, ref_w: int, ref_h: int) -> Optional[str]:
        """Build watermark overlay filter string for use in filter chain."""
        if not self.watermark_path or not os.path.exists(self.watermark_path):
            return None
            
        # Calculate watermark size (8% of video width, maintain aspect ratio)
        watermark_width = int(ref_w * 0.08)
        margin = 15  # 15px margin from edges
        
        # Create overlay filter that scales and positions watermark in top-left corner
        # This will be added to the main filter chain
        watermark_filter = (
            f"overlay='{self.watermark_path}':x={margin}:y={margin}:"
            f"eval=init:format=auto:shortest=1"
        )
        
        return watermark_filter
    
    def build_overlay_filter_chain(self, fontfile: str, ref_w: int, ref_h: int, fps: int,
                                  drama_name: str, footer_text: str, side_text: str,
                                  workdir: str, fast_mode: bool = False) -> str:
        """Build complete filter chain with text overlays."""
        # Base video processing
        base_filters = [f"scale={ref_w}:{ref_h}:force_original_aspect_ratio=decrease"]
        
        # Random cropping for variation
        crop_pad = random.randint(0, 3)
        if crop_pad > 0:
            base_filters.append(f"crop=iw-2*{crop_pad}:ih-2*{crop_pad}:{crop_pad}:{crop_pad}")
        
        base_filters.append(f"pad={ref_w}:{ref_h}:(ow-iw)/2:(oh-ih)/2")
        base_filters.append(f"fps={fps}")
        
        # Color adjustments (skip in fast mode)
        if not fast_mode:
            brightness = round(random.uniform(-0.02, 0.02), 3)
            contrast = round(random.uniform(0.98, 1.02), 3)
            saturation = round(random.uniform(0.98, 1.02), 3)
            hue = round(random.uniform(-5, 5), 2)
            base_filters.append(f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}")
            base_filters.append(f"hue=h={hue}")
        
        # Create text files
        title_txt, bottom_txt, side_txtf = self.create_text_files(workdir, drama_name, footer_text, side_text)
        
        # Build text overlays
        text_overlays = self.build_text_overlays(fontfile, ref_w, ref_h, title_txt, bottom_txt, side_txtf)
        
        # Combine all filters
        all_filters = base_filters + text_overlays
        return ",".join(all_filters)
    
    def get_watermark_command_args(self, ref_w: int, ref_h: int) -> List[str]:
        """Get additional FFmpeg command arguments for watermark overlay using filter_complex."""
        if not self.watermark_path or not os.path.exists(self.watermark_path):
            return []
            
        # Calculate watermark size and position
        watermark_width = int(ref_w * 0.08)  # 8% of video width
        margin = 15  # 15px margin from edges
        
        # Return filter_complex arguments for watermark
        filter_complex = (
            f"[0:v]scale={watermark_width}:-1[scaled_wm];"
            f"[1:v][scaled_wm]overlay={margin}:{margin}:format=auto[out]"
        )
        
        return ["-i", self.watermark_path, "-filter_complex", filter_complex, "-map", "[out]", "-map", "0:a"]
