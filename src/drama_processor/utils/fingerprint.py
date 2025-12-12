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


def _get_windows_machine_guid_from_wsl() -> Optional[str]:
    """在 WSL 内尝试读取 Windows MachineGuid（更稳定的机器绑定）。

    失败则返回 None（例如不是 WSL、或无权限/路径不存在）。
    """
    # WSL 内一般可访问该路径
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
    - 优先取 WSL 下的 Windows MachineGuid（若可读）
    - 再组合 Linux machine-id（若可读）
    - 最终做 sha256，避免直接暴露原始标识
    """
    win_guid = _get_windows_machine_guid_from_wsl() or ""
    linux_id = _get_linux_machine_id() or ""

    raw = f"win:{win_guid}|linux:{linux_id}".encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()

