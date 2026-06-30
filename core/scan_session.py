import threading
from datetime import datetime, timezone

_lock = threading.Lock()
_state = {
    "status": "idle",
    "error_type": None,
    "message": "",
    "detail": "",
    "processed": 0,
    "total": 0,
    "current_character": "",
    "started_at": None,
    "finished_at": None,
}


def _now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _reset_locked():
    _state.update({
        "status": "idle",
        "error_type": None,
        "message": "",
        "detail": "",
        "processed": 0,
        "total": 0,
        "current_character": "",
        "started_at": None,
        "finished_at": None,
    })


def begin_scan(characters):
    with _lock:
        _state.update({
            "status": "running",
            "error_type": None,
            "message": "扫描进行中，请勿操作键鼠…",
            "detail": "",
            "processed": 0,
            "total": len(characters),
            "current_character": "",
            "started_at": _now_iso(),
            "finished_at": None,
        })


def set_scan_phase(message):
    """更新扫描阶段提示（初始化、导航等），供前端轮询展示。"""
    with _lock:
        if _state["status"] == "running":
            _state["message"] = message


def mark_progress(index, char_name):
    with _lock:
        if _state["status"] != "running":
            return
        _state["processed"] = index
        _state["current_character"] = char_name
        _state["message"] = "正在扫描干员"


def mark_character_done(index):
    with _lock:
        if _state["status"] != "running":
            return
        _state["processed"] = index + 1


def finish_scan(message="全部干员扫描已完成。"):
    with _lock:
        _state.update({
            "status": "completed",
            "error_type": None,
            "message": message,
            "detail": "",
            "current_character": "",
            "finished_at": _now_iso(),
        })


def abort_scan(error_type, message, detail=""):
    with _lock:
        _state.update({
            "status": "error",
            "error_type": error_type,
            "message": message,
            "detail": detail,
            "current_character": "",
            "finished_at": _now_iso(),
        })


def is_running():
    with _lock:
        return _state["status"] == "running"


def get_scan_status():
    with _lock:
        return dict(_state)
