"""武器筛选状态与「重置筛选」不变量（须在第二行执行放大镜下方，避开 Burst 行）。"""

import time

from core.game_screen import click_screen
from core.log_utils import step, warn
from core.search.locators import resolve_reset_filter_click

_weapon_filter_active = False


def is_weapon_filter_active():
    return _weapon_filter_active


def set_weapon_filter_active(active):
    global _weapon_filter_active
    _weapon_filter_active = bool(active)


def reset_weapon_filter_on_search_ui():
    """在搜索界面直接点击「重置筛选」，不使用 ESC。"""
    global _weapon_filter_active
    step("SEARCH", "清除上一位武器筛选")
    cx, cy, method = resolve_reset_filter_click()
    if cx is not None:
        step("SEARCH", f"重置武器筛选（{method}）")
        click_screen(cx, cy, wait_after=0.8)
        time.sleep(1.0)
        _weapon_filter_active = False
        return True

    warn("SEARCH", "未找到重置筛选按钮")
    return False


def ensure_weapon_filter_cleared(is_panel_active):
    """下一位干员搜索前清除上一位遗留的武器筛选。"""
    global _weapon_filter_active
    if not _weapon_filter_active:
        return True
    for attempt in range(3):
        if is_panel_active():
            if reset_weapon_filter_on_search_ui():
                return True
        if attempt < 2:
            time.sleep(0.6)
    warn("SEARCH", "未能重置武器筛选（未点击任何位置）")
    return False
