"""武器类型筛选（打开筛选面板 → 选枪种）。"""

import os
import time

from core.aspect_layout import layout
from core.automation.actions import press_game_key
from core.game_screen import capture_with_offset
from core.automation.actions import click_at
from core.log_utils import error, step, warn
from core.search.constants import (
    BTN_FILTER,
    FILTER_BTN_THRESHOLD,
    WEAPON_FILTER_MAX_SCALE,
    WEAPON_FILTER_MIN_SCALE,
    WEAPON_FILTER_THRESHOLD,
)
from core.search.filter import ensure_weapon_filter_cleared, is_weapon_filter_active, set_weapon_filter_active
from core.search.locators import filter_toolbar_slice, match_center
from core.search.panel import is_search_panel_active
from core.vision import find_image


def _filter_panel_slice(screen):
    if screen is None:
        return None, 0, 0
    h, w = screen.shape[:2]
    x1 = int(w * layout.filter_panel_roi_x[0])
    x2 = int(w * layout.filter_panel_roi_x[1])
    y1 = int(h * layout.filter_panel_roi_y[0])
    y2 = int(h * layout.filter_panel_roi_y[1])
    return screen[y1:y2, x1:x2], x1, y1


def _click_template_in_roi(roi, roi_x1, roi_y1, ox, oy, template_path, threshold=0.75, min_scale=0.55, max_scale=1.35):
    match = find_image(
        roi,
        template_path,
        threshold=threshold,
        min_scale=min_scale,
        max_scale=max_scale,
        silent=True,
    )
    if not match:
        return False
    cx, cy = match_center(match)
    click_at(ox + cx + roi_x1, oy + cy + roi_y1)
    return True


def click_filter_entry():
    screen, ox, oy = capture_with_offset()
    if screen is None:
        return False
    row, rx1, ry1 = filter_toolbar_slice(screen)
    match = find_image(
        row,
        BTN_FILTER,
        threshold=FILTER_BTN_THRESHOLD,
        min_scale=0.55,
        max_scale=1.35,
        silent=True,
    )
    if not match:
        return False
    cx, cy = match_center(match)
    click_at(ox + cx + rx1, oy + cy + ry1, wait_after=0.6)
    return True


def apply_weapon_filter(weapon_type):
    weapon_img = f"assets/ui/weapon_{weapon_type}.png"

    if not os.path.exists(weapon_img):
        error("FILTER", f"武器图不存在: {weapon_type}")
        return False

    if is_weapon_filter_active():
        ensure_weapon_filter_cleared(is_search_panel_active)

    step("FILTER", f"打开筛选 → {weapon_type}")
    if not click_filter_entry():
        error("FILTER", "未找到筛选入口")
        return False
    time.sleep(0.9)

    screen, ox, oy = capture_with_offset()
    panel, px1, py1 = _filter_panel_slice(screen)
    if panel is None:
        warn("FILTER", "无法截取筛选面板")
        press_game_key("esc", wait_after=0.5)
        return False

    if not _click_template_in_roi(
        panel,
        px1,
        py1,
        ox,
        oy,
        weapon_img,
        threshold=WEAPON_FILTER_THRESHOLD,
        min_scale=WEAPON_FILTER_MIN_SCALE,
        max_scale=WEAPON_FILTER_MAX_SCALE,
    ):
        warn("FILTER", f"筛选页内未找到 {weapon_type}")
        press_game_key("esc", wait_after=0.5)
        return False

    step("FILTER", f"已选 {weapon_type}")
    press_game_key("esc", wait_after=1.5)
    set_weapon_filter_active(True)
    return True
