"""
tqdm 在非 TTY（重定向、部分 IDE 任务、管道）下会默认关闭动画条。
此处统一强制启用，并写到 stderr，避免与 stdout 日志混在一起。
"""
from __future__ import annotations

import sys
from typing import Any


def tqdm(*args: Any, **kwargs: Any):
    from tqdm import tqdm as _tqdm

    defaults: dict[str, Any] = {
        "disable": False,
        "file": sys.stderr,
        "ascii": True,
        "mininterval": 0.2,
        "dynamic_ncols": True,
    }
    defaults.update(kwargs)
    return _tqdm(*args, **defaults)


def ensure_line_buffered_stdio() -> None:
    """尽量行缓冲，便于在终端里立刻看到 print / tqdm。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(line_buffering=True)
        except Exception:
            pass
