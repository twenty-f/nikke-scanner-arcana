"""搜索/筛选 UI 模板定位（基于 GameScreen 窗口图像）。"""

from core.aspect_layout import layout
from core.game_screen import capture_with_offset, get_game_screen
from core.search.constants import (
    BTN_FILTER,
    BTN_FILTER_CLEAR,
    BTN_SEARCH_EXECUTE,
    FILTER_BTN_THRESHOLD,
    FILTER_CLEAR_MAX_SCALE,
    FILTER_CLEAR_MIN_SCALE,
    FILTER_CLEAR_THRESHOLD,
    SEARCH_BOX_ACTIVE,
    SEARCH_BOX_MAX_SCALE,
    SEARCH_BOX_MIN_SCALE,
    SEARCH_BOX_MIN_WIDTH,
    SEARCH_BOX_THRESHOLD,
    SEARCH_EXECUTE_MAX_SCALE,
    SEARCH_EXECUTE_MIN_SCALE,
    SEARCH_EXECUTE_THRESHOLD,
    SEARCH_TOGGLE_MAX_TOOLBAR_X_RATIO,
    SEARCH_TOGGLE_MIN_SCALE,
    SEARCH_TOGGLE_MAX_SCALE,
    SEARCH_TOGGLE_THRESHOLD,
)
from core.vision import find_image, find_leftmost_image
from core.window_manager import get_window_rect


def match_center(match):
    loc, width, height = match
    return loc[0] + width // 2, loc[1] + height // 2


def match_in_roi_to_screen(match, ox, oy, roi_y1, roi_x1=0):
    if not match:
        return None
    (lx, ly), tw, th = match
    return ((lx + roi_x1 + ox, ly + roi_y1 + oy), tw, th)


def filter_toolbar_slice(image):
    h, w = image.shape[:2]
    x1 = int(w * layout.filter_toolbar_roi_x[0])
    x2 = int(w * layout.filter_toolbar_roi_x[1])
    y1 = int(h * layout.filter_toolbar_roi_y[0])
    y2 = int(h * layout.filter_toolbar_roi_y[1])
    return image[y1:y2, x1:x2], x1, y1


def search_input_row_slice(image):
    h = image.shape[0]
    y1 = int(h * layout.filter_toolbar_roi_y[1])
    y2 = int(h * layout.search_row_roi_y[1])
    if y2 <= y1 + 4:
        y1 = int(h * layout.search_row_roi_y[0])
        y2 = int(h * layout.search_row_roi_y[1])
    return image[y1:y2, :], y1


def search_row_slice(image):
    h = image.shape[0]
    y1 = int(h * layout.search_row_roi_y[0])
    y2 = int(h * layout.search_row_roi_y[1])
    return image[y1:y2, :], y1


def min_search_row_screen_y():
    rect = get_window_rect()
    if not rect:
        return 0
    _, top, _, height = rect
    return top + int(height * layout.filter_toolbar_roi_y[1]) + 6


def is_search_row_screen_y(y):
    return y >= min_search_row_screen_y()


def _resolve_capture(capture):
    """capture: None | BGR 图像 | (image, ox, oy)"""
    if capture is None:
        return capture_with_offset()
    if isinstance(capture, tuple) and len(capture) == 3:
        return capture
    gs = get_game_screen()
    return capture, gs._ox, gs._oy


def find_search_execute_icon(capture=None):
    """第二行灰色执行放大镜；返回屏幕坐标 match 或 None。"""
    win, ox, oy = _resolve_capture(capture)
    if win is None:
        return None

    h = win.shape[0]
    min_cy = int(h * layout.filter_toolbar_roi_y[1])
    row, row_y1 = search_row_slice(win)
    match = find_image(
        row,
        BTN_SEARCH_EXECUTE,
        threshold=SEARCH_EXECUTE_THRESHOLD,
        min_scale=SEARCH_EXECUTE_MIN_SCALE,
        max_scale=SEARCH_EXECUTE_MAX_SCALE,
        silent=True,
    )
    if not match:
        return None

    (lx, ly), tw, th = match
    if row_y1 + ly + th // 2 < min_cy:
        return None

    return match_in_roi_to_screen(match, ox, oy, row_y1)


def find_search_toggle_icon(capture=None):
    win, ox, oy = _resolve_capture(capture)
    if win is None:
        return None

    row, rx1, row_y1 = filter_toolbar_slice(win)
    match = find_leftmost_image(
        row,
        BTN_SEARCH_EXECUTE,
        threshold=SEARCH_TOGGLE_THRESHOLD,
        min_scale=SEARCH_TOGGLE_MIN_SCALE,
        max_scale=SEARCH_TOGGLE_MAX_SCALE,
        max_rel_x=SEARCH_TOGGLE_MAX_TOOLBAR_X_RATIO,
        silent=True,
    )
    return match_in_roi_to_screen(match, ox, oy, row_y1, rx1)


