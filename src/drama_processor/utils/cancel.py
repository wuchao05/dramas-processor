"""取消处理相关工具。"""

from threading import Event
from typing import Optional


class CancelledError(Exception):
    """用户取消处理。"""


def raise_if_cancelled(cancel_event: Optional[Event]) -> None:
    """检测是否已取消，若已取消则抛出异常。"""
    if cancel_event is not None and cancel_event.is_set():
        raise CancelledError("已取消处理")
