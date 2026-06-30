"""游戏窗口截屏与屏幕坐标点击（唯一坐标入口，禁止全屏比例混用）。"""

import time

import cv2
import mss
import numpy as np
import pydirectinput

from core.window_manager import DEFAULT_WINDOW_TITLE, ensure_game_focus, get_window_rect


def _grab_bgr(left, top, width, height):
    if width <= 0 or height <= 0:
        return None
    region = {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}
    with mss.mss() as sct:
        shot = sct.grab(region)
    bgra = np.array(shot)
    return cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)


class GameScreen:
    """绑定游戏窗口标题，截屏与点击均基于窗口 rect。"""

    __slots__ = ("window_title", "_ox", "_oy", "_last")

    def __init__(self, window_title=DEFAULT_WINDOW_TITLE):
        self.window_title = window_title
        self._ox = 0
        self._oy = 0
        self._last = None

    def rect(self):
        return get_window_rect(self.window_title)

    def capture(self, *, ensure_focus=True):
        """截取游戏窗口 BGR 图像；失败返回 None。"""
        if ensure_focus:
            ensure_game_focus(self.window_title, center=False)
        rect = self.rect()
        if not rect:
            return None
        left, top, width, height = rect
        img = _grab_bgr(left, top, width, height)
        if img is None:
            return None
        self._ox, self._oy = left, top
        self._last = img
        return img

    def capture_with_offset(self, *, ensure_focus=True):
        """返回 (窗口图像, 屏幕 ox, 屏幕 oy)。"""
        img = self.capture(ensure_focus=ensure_focus)
        if img is None:
            return None, 0, 0
        return img, self._ox, self._oy

    def click_screen(self, x, y, wait_after=0.5):
        ensure_game_focus(self.window_title, force=True, center=False)
        pydirectinput.moveTo(int(x), int(y))
        time.sleep(0.15)
        pydirectinput.click()
        time.sleep(wait_after)
        return True

    def click_ratio(self, x_ratio, y_ratio, wait_after=0.5):
        rect = self.rect()
        if not rect:
            return False
        left, top, width, height = rect
        self.click_screen(left + width * x_ratio, top + height * y_ratio, wait_after=wait_after)
        return True

    def to_screen_xy(self, local_x, local_y):
        """窗口内坐标 → 屏幕坐标。"""
        return self._ox + local_x, self._oy + local_y


_default = GameScreen()


def get_game_screen(window_title=DEFAULT_WINDOW_TITLE):
    if window_title == DEFAULT_WINDOW_TITLE:
        return _default
    return GameScreen(window_title)


def capture_game_window(window_title=DEFAULT_WINDOW_TITLE, *, ensure_focus=True):
    return get_game_screen(window_title).capture(ensure_focus=ensure_focus)


def capture_with_offset(window_title=DEFAULT_WINDOW_TITLE, *, ensure_focus=True):
    return get_game_screen(window_title).capture_with_offset(ensure_focus=ensure_focus)


def click_window_ratio(x_ratio, y_ratio, wait_after=0.5, window_title=DEFAULT_WINDOW_TITLE):
    return get_game_screen(window_title).click_ratio(x_ratio, y_ratio, wait_after=wait_after)


def click_screen(x, y, wait_after=0.5):
    return _default.click_screen(x, y, wait_after=wait_after)
