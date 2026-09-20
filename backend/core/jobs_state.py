"""后台任务进度状态管理。
被 scheduler.py 和 api/routes.py 共用，提供线程安全的进度读写。
"""
from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
# 结构: { task_name: { progress, label, done, error, running } }
_state: dict[str, dict[str, Any]] = {}

_DEFAULT = {"progress": 0.0, "label": "等待开始", "done": False, "error": "", "running": False}


def get_all() -> dict[str, dict[str, Any]]:
    with _lock:
        return {k: dict(v) for k, v in _state.items()}


def get(task: str) -> dict[str, Any]:
    with _lock:
        return dict(_state.get(task, _DEFAULT))


def start(task: str, label: str = "开始"):
    with _lock:
        _state[task] = {
            "progress": 0.0,
            "label": label,
            "done": False,
            "error": "",
            "running": True,
            "cancelRequested": False,
        }


def request_cancel(task: str):
    """请求取消任务：任务函数应在每轮循环检查 is_cancel_requested 后自行结束。"""
    with _lock:
        cur = _state.setdefault(task, dict(_DEFAULT))
        cur["cancelRequested"] = True


def is_cancel_requested(task: str) -> bool:
    with _lock:
        return bool(_state.get(task, {}).get("cancelRequested"))


def update(task: str, progress: float, label: str = ""):
    with _lock:
        cur = _state.setdefault(task, dict(_DEFAULT))
        cur["progress"] = max(0.0, min(1.0, float(progress)))
        if label:
            cur["label"] = label
        cur["running"] = True
        cur["done"] = False


def finish(task: str, label: str = "完成", error: str = ""):
    with _lock:
        _state[task] = {
            "progress": 1.0 if not error else _state.get(task, {}).get("progress", 0.0),
            "label": label,
            "done": not bool(error),
            "error": error,
            "running": False,
        }


def is_running(task: str) -> bool:
    with _lock:
        return bool(_state.get(task, {}).get("running"))
