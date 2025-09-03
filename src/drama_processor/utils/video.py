"""Video processing utility functions."""

import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Union


def parse_rate(rate_str: Optional[str]) -> float:
    """Parse frame rate string.
    
    Args:
        rate_str: Frame rate string (e.g., "30/1", "25.0")
        
    Returns:
        Frame rate as float
    """
    if not rate_str or rate_str == "0/0":
        return 0.0
    
    if "/" in rate_str:
        try:
            numerator, denominator = rate_str.split("/", 1)
            num, denom = float(numerator), float(denominator)
            return 0.0 if denom == 0 else num / denom
        except (ValueError, ZeroDivisionError):
            return 0.0
    
    try:
        return float(rate_str)
    except ValueError:
        return 0.0


def probe_video_stream(path: Union[str, Path]) -> Dict[str, Any]:
    """Probe video stream information.
    
    Args:
        path: Video file path
        
    Returns:
        Dictionary containing video information
        
    Raises:
        subprocess.CalledProcessError: If ffprobe fails
        json.JSONDecodeError: If output is not valid JSON
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_streams",
        "-show_format",
        "-of", "json",
        str(path)
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True
    )
    
    info = json.loads(result.stdout)
    stream = (info.get("streams") or [{}])[0]
    format_info = info.get("format") or {}
    
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    duration = float(
        format_info.get("duration") or 
        stream.get("duration") or 
        0.0
    )
    fps = (
        parse_rate(stream.get("avg_frame_rate")) or 
        parse_rate(stream.get("r_frame_rate"))
    )
    
    return {
        "w": width,
        "h": height,
        "duration": duration,
        "fps": fps
    }


def probe_duration(path: Union[str, Path]) -> float:
    """Get video duration.
    
    Args:
        path: Video file path
        
    Returns:
        Duration in seconds
    """
    info = probe_video_stream(path)
    return info["duration"]


def is_black_frame_at(video_path: Path, time: float, amount_pct: int = 98, pix_th: int = 32) -> bool:
    """Check if frame at given time is black.
    
    Args:
        video_path: Video file path
        time: Time in seconds
        amount_pct: Black frame threshold percentage
        pix_th: Pixel threshold
        
    Returns:
        True if frame is black
    """
    cmd = [
        "ffmpeg", "-v", "error",
        "-i", str(video_path),
        "-ss", f"{time}",
        "-frames:v", "1",
        "-vf", f"blackframe=amount={amount_pct}:th={pix_th}",
        "-f", "null", "-"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        output = result.stdout or ""
        if "pblack:" in output:
            pblack_value = float(output.split("pblack:")[-1].split()[0])
            return pblack_value >= amount_pct
            
    except (subprocess.CalledProcessError, ValueError, IndexError):
        pass
    
    return False


def extract_first_frame(video_path: Path, output_path: Path) -> None:
    """Extract first non-black frame from video.
    
    Args:
        video_path: Input video path
        output_path: Output image path
        
    Raises:
        subprocess.CalledProcessError: If extraction fails
    """
    probe_points = [0.05, 0.5, 1.0, 1.5, 2.5, 3.5, 5.0]
    
    for time_point in probe_points:
        if not is_black_frame_at(video_path, time_point):
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-ss", f"{time_point}",
                "-frames:v", "1",
                str(output_path)
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return
    
    # Fallback: extract frame at 1 second
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-ss", "1.0",
        "-frames:v", "1",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)