def find_in_filter_toolbar(template_path, threshold, min_scale, max_scale, capture=None):
    win, ox, oy = _resolve_capture(capture)
    if win is None:
        return None

    row, rx1, row_y1 = filter_toolbar_slice(win)
    match = find_image(
        row,
        template_path,
        threshold=threshold,
        min_scale=min_scale,
        max_scale=max_scale,
        silent=True,
    )
    return match_in_roi_to_screen(match, ox, oy, row_y1, rx1)


def find_filter_sort_button(capture=None):
    return find_in_filter_toolbar(
        BTN_FILTER,
        FILTER_BTN_THRESHOLD,
        0.55,
        1.35,
        capture=capture,
    )


def find_search_box_active():
    """第二行空搜索框占位条；返回屏幕坐标 match 或 None。"""
    win, ox, oy = capture_with_offset()
    if win is None:
        return None
    row, row_y1 = search_input_row_slice(win)
    match = find_image(
        row,
        SEARCH_BOX_ACTIVE,
        threshold=SEARCH_BOX_THRESHOLD,
        min_scale=SEARCH_BOX_MIN_SCALE,
        max_scale=SEARCH_BOX_MAX_SCALE,
        silent=True,
    )
    if not match:
        return None
    _, width, height = match
    if width < SEARCH_BOX_MIN_WIDTH or height < 12:
        return None
    return match_in_roi_to_screen(match, ox, oy, row_y1)


def min_reset_filter_screen_y():
    rect = get_window_rect()
    if not rect:
        return 0
    _, top, _, height = rect
    return top + int(height * layout.filter_toolbar_roi_y[1]) + 10


def is_reset_filter_screen_pos(x, y):
    if y < min_reset_filter_screen_y():
        return False
    rect = get_window_rect()
    if not rect:
        return True
    left, _, width, _ = rect
    return (x - left) / width >= layout.filter_clear_min_x_ratio


def find_filter_clear_match():
    """「重置筛选」模板匹配（执行放大镜下方 ROI）。"""
    win, ox, oy = capture_with_offset()
    if win is None:
        return None

    h, w = win.shape[:2]
    execute = find_search_execute_icon((win, ox, oy))
    if execute:
        ecx, ecy = match_center(execute)
        ex, ey = ecx - ox, ecy - oy
        y1 = min(h - 1, ey + 8)
        y2 = min(h, ey + int(h * 0.10))
        x1 = max(0, ex - 140)
        x2 = min(w, ex + 30)
    else:
        x1 = int(w * layout.filter_clear_roi_x[0])
        x2 = int(w * layout.filter_clear_roi_x[1])
        y1 = int(h * layout.filter_clear_roi_y[0])
        y2 = int(h * layout.filter_clear_roi_y[1])

    if y2 <= y1 + 4 or x2 <= x1 + 4:
        return None

    roi = win[y1:y2, x1:x2]
    match = find_image(
        roi,
        BTN_FILTER_CLEAR,
        threshold=FILTER_CLEAR_THRESHOLD,
        min_scale=FILTER_CLEAR_MIN_SCALE,
        max_scale=FILTER_CLEAR_MAX_SCALE,
        silent=True,
    )
    if not match:
        return None
    (lx, ly), tw, th = match
    cx = lx + x1 + ox + tw // 2
    cy = ly + y1 + oy + th // 2
    if not is_reset_filter_screen_pos(cx, cy):
        return None
    return ((lx + x1 + ox, ly + y1 + oy), tw, th)


def resolve_reset_filter_click():
    """
    解析「重置筛选」点击坐标。
    固定在第二行灰色执行放大镜正下方；优先几何锚点 → 模板 → 窗口比例。
    """
    execute = find_search_execute_icon()
    if execute:
        cx, cy = match_center(execute)
        rect = get_window_rect()
        if rect:
            _, _, _, height = rect
            reset_y = cy + int(height * layout.filter_clear_below_execute_ratio)
            if is_reset_filter_screen_pos(cx, reset_y):
                return cx, reset_y, "执行放大镜下方"

    match = find_filter_clear_match()
    if match:
        cx, cy = match_center(match)
        return cx, cy, "模板"

    rect = get_window_rect()
    if rect:
        left, top, width, height = rect
        x = int(left + width * layout.filter_clear_x_ratio)
        y = int(top + height * layout.filter_clear_y_ratio)
        if is_reset_filter_screen_pos(x, y):
            return x, y, "比例"

    return None, None, None
