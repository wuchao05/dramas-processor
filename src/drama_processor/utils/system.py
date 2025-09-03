"""System utility functions."""

import os
import subprocess
from pathlib import Path
from typing import Optional


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

