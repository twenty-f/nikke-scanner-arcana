"""截屏、点击、剪贴板注入、模板轮询。"""

import time

import pydirectinput
import pyperclip

from core.game_screen import capture_game_window, click_screen, get_game_screen
from core.vision import find_image
from core.window_manager import ensure_game_focus

TEMPLATE_FIND_RETRIES = 8
TEMPLATE_FIND_INTERVAL = 0.8


def load_screen(*, ensure_focus=True):
    """加载游戏窗口截图（默认截屏前 ensure_game_focus）。"""
    return capture_game_window(ensure_focus=ensure_focus)


def press_game_key(key, wait_after=0.0, *, force_focus=True):
    """向游戏窗口发送按键（发送前确保焦点）。"""
    ensure_game_focus(force=force_focus, center=False)
    pydirectinput.press(key)
    if wait_after:
        time.sleep(wait_after)


def click_at(x, y, wait_after=0.5):
    click_screen(x, y, wait_after=wait_after)


def click_at_window_local(local_x, local_y, wait_after=0.5):
    """窗口内坐标 → 屏幕坐标后点击（须在同一次 capture 之后调用）。"""
    sx, sy = get_game_screen().to_screen_xy(local_x, local_y)
    click_screen(sx, sy, wait_after=wait_after)


def paste_from_clipboard(text):
    ensure_game_focus(force=True, center=False)
    pyperclip.copy(text)
    time.sleep(0.2)
    pydirectinput.keyDown("ctrl")
    pydirectinput.press("a")
    time.sleep(0.05)
    pydirectinput.press("v")
    pydirectinput.keyUp("ctrl")
    time.sleep(0.3)


def wait_for_template(
    template_path,
    threshold=0.75,
    retries=TEMPLATE_FIND_RETRIES,
    interval=TEMPLATE_FIND_INTERVAL,
):
    for attempt in range(retries):
        screen = load_screen()
        if screen is None:
            time.sleep(interval)
            continue
        match = find_image(screen, template_path, threshold=threshold, show_result=False)
        if match:
            return match
        if attempt < retries - 1:
            time.sleep(interval)
    return None


def click_template(
    template_path,
    threshold=0.75,
    offset_x=0,
    offset_y=0,
    retries=TEMPLATE_FIND_RETRIES,
):
    from core.search.locators import match_center

    match = wait_for_template(template_path, threshold=threshold, retries=retries)
    if not match:
        return False
    cx, cy = match_center(match)
    click_at(cx + offset_x, cy + offset_y)
    return True
