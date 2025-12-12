"""System utility functions."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Optional


def find_font(name_hint: str) -> Optional[str]:
    """Find font file path containing the specified keyword.
    
    Args:
        name_hint: Font name hint to search for
        
    Returns:
        Font file path if found, None otherwise
    """
    try:
        result = subprocess.run(
            ["fc-list"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        
        for line in result.stdout.splitlines():
            if name_hint.lower() in line.lower():
                return line.split(":")[0]
                
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass  # fc-list not available
    
    return None


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, creating it if necessary.
    
    Args:
        path: Directory path
        
    Returns:
        The directory path
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_cpu_count() -> int:
    """Get the number of CPU cores.
    
    Returns:
        Number of CPU cores, defaults to 4 if unable to determine
    """
    return os.cpu_count() or 4


def even(x: int) -> int:
    """Ensure number is even.
    
    Args:
        x: Input number
        
    Returns:
        Even number (decremented by 1 if odd)
    """
    return x if x % 2 == 0 else x - 1


def get_runtime_search_roots() -> List[Path]:
    """获取运行时用于查找资源的根目录列表（按优先级排序）。

    主要解决 PyInstaller one-file 场景下 __file__ 指向临时目录，
    导致 assets/configs 等相对路径无法定位的问题。
    查找顺序：
    1. 可执行文件所在目录（PyInstaller/系统安装后最常见）
    2. PyInstaller 解包目录（若未来把资源打进二进制）
    3. 当前工作目录
    4. 仓库根目录（开发态兜底）
    """
    roots: List[Path] = []

    # 1) 可执行文件目录（对外分发包 assets 通常放这里）
    try:
        exe_dir = Path(sys.executable).resolve().parent
        roots.append(exe_dir)
    except Exception:
        pass

    # 2) PyInstaller 解包目录（可选）
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        try:
            roots.append(Path(meipass))
        except Exception:
            pass

    # 3) 当前工作目录
    try:
        roots.append(Path.cwd())
    except Exception:
        pass

    # 4) 开发态仓库根目录（从本文件向上 3 层）
    try:
        repo_root = Path(__file__).resolve().parents[3]
        roots.append(repo_root)
    except Exception:
        pass

    # 去重并保持顺序
    unique: List[Path] = []
    seen: set = set()
    for r in roots:
        try:
            rr = r.resolve()
        except Exception:
            rr = r
        if rr not in seen:
            unique.append(rr)
            seen.add(rr)
    return unique


def resolve_asset_path(rel_or_abs_path: str, roots: Optional[Iterable[Path]] = None) -> Optional[str]:
    """解析资源路径，支持相对 assets/configs 路径。

    Args:
        rel_or_abs_path: 相对或绝对路径
        roots: 可选自定义搜索根目录

    Returns:
        找到则返回绝对路径字符串，否则返回 None
    """
    if not rel_or_abs_path:
        return None

    p = Path(rel_or_abs_path)
    if p.is_absolute():
        return str(p) if p.is_file() else None

    for root in (list(roots) if roots is not None else get_runtime_search_roots()):
        candidate = root / rel_or_abs_path
        if candidate.is_file():
            return str(candidate)
    return None
