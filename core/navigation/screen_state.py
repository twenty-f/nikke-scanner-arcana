"""当前界面判定：仓库 / 详情 / 大厅。"""

from core.aspect_layout import layout
from core.automation.actions import load_screen
from core.navigation.constants import (
    BTN_NIKKE,
    QUIT_CONFIRM_MAX_SCALE,
    QUIT_CONFIRM_MIN_SCALE,
    QUIT_CONFIRM_THRESHOLD,
    QUIT_GAME_CONFIRM,
)
from core.search.constants import BTN_FILTER, FILTER_BTN_THRESHOLD
from core.search.locators import filter_toolbar_slice
from core.vision import find_image


def find_quit_confirm(screen):
    return find_image(
        screen,
        QUIT_GAME_CONFIRM,
        threshold=QUIT_CONFIRM_THRESHOLD,
        min_scale=QUIT_CONFIRM_MIN_SCALE,
        max_scale=QUIT_CONFIRM_MAX_SCALE,
        silent=True,
    )


def find_lobby_nikke_btn(screen):
    if screen is None:
        return None
    h = screen.shape[0]
    roi_y_offset = int(h * layout.lobby_roi_y_start)
    return find_image(screen[roi_y_offset:, :], BTN_NIKKE, threshold=0.60, silent=True)


def is_filter_toolbar_visible(screen):
    row, _, _ = filter_toolbar_slice(screen)
    return bool(
        find_image(
            row,
            BTN_FILTER,
            threshold=FILTER_BTN_THRESHOLD,
            min_scale=0.55,
            max_scale=1.35,
            silent=True,
        )
    )


def is_search_row_visible():
    from core.search.panel import probe_search_panel

    _, is_open = probe_search_panel()
    return is_open


def is_in_warehouse():
    """妮姬仓库列表（非角色详情，且顶部筛选/搜索区可见）。"""
    screen = load_screen()
    if screen is None:
        return False

    h, w = screen.shape[:2]
    roi = screen[:, int(w * layout.detail_roi_x_start):]
    top = find_image(roi, "assets/anchor_top.png", threshold=0.80, silent=True)
    bottom = find_image(roi, "assets/anchor_bottom.png", threshold=0.80, silent=True)
    if top and bottom:
        return False

    if is_search_row_visible():
        return True
    return is_filter_toolbar_visible(screen)


def is_on_character_detail():
    if is_in_warehouse():
        return False

    screen = load_screen()
    if screen is None:
        return False

    h, w = screen.shape[:2]
    roi = screen[:, int(w * layout.detail_roi_x_start):]
    top = find_image(roi, "assets/anchor_top.png", threshold=0.80, silent=True)
    bottom = find_image(roi, "assets/anchor_bottom.png", threshold=0.80, silent=True)
    return bool(top and bottom)


def is_quit_confirm_visible():
    screen = load_screen()
    if screen is None:
        return False
    return bool(find_quit_confirm(screen))


def is_lobby_ready():
    screen = load_screen()
    if screen is None:
        return False
    if find_quit_confirm(screen):
        return False
    return bool(find_lobby_nikke_btn(screen))
