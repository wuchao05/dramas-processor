"""FFmpeg 可执行文件路径检测"""
import os
import shutil
import sys
from pathlib import Path
from typing import Optional


def find_ffmpeg() -> str:
    """查找 ffmpeg 可执行文件路径（优先使用内置版本）"""
    # 1. 检查项目 bin 目录（打包或开发环境）
    local_ffmpeg = _find_local_ffmpeg("ffmpeg")
    if local_ffmpeg:
        return local_ffmpeg
    
    # 2. 检查系统 PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    
    # 3. 兜底
    return "ffmpeg"


def find_ffprobe() -> str:
    """查找 ffprobe 可执行文件路径（优先使用内置版本）"""
    # 1. 检查项目 bin 目录
    local_ffprobe = _find_local_ffmpeg("ffprobe")
    if local_ffprobe:
        return local_ffprobe
    
    # 2. 检查系统 PATH
    system_ffprobe = shutil.which("ffprobe")
    if system_ffprobe:
        return system_ffprobe
    
    # 3. 兜底
    return "ffprobe"


def _find_local_ffmpeg(name: str) -> Optional[str]:
    """在项目 bin 目录中查找 FFmpeg"""
    # 搜索路径列表
    search_paths = []
    
    # 1. 可执行文件目录（打包后）
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        search_paths.append(exe_dir / "bin")
        search_paths.append(exe_dir)
    
    # 2. 项目根目录（开发环境）
    try:
        project_root = Path(__file__).resolve().parents[3]
        search_paths.append(project_root / "bin")
    except Exception:
        pass
    
    # 3. 当前工作目录
    search_paths.append(Path.cwd() / "bin")
    
    # 查找可执行文件
    exe_name = f"{name}.exe" if os.name == "nt" else name
    for search_path in search_paths:
        candidate = search_path / exe_name
        if candidate.exists():
            return str(candidate)
    
    return None
