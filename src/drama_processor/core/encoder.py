"""Video encoding and processing module."""

import os
import json
import time
import tempfile
import shutil
import subprocess
import shlex
import random
import math
from threading import Event
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from collections import Counter

from ..models.config import ProcessingConfig
from ..utils.video import probe_video_stream, probe_duration
from ..utils.files import write_text_file, ensure_dir, md5_of_text, md5_of_file
from ..utils.time import human_duration
from ..utils.cancel import raise_if_cancelled
from ..utils.system import get_windows_subprocess_kwargs_hide_console


class VideoEncoder:
    """Video encoder for drama processing."""
    
    def __init__(
        self,
        config: ProcessingConfig,
        watermark_path: Optional[str] = None,
    
    def to_vertical(self, text: str) -> str:
        """Convert text to vertical layout."""
        if "\n" in text:
            return text
        return "\n".join(list(text))
    
    def build_overlay_filters(self, ref_w: int, ref_h: int, fps: int, fontfile: str,
                            drama_name: str, footer_text: str, side_text: str,
                            workdir: str, fast_mode: bool, material_idx: Optional[int] = None) -> str:
        """Build video filter string with text overlays."""
        # Base video processing filters
        base_filters = [f"scale={ref_w}:{ref_h}:force_original_aspect_ratio=decrease"]
        crop_pad = random.randint(0, 3)  # Light cropping for variation
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

        base = ",".join(base_filters)

        # Text overlay setup
        title_fs, bottom_fs, side_fs = self.title_font_size, self.bottom_font_size, self.side_font_size
        margin = max(12, int(ref_h * 0.037))

        title_txt = os.path.join(workdir, "title.txt")
        bottom_txt = os.path.join(workdir, "bottom.txt")
        side_txtf = os.path.join(workdir, "side.txt")

        write_text_file(title_txt, f"《{drama_name}》")
        write_text_file(bottom_txt, footer_text)
        write_text_file(side_txtf, self.to_vertical(side_text))

        title_color = random.choice(self.title_colors)
        fontfile_filter = self._filter_path(fontfile)
        title_txt_filter = self._filter_path(title_txt)
        bottom_txt_filter = self._filter_path(bottom_txt)
        side_txt_filter = self._filter_path(side_txtf)

        # Text overlay filters
        # Title at bottom (replacing footer position)
        dt_top = (
            f"drawtext=fontfile='{fontfile_filter}':textfile='{title_txt_filter}':fontsize={title_fs}:"
            f"fontcolor={title_color}@{self.title_opacity}:shadowx=1:shadowy=1:box=0:"
            f"x=(w-text_w)/2:y=h-text_h-{margin + 120}"
        )
        
        # Base filters with title only (no bottom text)
        filters = [base, dt_top]
        
        # Hook text overlay (appears only in first 3 seconds)
        if self.config.enable_hook_text and self.config.hook_texts:
            hook_text = random.choice(self.config.hook_texts)
            hook_fs = self.config.hook_font_size
            hook_color = self.config.hook_text_color
            hook_border = self.config.hook_border_color
            hook_duration = self.config.hook_duration
            
            # Center position with shadow/border effect
            # Using borderw for outline effect
            dt_hook = (
                f"drawtext=fontfile='{fontfile_filter}':text='{hook_text}':"
                f"fontsize={hook_fs}:fontcolor={hook_color}:"
                f"borderw=3:bordercolor={hook_border}:"
                f"x=(w-text_w)/2:y=(h-text_h)/2:"
                f"enable='lt(t,{hook_duration})'"  # Only show for first N seconds
            )
            filters.append(dt_hook)
        
        # Right side text - use individual drawtext for each character for tighter spacing
        if self.config.enable_right_side_text:
            try:
                # Read side text content
                with open(side_txtf, 'r', encoding='utf-8') as f:
                    side_text_content = f.read().strip()
                
                # Remove newlines to get original characters
                side_chars = [c for c in side_text_content if c != '\n']
                
                # Character spacing: 1.3 = slightly loose
                char_spacing = int(side_fs * 1.3)
                
                # Create individual drawtext for each character
                start_y = margin + 200
                for i, char in enumerate(side_chars):
                    # Escape special characters for FFmpeg
                    escaped_char = char.replace("'", "\\'").replace(":", "\\:")
                    y_pos = start_y + i * char_spacing
                    
                    dt_char = (
                        f"drawtext=fontfile='{fontfile_filter}':text='{escaped_char}':fontsize={side_fs}:"
                        f"fontcolor=white@0.85:box=0:"
                        f"x=w-text_w-{margin}:y={y_pos}"
                    )
                    filters.append(dt_char)
            except Exception:
                # Fallback to old method if reading fails
                line_spacing_opt = ""
                if self.vertical_line_spacing:
                    line_spacing_opt = f":line_spacing={self.vertical_line_spacing}"
                dt_side = (
                    f"drawtext=fontfile='{fontfile_filter}':textfile='{side_txt_filter}':fontsize={side_fs}:"
                    f"fontcolor=white@0.85:box=0{line_spacing_opt}:"
                    f"x=w-text_w-{margin}:y={margin + 200}"
                )
                filters.append(dt_side)
        
        # Add brand text overlay (left side, same tight spacing)
        # Controlled by enable_left_side_text
        if self.use_brand_text and self.config.enable_left_side_text:
            # Get brand text for current material
            if material_idx is not None:
                brand_text = self.config.get_brand_text_for_material(material_idx)
            else:
                brand_text = self.config.brand_text
            
            brand_txt = os.path.join(workdir, "brand.txt")
            write_text_file(brand_txt, self.to_vertical(brand_text))
            
            try:
                # Read brand text content
                with open(brand_txt, 'r', encoding='utf-8') as f:
                    brand_text_content = f.read().strip()
                
                # Remove newlines to get original characters
                brand_chars = [c for c in brand_text_content if c != '\n']
                
                # Same character spacing as side text (1.3 = slightly loose)
                char_spacing = int(side_fs * 1.3)
                
                # Create individual drawtext for each character
                start_y = margin + 200
                for i, char in enumerate(brand_chars):
                    # Escape special characters for FFmpeg
                    escaped_char = char.replace("'", "\\'").replace(":", "\\:")
                    y_pos = start_y + i * char_spacing
                    
                    dt_char = (
                        f"drawtext=fontfile='{fontfile_filter}':text='{escaped_char}':fontsize={side_fs}:"
                        f"fontcolor=white@0.85:box=0:"
                        f"x={margin}:y={y_pos}"
                    )
                    filters.append(dt_char)
            except Exception:
                # Fallback to old method
                brand_txt_filter = self._filter_path(brand_txt)
                line_spacing_opt = ""
                if self.vertical_line_spacing:
                    line_spacing_opt = f":line_spacing={self.vertical_line_spacing}"
                dt_brand = (
                    f"drawtext=fontfile='{fontfile_filter}':textfile='{brand_txt_filter}':fontsize={side_fs}:"
                    f"fontcolor=white@0.85:box=0{line_spacing_opt}:"
                    f"x={margin}:y={margin + 200}"
                )
                filters.append(dt_brand)

        return ",".join(filters)
    
    def build_base_vf(self, ref_w: int, ref_h: int, fps: int) -> str:
        """Build basic video filter for tail normalization."""
        return (
            f"scale={ref_w}:{ref_h}:force_original_aspect_ratio=decrease,"
            f"pad={ref_w}:{ref_h}:(ow-iw)/2:(oh-ih)/2,fps={fps}"
        )
    
    def norm_and_trim(self, src: str, start_s: float, end_s: float, out_path: str,
                     ref_w: int, ref_h: int, fps: int, fontfile: str, drama_name: str,
                     footer_text: str, side_text: str, workdir: str, use_hw: bool,
                     seg_idx: int, seg_total: int, fast_mode: bool, filter_threads: int,
                     material_idx: Optional[int] = None):
        """Normalize and trim video segment with text overlay."""
        dur = max(0.01, end_s - start_s)
        
        def _is_oom_error(text: str) -> bool:
            t = (text or "").lower()
            return any(
                s in t
                for s in [
                    "malloc of size",
                    "cannot allocate memory",
                    "out of memory",
                    "error while opening encoder",
                ]
            )

        def build_cmd(vcodec: str, hw: bool, *, ft: Optional[int] = None, threads: Optional[int] = None):
            # Check if we should use watermark (only if brand text is disabled and watermark exists)
            use_watermark = (not self.use_brand_text and 
                           self.watermark_path and 
                           os.path.exists(self.watermark_path))
            ft_val = int(ft) if ft is not None else int(filter_threads)
            
            if use_watermark:
                # Use filter_complex for watermark + text overlays
                vf = self.build_overlay_filters(ref_w, ref_h, fps, fontfile, drama_name, 
                                              footer_text, side_text, workdir, fast_mode=fast_mode, 
                                              material_idx=material_idx)
                
                # Calculate watermark size and position
                watermark_width = int(ref_w * 0.08)  # 8% of video width
                text_margin = max(12, int(ref_h * 0.037))  # Same margin as text overlays
                
                # Position watermark to match text positioning:
                # - Left margin same as right text's right margin
                # - Top margin same as title's top margin
                watermark_x = text_margin  # Same as right text distance from right edge
                watermark_y = text_margin + 20  # Same as title distance from top
                
                # Build filter_complex that combines video processing with watermark overlay
                filter_complex = (
                    f"[0:v]{vf}[main];"
                    f"[1:v]scale={watermark_width}:-1[wm];"
                    f"[main][wm]overlay={watermark_x}:{watermark_y}:format=auto[out]"
                )
                
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(max(0, start_s)), "-t", str(dur),
                    "-i", src,
                    "-i", self.watermark_path,
                    "-filter_complex", filter_complex,
                    "-map", "[out]", "-map", "0:a",
                    "-analyzeduration", "20M", "-probesize", "20M",
                    "-sws_flags", "fast_bilinear",
                    "-filter_threads", str(ft_val),
                    "-filter_complex_threads", str(ft_val),
                    "-c:v", vcodec,
                    "-profile:v", self.config.video.profile,
                ]
            else:
                # Use text overlays (including brand text if enabled)
                vf = self.build_overlay_filters(ref_w, ref_h, fps, fontfile, drama_name, 
                                              footer_text, side_text, workdir, fast_mode=fast_mode, 
                                              material_idx=material_idx)
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(max(0, start_s)), "-t", str(dur),
                    "-i", src,
                    "-vf", vf,
                    "-analyzeduration", "20M", "-probesize", "20M",
                    "-sws_flags", "fast_bilinear",
                    "-filter_threads", str(ft_val),
                    "-filter_complex_threads", str(ft_val),
                    "-c:v", vcodec,
                    "-profile:v", self.config.video.profile,
                ]

            # 限制编码线程数（可显著降低内存峰值；仅在需要时开启）
            if threads is not None:
                cmd += ["-threads", str(int(threads))]
            
            if hw:
                # Hardware encoding parameters
                cmd += ["-level", self.config.video.hw_level, "-tag:v", self.config.video.tag, "-b:v", self.bitrate, 
                       "-maxrate", self.config.video.max_rate, "-bufsize", self.config.video.buffer_size]
                # Add hardware-specific preset if it's NVENC format (p1-p7)
                preset = self.config.video.preset
                if preset.startswith('p') and preset[1:].isdigit():
                    cmd += ["-preset", preset]
            else:
                # Software encoding parameters
                # Convert NVENC preset (p1-p7) to libx264 preset if needed
                preset = self.config.video.preset
                if preset.startswith('p') and preset[1:].isdigit():
                    # NVENC preset detected, use default software preset
                    preset = "veryfast"
                cmd += ["-level", self.config.video.sw_level, "-preset", preset, "-crf", self.soft_crf, 
                       "-pix_fmt", self.config.video.pixel_format]
            cmd += ["-c:a", "aac", "-b:a", self.audio_br, "-ar", str(self.audio_sr), 
                   "-movflags", "+faststart", out_path]
            return cmd

        def _run_with_oom_retry(cmd_builder, label_text: str):
            try:
                return self.run_ffmpeg(cmd_builder(), label=label_text)
            except Exception as e:
                out = getattr(e, "ffmpeg_output", "") or str(e)
                if _is_oom_error(out):
                    print("⚠️ 检测到内存不足/编码器初始化失败，自动降线程重试一次（filter_threads=1, threads=1）…")
                    return self.run_ffmpeg(cmd_builder(ft=1, threads=1), label=label_text + "(low-mem-retry)")
                raise
        
        if seg_total == 1:
            label = f"规范化片段"
        else:
            label = f"规范化片段#{seg_idx}/{seg_total}"
        t0 = time.time()
        try:
            if use_hw:
                # Try hardware encoding first
                result = _run_with_oom_retry(lambda **kw: build_cmd(self.video_codec_hw, True, **kw), label)
                # Check if hardware encoding actually failed
                if result.returncode != 0:
                    raise Exception("Hardware encoding failed")
            else:
                _run_with_oom_retry(lambda **kw: build_cmd(self.video_codec_sw, False, **kw), label)
        except Exception as e:
            if use_hw:
                print("⚠️ 硬编失败，回退到 x264 软编…")
                _run_with_oom_retry(lambda **kw: build_cmd(self.video_codec_sw, False, **kw), label + "(fallback-x264)")
            else:
                raise
        # Remove the extra completion print since run_ffmpeg already prints completion
    
    def norm_tail(self, src: str, out_path: str, ref_w: int, ref_h: int, fps: int, 
                 use_hw: bool, filter_threads: int):
        """Normalize tail video to match target specs."""
        vf = self.build_base_vf(ref_w, ref_h, fps)
        
        def build_cmd(vcodec: str, hw: bool):
            cmd = [
                "ffmpeg", "-y",
                "-i", src,
                "-vf", vf,
                "-analyzeduration", "20M", "-probesize", "20M",
                "-sws_flags", "fast_bilinear",
                "-filter_threads", str(filter_threads),
                "-filter_complex_threads", str(filter_threads),
                "-c:v", vcodec,
                "-profile:v", self.config.video.profile,
            ]
            if hw:
                cmd += ["-level", self.config.video.hw_level, "-tag:v", self.config.video.tag, "-b:v", self.bitrate,
                       "-maxrate", self.config.video.max_rate, "-bufsize", self.config.video.buffer_size]
            else:
                cmd += ["-level", self.config.video.sw_level, "-preset", self.config.video.preset, "-crf", self.soft_crf,
                       "-pix_fmt", self.config.video.pixel_format]
            cmd += ["-c:a", "aac", "-b:a", self.audio_br, "-ar", str(self.audio_sr),
                   "-movflags", "+faststart", out_path]
            return cmd
        
        self.run_ffmpeg(build_cmd(self.video_codec_hw, True) if use_hw else build_cmd(self.video_codec_sw, False), 
                       label="尾部规范化")
    
    def get_or_build_tail_norm(self, tail_src: str, ref_w: int, ref_h: int, fps: int,
                              use_hw: bool, cache_dir: str, refresh: bool, filter_threads: int) -> Optional[str]:
        """Get or build normalized tail video with caching."""
        if not tail_src or not os.path.isfile(tail_src):
            return None
        
        ensure_dir(cache_dir)
        try:
            file_sig = md5_of_file(tail_src)[:8]
        except Exception:
            file_sig = "nosig"
        
        key_str = f"{os.path.abspath(tail_src)}|{file_sig}|{ref_w}x{ref_h}@{fps}|{'hw' if use_hw else 'sw'}"
        fp = md5_of_text(key_str)[:16]
        cache_path = os.path.join(cache_dir, f"tail_{fp}.mp4")
        
        if os.path.isfile(cache_path) and not refresh:
            print(f"🧩 复用尾部缓存：{cache_path}")
            return cache_path
        
        tmp_out = cache_path + ".tmp.mp4"
        try:
            print("⚙️ 正在规范化尾部（构建/刷新缓存）…")
            t0 = time.time()
            self.norm_tail(tail_src, tmp_out, ref_w, ref_h, fps, use_hw=use_hw, filter_threads=filter_threads)
            os.replace(tmp_out, cache_path)
            print(f"✅ 尾部缓存就绪：{cache_path} | 用时 {human_duration(time.time()-t0)}")
            return cache_path
        except Exception as e:
            print("⚠️ 规范化尾部失败：", e)
            try:
                if os.path.exists(tmp_out): 
                    os.remove(tmp_out)
            except: 
                pass
            return None
    

    def concat_videos(self, list_file: str, out_path: str, filter_threads: int):
        """Concatenate videos using ffmpeg concat demuxer."""
        self.run_ffmpeg([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", list_file,
            "-c", "copy", "-movflags", "+faststart",
            out_path
        ], label=f"concat->{os.path.basename(out_path)}")
    
    def write_ffconcat_list(self, paths: List[str], list_path: str):
        """Write ffmpeg concat file list."""
        with open(list_path, "w", encoding="utf-8") as f:
            for p in paths:
                esc = p.replace("'", r"\'")
                f.write(f"file '{esc}'\n")
    
    def determine_reference_resolution(self, episodes: List[str], canvas: Optional[str]) -> Tuple[int, int]:
        """Determine reference resolution from episodes or canvas setting."""
        if canvas:
            if canvas.lower() == "first":
                info = probe_video_stream(episodes[0])
                return self.even(info["w"]), self.even(info["h"])
            elif "x" in canvas.lower():
                w, h = canvas.lower().split("x")
                return self.even(int(w)), self.even(int(h))
            else:
                raise ValueError("--canvas 需要 'first' 或 'WxH'")
        else:
            # Auto-detect most common resolution
            sizes = []
            for ep in episodes:
                info = probe_video_stream(ep)
                if info["w"] and info["h"]:
                    sizes.append((self.even(info["w"]), self.even(info["h"])))
            if not sizes:
                raise ValueError("未能探测到任何有效分辨率")
            return Counter(sizes).most_common(1)[0][0]
    
    def choose_output_fps(self, episodes: List[str], requested_fps: int, smart: bool) -> int:
        """Choose output FPS based on source material and settings."""
        if not smart:
            return requested_fps
        
        src_fps = 0.0
        for ep in episodes:
            try:
                info = probe_video_stream(ep)
                if info.get("fps"):
                    src_fps = info["fps"]
                    break
            except Exception:
                continue
        
        if src_fps > 0:
            if src_fps < 40:
                out = int(round(src_fps))
            else:
                out = 45
            # Only show FPS output during processing, not analysis
            import sys
            if not hasattr(sys, '_drama_analyzer_mode'):
                print(f"🎯 自适应 FPS：源约 {src_fps:.2f} -> 输出 {out}")
            return out
        return requested_fps
    
    def build_segments_at_episode_boundaries(self, episodes: List[str], start_ep_idx: int, 
                                           start_offset: float, min_sec: float, max_sec: float) -> List[Tuple[str, float, float]]:
        """Build segments aligned at episode boundaries with guaranteed minimum duration."""
        # First, calculate available content from this start point
        available_duration = self._calculate_available_duration(episodes, start_ep_idx, start_offset)
        
        # If available content is less than minimum, try to find a better start point
        if available_duration < min_sec:
            print(f"⚠️ 当前起始点可用时长 {available_duration:.1f}s < 最小要求 {min_sec:.1f}s，尝试调整...")
            adjusted_start = self._find_valid_start_point(episodes, min_sec, max_sec)
            if adjusted_start:
                start_ep_idx, start_offset = adjusted_start
                print(f"✅ 调整起始点: 第{start_ep_idx+1}集 {start_offset:.1f}s")
            else:
                print(f"⚠️ 无法找到满足最小时长的起始点，跳过此素材")
                return []
        
        # Build segment choices from the valid start point
        choices = []
        total = 0.0
        for i in range(start_ep_idx, len(episodes)):
            path = episodes[i]
            try:
                dur = probe_duration(path)
            except Exception:
                continue
            seg_start = start_offset if i == start_ep_idx else 0.0
            take = max(0.0, dur - seg_start)
            if take <= 0:
                continue
            total += take
            choices.append((i, seg_start, dur, total))
            if total >= max_sec:
                break
        
        if not choices:
            return []

        # Find optimal cutoff within valid range
        target_mid = (min_sec + max_sec) / 2.0
        
        # Only consider choices that meet minimum duration requirement
        valid_choices = [j for j, (_, _, _, cum) in enumerate(choices) if cum >= min_sec]
        
        if valid_choices:
            # Among valid choices, prefer those within max_sec range
            preferred_choices = [j for j in valid_choices if choices[j][3] <= max_sec]
            if preferred_choices:
                cut_upto = min(preferred_choices, key=lambda j: abs(choices[j][3] - target_mid))
            else:
                # If no choice within max_sec, take the shortest valid one
                cut_upto = min(valid_choices, key=lambda j: choices[j][3])
        else:
            # This should not happen given our pre-check, but as fallback
            print(f"⚠️ 警告：无法满足最小时长要求 {min_sec:.1f}s")
            return []

        # Build final segment list
        segs: List[Tuple[str, float, float]] = []
        for j, (i, s, e, _) in enumerate(choices[: cut_upto + 1]):
            segs.append((episodes[i], s, e))
        
        # Verify final duration meets requirement
        final_duration = 0.0
        for i, (ep_path, start, end) in enumerate(segs):
            seg_duration = end - start
            final_duration += seg_duration
        if final_duration < min_sec:
            print(f"⚠️ 最终时长 {final_duration:.1f}s < 最小要求 {min_sec:.1f}s，跳过此素材")
            return []
            
        return segs
    
    def _calculate_available_duration(self, episodes: List[str], start_ep_idx: int, start_offset: float) -> float:
        """Calculate total available duration from given start point."""
        total_duration = 0.0
        for i in range(start_ep_idx, len(episodes)):
            try:
                dur = probe_duration(episodes[i])
                if i == start_ep_idx:
                    available = max(0.0, dur - start_offset)
                else:
                    available = dur
                total_duration += available
            except Exception:
                continue
        return total_duration
    
    def _find_valid_start_point(self, episodes: List[str], min_sec: float, max_sec: float) -> Optional[Tuple[int, float]]:
        """Find a start point that can provide minimum required duration."""
        # Try each episode as starting point
        for ep_idx in range(len(episodes)):
            try:
                episode_duration = probe_duration(episodes[ep_idx])
                
                # Calculate maximum safe offset for this episode
                available_from_ep = self._calculate_available_duration(episodes, ep_idx, 0.0)
                
                if available_from_ep < min_sec:
                    continue  # This episode can't provide enough content even from start
                
                # Find maximum offset that still allows min_sec of content
                max_safe_offset = episode_duration - min_sec
                if max_safe_offset < 0:
                    max_safe_offset = 0.0
                
                # Conservative offset: take from earlier in the episode
                safe_offset = min(max_safe_offset, episode_duration * 0.1)  # Max 10% into episode
                
                # Verify this start point can provide minimum duration
                available_duration = self._calculate_available_duration(episodes, ep_idx, safe_offset)
                if available_duration >= min_sec:
                    return (ep_idx, safe_offset)
                    
            except Exception:
                continue
        
        return None  # No valid start point found
    
    def process_material(self, episodes: List[str], drama_name: str, start_ep_idx: int, start_offset: float,
                        min_sec: float, max_sec: float, out_path: str, reference_resolution: Tuple[int, int],
                        target_fps: int, fontfile: str, footer_text: str, side_text: str, use_hw: bool,
                        tail_video: Optional[Path], cover_image: Optional[Path],
                        temp_root: str, keep_temp: bool, tail_cache_dir: str, refresh_tail_cache: bool,
                        material_idx: int, material_total: int, fast_mode: bool, filter_threads: int) -> Path:
        """Process a single material with all processing steps."""
        workdir = tempfile.mkdtemp(prefix="mat_", dir=temp_root)
        t0_all = time.time()
        print(f"🎬 开始素材 | 剧：{drama_name} | 第 {material_idx} / {material_total} 条 | 临时目录：{workdir}")
        
        # Display episode range and start point info
        episode_names = [os.path.basename(ep) for ep in episodes]
        start_episode_name = episode_names[start_ep_idx] if start_ep_idx < len(episode_names) else "N/A"
        print(f"📚 剧集范围: 共 {len(episodes)} 集")
        print(f"   起始集: 第{start_ep_idx + 1}集 ({start_episode_name})")
        print(f"   起始偏移: {start_offset:.1f}s")
        print(f"   时长要求: {min_sec:.1f}s ~ {max_sec:.1f}s")

        try:
            ref_w, ref_h = reference_resolution
            tail_file = str(tail_video) if tail_video else None
            cover_img = str(cover_image) if cover_image else None
            
            # Build segments
            t0 = time.time()
            segs = self.build_segments_at_episode_boundaries(episodes, start_ep_idx, start_offset, min_sec, max_sec)
            print(f"⏱️ 片段选择: {human_duration(time.time()-t0)}")
            if not segs:
                print("⚠️ 无可用片段，跳过。")
                return None
            
            # Display selected segments info
            total_selected_duration = sum(end - start for _, start, end in segs)
            print(f"✅ 已选择 {len(segs)} 个片段，总时长: {total_selected_duration:.1f}s")
            
            # Show detailed segment breakdown
            if len(segs) > 1:
                print("📋 片段详情:")
                for i, (ep_path, s_time, e_time) in enumerate(segs, 1):
                    ep_name = os.path.basename(ep_path)
                    duration = e_time - s_time
                    print(f"   {i}. {ep_name}: {s_time:.1f}s-{e_time:.1f}s (时长: {duration:.1f}s)")
            else:
                ep_name = os.path.basename(segs[0][0])
                s_time, e_time = segs[0][1], segs[0][2]
                print(f"📋 单片段: {ep_name}: {s_time:.1f}s-{e_time:.1f}s")

            # Process individual segments
            tmp_parts = []
            seg_total = len(segs)
            if seg_total == 1:
                print(f"📝 处理片段: {os.path.basename(segs[0][0])} ({segs[0][1]:.1f}s-{segs[0][2]:.1f}s)")
            else:
                print(f"📝 处理 {seg_total} 个片段...")
            
            for idx, (ep_path, s, e) in enumerate(segs, start=1):
                tmp_out = os.path.join(workdir, f"norm_{idx:03d}.mp4")
                if seg_total > 1:
                    print(f"  📹 片段 {idx}/{seg_total}: {os.path.basename(ep_path)} ({s:.1f}s-{e:.1f}s)")
                self.norm_and_trim(ep_path, s, e, tmp_out, ref_w, ref_h, target_fps, fontfile, 
                                 drama_name, footer_text, side_text, workdir, use_hw=use_hw, 
                                 seg_idx=idx, seg_total=seg_total, fast_mode=fast_mode, 
                                 filter_threads=filter_threads, material_idx=material_idx)
                tmp_parts.append(tmp_out)

            # Concatenate main segments
            list_path = os.path.join(workdir, "list_main.txt")
            self.write_ffconcat_list(tmp_parts, list_path)
            concat_main = os.path.join(workdir, "concat_main.mp4")
            t0 = time.time()
            self.concat_videos(list_path, concat_main, filter_threads=filter_threads)
            print(f"⏱️ 主片段拼接: {human_duration(time.time()-t0)}")

            # Add tail if specified
            final_src = concat_main
            if tail_file and os.path.isfile(tail_file):
                tail_norm_cached = self.get_or_build_tail_norm(
                    tail_src=tail_file,
                    ref_w=ref_w, ref_h=ref_h, fps=target_fps,
                    use_hw=use_hw,
                    cache_dir=tail_cache_dir,
                    refresh=refresh_tail_cache,
                    filter_threads=filter_threads
                )
                if tail_norm_cached and os.path.isfile(tail_norm_cached):
                    list2 = os.path.join(workdir, "list_with_tail.txt")
                    self.write_ffconcat_list([concat_main, tail_norm_cached], list2)
                    final_with_tail = os.path.join(workdir, "concat_with_tail.mp4")
                    t0 = time.time()
                    self.concat_videos(list2, final_with_tail, filter_threads=filter_threads)
                    print(f"⏱️ 拼接尾部 用时：{human_duration(time.time()-t0)}")
                    final_src = final_with_tail
                    print("ℹ️ 已追加尾部（缓存）：", tail_norm_cached)
                else:
                    print("⚠️ 尾部缓存不可用，跳过尾部。")
            else:
                if tail_file:
                    print("⚠️ 指定的尾部文件不存在，跳过：", tail_file)

            # Simple final copy with faststart (skip cover for now to fix duration issue)
            t0 = time.time()
            
            self.run_ffmpeg([
                "ffmpeg", "-y",
                "-i", final_src,
                "-c", "copy",
                "-movflags", "+faststart",
                out_path
            ], label="最终输出")
            print(f"⏱️ 最终封装: {human_duration(time.time()-t0)}")

            dt_all = time.time() - t0_all
            
            # Get video duration for display
            try:
                from ..utils.video import probe_duration
                duration = probe_duration(out_path)
                duration_str = human_duration(duration)
            except Exception:
                duration_str = "未知"
            
            print(f"✅ 素材完成 | 剧：{drama_name} | 第 {material_idx} 条 | 时长 {duration_str} | 输出：{out_path} | 用时 {human_duration(dt_all)}")
            return Path(out_path)
            
        finally:
            if not keep_temp:
                try:
                    shutil.rmtree(workdir, ignore_errors=True)
                except Exception:
                    pass
            else:
                print(f"🔧 保留临时目录：{workdir}")
