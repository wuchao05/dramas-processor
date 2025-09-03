"""File utility functions."""

import glob
import hashlib
import math
import os
import subprocess
from pathlib import Path
from typing import List, Optional


def list_episode_files(episode_dir: Path) -> List[Path]:
    """List episode files in directory, sorted by episode number.
    
    Args:
        episode_dir: Directory containing episode files
        
    Returns:
        List of episode file paths sorted by number
    """
    files = glob.glob(str(episode_dir / "*.mp4"))
    
    def sort_key(file_path: str) -> float:
        """Generate sort key for episode file."""
        base_name = Path(file_path).stem
        try:
            return int(base_name)
        except ValueError:
            return math.inf
    
    sorted_files = sorted(files, key=sort_key)
    return [Path(f) for f in sorted_files]


def md5_of_text(text: str) -> str:
    """Calculate MD5 hash of text.
    
    Args:
        text: Input text
        
    Returns:
        MD5 hash as hexadecimal string
    """
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def md5_of_file(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Calculate MD5 hash of file.
    
    Args:
        file_path: Path to file
        chunk_size: Chunk size for reading file
        
    Returns:
        MD5 hash as hexadecimal string
        
    Raises:
        OSError: If file cannot be read
    """
    hash_obj = hashlib.md5()
    
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hash_obj.update(chunk)
    
    return hash_obj.hexdigest()


def write_text_file(path: str, text: str):
    """Write text to file with UTF-8 encoding."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def ensure_dir(path: str) -> str:
    """Ensure directory exists, create if needed."""
    os.makedirs(path, exist_ok=True)
    return path


def find_font(name_hint: str) -> str:
    """Auto-find font file path containing specified keywords."""
    try:
        out = subprocess.check_output(["fc-list"], text=True)
        for line in out.splitlines():
            if name_hint.lower() in line.lower():
                return line.split(":")[0]
    except Exception as e:
        print("⚠️ 字体查找失败：", e)
    return ""


def has_mp4(directory: str) -> bool:
    """Check if directory contains MP4 files."""
    return len(glob.glob(os.path.join(directory, "*.mp4"))) > 0


def scan_drama_dirs(root_dir: str) -> List[str]:
    """Scan for drama directories containing MP4 files."""
    excluded_names = {"exports", "_exports"}
    
    dirs = []
    for entry in os.scandir(root_dir):
        if (entry.is_dir() and 
            not entry.name.startswith(".") and 
            entry.name.lower() not in excluded_names and 
            has_mp4(entry.path)):
            dirs.append(entry.path)
    
    return sorted(dirs)


# Cover picking function removed


def prepare_export_dir(exports_root: str, drama_name: str, date_str: Optional[str] = None) -> tuple[str, Optional[str]]:
    """Prepare export directory with run suffix, optionally using date-based organization."""
    # 如果指定了日期字符串，创建基于日期的目录结构
    if date_str:
        # 获取 exports_root 的父目录
        parent_dir = os.path.dirname(os.path.abspath(exports_root))
        date_export_dir = os.path.join(parent_dir, f"{date_str}导出")
        
        # 确保日期导出目录存在
        os.makedirs(date_export_dir, exist_ok=True)
        
        # 使用日期导出目录作为新的根目录
        exports_root = date_export_dir
    
    # 确保导出根目录存在
    os.makedirs(exports_root, exist_ok=True)
    
    existing = []
    base_plain = os.path.join(exports_root, drama_name)
    
    if os.path.isdir(base_plain):
        existing.append(-1)
    
    for entry in os.scandir(exports_root):
        if not entry.is_dir():
            continue
        name = entry.name
        if name == drama_name:
            continue
        
        prefix = f"{drama_name}-"
        if name.startswith(prefix):
            suffix = name[len(prefix):]
            if len(suffix) == 3 and suffix.isdigit():
                existing.append(int(suffix))
    
    if not existing:
        out_dir = base_plain
        run_suffix = None
    else:
        next_idx = (max(existing) + 1) if max(existing) >= 0 else 1
        run_suffix = f"{next_idx:03d}"
        out_dir = os.path.join(exports_root, f"{drama_name}-{run_suffix}")
    
    os.makedirs(out_dir, exist_ok=True)
    return out_dir, run_suffix


def get_latest_export_dir(exports_root: str, drama_name: str, date_str: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """Get the latest export directory for a drama, optionally using date-based organization."""
    # 如果指定了日期字符串，在对应的日期目录中查找
    if date_str:
        parent_dir = os.path.dirname(os.path.abspath(exports_root))
        date_export_dir = os.path.join(parent_dir, f"{date_str}导出")
        exports_root = date_export_dir
    
    if not os.path.isdir(exports_root):
        return None, None
    
    base_plain = os.path.join(exports_root, drama_name)
    max_suffix = -999
    best_dir = None
    best_suffix: Optional[str] = None
    
    if os.path.isdir(base_plain):
        best_dir = base_plain
        max_suffix = -1
        best_suffix = None
    
    prefix = f"{drama_name}-"
    for entry in os.scandir(exports_root):
        if not entry.is_dir():
            continue
        name = entry.name
        if not name.startswith(prefix):
            continue
        
        suffix = name[len(prefix):]
        if len(suffix) == 3 and suffix.isdigit():
            val = int(suffix)
            if val > max_suffix:
                max_suffix = val
                best_dir = os.path.join(exports_root, name)
                best_suffix = f"{val:03d}"
    
    return best_dir, best_suffix


def count_existing_materials(dir_path: str) -> int:
    """Count existing MP4 materials in directory."""
    if not dir_path or not os.path.isdir(dir_path):
        return 0
    return len(glob.glob(os.path.join(dir_path, "*.mp4")))


def ensure_temp_root(temp_root_opt: Optional[str]) -> str:
    """Ensure temporary root directory exists."""
    root = (temp_root_opt.strip() if temp_root_opt else "/tmp")
    try:
        os.makedirs(root, exist_ok=True)
    except Exception as e:
        print(f"⚠️ 创建临时目录失败（{root}），回退到 /tmp：{e}")
        root = "/tmp"
        os.makedirs(root, exist_ok=True)
    return root

