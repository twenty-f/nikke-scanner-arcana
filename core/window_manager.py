import ctypes
import time

import win32api
import win32con
import win32gui
import win32process

from core.log_utils import error, step, warn

try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

DEFAULT_WINDOW_TITLE = "胜利女神：新的希望"
FOCUS_THROTTLE_SEC = 0.35
FOCUS_SETTLE_SEC = 0.45

_focus_cache = {"title": None, "at": 0.0, "ok": False}


def _is_foreground(hwnd):
    try:
        return ctypes.windll.user32.GetForegroundWindow() == hwnd
    except Exception:
        return False


def _apply_game_focus(hwnd, *, center=True):
    """
    Win32 置顶并尝试抢到前台焦点。
    返回是否已成功成为前台窗口。
    """
    user32 = ctypes.windll.user32
    current_thread = win32api.GetCurrentThreadId()
    window_thread, _ = win32process.GetWindowThreadProcessId(hwnd)
    focus_ok = False

    try:
        win32gui.SystemParametersInfo(
            win32con.SPI_SETFOREGROUNDLOCKTIMEOUT,
            0,
            win32con.SPIF_SENDWININICHANGE | win32con.SPIF_UPDATEINIFILE,
        )
    except Exception:
        pass

    try:
        user32.AttachThreadInput(current_thread, window_thread, True)
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        if center:
            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            width = right - left
            height = bottom - top

            try:
                monitor_handle = win32api.MonitorFromWindow(
                    hwnd, win32con.MONITOR_DEFAULTTONEAREST
                )
                monitor_info = win32api.GetMonitorInfo(monitor_handle)
                screen_l, screen_t, screen_r, screen_b = monitor_info["Work"]
            except Exception as exc:
                warn("WIN", f"多显示器探测失败，使用主屏: {exc}")
                work_area = win32gui.SystemParametersInfo(win32con.SPI_GETWORKAREA)
                screen_l, screen_t, screen_r, screen_b = work_area

            screen_width = screen_r - screen_l
            screen_height = screen_b - screen_t
            center_x = screen_l + (screen_width - width) // 2
            center_y = screen_t + (screen_height - height) // 2

            if abs(left - center_x) > 5 or abs(top - center_y) > 5:
                win32gui.SetWindowPos(
                    hwnd,
                    0,
                    center_x,
                    center_y,
                    0,
                    0,
                    win32con.SWP_NOZORDER | win32con.SWP_NOSIZE,
                )
                time.sleep(0.3)

        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE,
        )
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_NOTOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE,
        )
        win32gui.SetForegroundWindow(hwnd)
        focus_ok = _is_foreground(hwnd)

    except Exception as exc:
        warn("WIN", f"置顶异常: {exc}")
        import pydirectinput

        pydirectinput.press("alt")
        try:
            win32gui.SetForegroundWindow(hwnd)
            focus_ok = _is_foreground(hwnd)
        except Exception:
            focus_ok = False

    finally:
        try:
            user32.AttachThreadInput(current_thread, window_thread, False)
        except Exception:
            pass

    if not focus_ok:
        time.sleep(0.12)
        focus_ok = _is_foreground(hwnd)

    return focus_ok


def ensure_game_focus(
    window_title=DEFAULT_WINDOW_TITLE,
    *,
    force=False,
    center=False,
    log=False,
):
    """
    确保游戏窗口在前台（节流，避免每次截屏都完整置顶）。

    force=True：跳过节流，强制执行（扫描开始等关键节点）。
    center=True：将窗口移到所在显示器工作区居中（仅扫描开始时使用）。
    log=True：成功/失败时输出 [WIN] 日志。
    """
    global _focus_cache

    now = time.time()
    if (
        not force
        and _focus_cache["title"] == window_title
        and (now - _focus_cache["at"]) < FOCUS_THROTTLE_SEC
    ):
        return _focus_cache["ok"]

    hwnd = win32gui.FindWindow(None, window_title)
    if not hwnd:
        error("WIN", f"未找到窗口: {window_title}")
        _focus_cache = {"title": window_title, "at": now, "ok": False}
        return False

    focus_ok = _apply_game_focus(hwnd, center=center)
    if focus_ok:
        time.sleep(FOCUS_SETTLE_SEC)
        focus_ok = _is_foreground(hwnd)

    _focus_cache = {"title": window_title, "at": time.time(), "ok": focus_ok}

    if log:
        if focus_ok:
            step("WIN", "窗口已置顶")
        else:
            warn("WIN", "未能抢到游戏焦点，请确认游戏窗口未被其他程序完全遮挡")

    return focus_ok


def force_bring_to_front(window_title=DEFAULT_WINDOW_TITLE):
    """扫描开始时：强制置顶、居中，并输出日志。"""
    return ensure_game_focus(window_title, force=True, center=True, log=True)


def get_window_rect(window_title=DEFAULT_WINDOW_TITLE):
    """获取目标窗口在整个跨屏虚拟桌面上的真实绝对坐标。"""
    hwnd = win32gui.FindWindow(None, window_title)
    if not hwnd:
        return None

    try:
        rect = win32gui.GetWindowRect(hwnd)
        return (rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])
    except Exception as exc:
        warn("WIN", f"获取窗口尺寸失败: {exc}")
        return None
