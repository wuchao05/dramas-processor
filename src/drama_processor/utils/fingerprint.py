"""机器指纹生成（用于 license 机器绑定）。"""

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Optional


def _read_text(path: str) -> Optional[str]:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except Exception:
        return None


def _get_linux_machine_id() -> Optional[str]:
    # Linux/WSL 常见
    return _read_text("/etc/machine-id") or _read_text("/var/lib/dbus/machine-id")


def _get_windows_machine_guid() -> Optional[str]:
    """在 Windows 下读取 MachineGuid（原生 Windows 和 WSL 兼容）"""
    import platform
    
    # Windows 原生环境
    if platform.system() == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography"
            )
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            return value
        except Exception:
            return None
    
    # WSL 环境（通过 reg.exe 访问 Windows 注册表）
    reg = Path("/mnt/c/Windows/System32/reg.exe")
    if not reg.exists():
        return None
    try:
        out = subprocess.check_output(
            [str(reg), "query", r"HKLM\SOFTWARE\Microsoft\Cryptography", "/v", "MachineGuid"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        # 输出示例：
        # MachineGuid    REG_SZ    xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        for line in out.splitlines():
            if "MachineGuid" in line and "REG_" in line:
                parts = line.split()
                if parts:
                    return parts[-1].strip()
    except Exception:
        return None
    return None


def get_machine_fingerprint() -> str:
    """获取当前机器指纹（sha256 十六进制）。

    策略：
    - 优先取 Windows MachineGuid（原生 Windows 或 WSL）
    - 再组合 Linux machine-id（若可读）
    - 最终做 sha256，避免直接暴露原始标识
    """
    win_guid = _get_windows_machine_guid() or ""
    linux_id = _get_linux_machine_id() or ""

    raw = f"win:{win_guid}|linux:{linux_id}".encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()

