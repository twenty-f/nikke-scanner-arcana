"""搜索栏展开、聚焦第二行输入框、点击首位结果。"""

import time

from core.aspect_layout import layout
from core.automation.actions import click_at, load_screen, press_game_key
from core.game_screen import capture_with_offset, click_window_ratio
from core.log_utils import error, step, warn
from core.navigation.screen_state import is_in_warehouse, is_on_character_detail
from core.navigation.warehouse import navigate_to_nikke_warehouse
from core.search.constants import (
    BTN_FILTER,
    BTN_SEARCH_EXECUTE,
    FILTER_BTN_THRESHOLD,
    SEARCH_BOX_ACTIVE,
    SEARCH_BOX_MAX_SCALE,
    SEARCH_BOX_MIN_SCALE,
    SEARCH_BOX_MIN_WIDTH,
    SEARCH_BOX_THRESHOLD,
    SEARCH_EXECUTE_MAX_SCALE,
    SEARCH_EXECUTE_MIN_SCALE,
    SEARCH_EXECUTE_THRESHOLD,
    TEMPLATE_FIND_INTERVAL,
    TEMPLATE_FIND_RETRIES,
)
from core.search.locators import (
    filter_toolbar_slice,
    find_filter_sort_button,
    find_search_box_active,
    find_search_execute_icon,
    find_search_toggle_icon,
    is_search_row_screen_y,
    match_center,
    search_input_row_slice,
)
from core.vision import find_image
from core.window_manager import get_window_rect


def probe_search_panel():
    execute = find_search_execute_icon()
    if execute:
        return find_search_box_active(), True
    return None, False


def is_search_panel_active():
    _, is_open = probe_search_panel()
    return is_open


def wait_for_search_box_active(retries=TEMPLATE_FIND_RETRIES, interval=TEMPLATE_FIND_INTERVAL):
    for attempt in range(retries):
        box, is_open = probe_search_panel()
        if is_open:
            return box if box else True
        if attempt > 0 and attempt % 3 == 0:
            step("SEARCH", f"等待搜索栏 ({attempt + 1}/{retries})")
        if attempt < retries - 1:
            time.sleep(interval)
    return None


def click_search_toggle():
    for attempt in range(3):
        toggle = find_search_toggle_icon()
        if toggle:
            cx, cy = match_center(toggle)
            step("SEARCH", "点击搜索开关")
            click_at(cx, cy, wait_after=0.6)
            return True

        filt = find_filter_sort_button()
        rect = get_window_rect()
        if filt and rect:
            fcx, fcy = match_center(filt)
            _, _, width, _ = rect
            tx = int(fcx - width * layout.search_toggle_left_of_filter_ratio)
            step("SEARCH", "点击搜索开关（战斗力左侧）")
            click_at(tx, fcy, wait_after=0.6)
            return True

        if attempt < 2:
            time.sleep(0.35)

    step("SEARCH", "点击搜索开关（比例回退）")
    return click_window_ratio(
        layout.search_toggle_x_ratio,
        layout.search_toggle_y_ratio,
        wait_after=0.6,
    )


def open_search_panel():
    box, is_open = probe_search_panel()
    if is_open:
        return box if box else True

    if not click_search_toggle():
        warn("SEARCH", "未找到搜索开关")
        return None

    time.sleep(0.8)
    panel = wait_for_search_box_active(retries=8)
    if not panel:
        warn("SEARCH", "搜索框未展开")
    return panel


def focus_search_input(search_box):
    (lx, ly), tw, th = search_box
    input_x = lx + tw // 4
    cy = ly + th // 2
    if not is_search_row_screen_y(cy):
        warn("SEARCH", "搜索框坐标落在第一行，改用地锚聚焦")
        if focus_search_input_for_replace():
            return search_box
        return None
    step("SEARCH", "点击搜索输入框")
    click_at(input_x, cy, wait_after=0.35)
    click_at(input_x, cy, wait_after=0.5)
    return search_box


def focus_search_input_for_replace():
    win, ox, oy = capture_with_offset()
    if win is not None:
        row, row_y1 = search_input_row_slice(win)
        box = find_image(
            row,
            SEARCH_BOX_ACTIVE,
            threshold=SEARCH_BOX_THRESHOLD,
            min_scale=SEARCH_BOX_MIN_SCALE,
            max_scale=SEARCH_BOX_MAX_SCALE,
            silent=True,
        )
        if box:
            (lx, ly), tw, th = box
            x = ox + lx + tw // 4
            y = oy + row_y1 + ly + th // 2
            if is_search_row_screen_y(y):
                step("SEARCH", "点击搜索输入框")
                click_at(x, y, wait_after=0.35)
                click_at(x, y, wait_after=0.5)
                return True

        execute = find_image(
            row,
            BTN_SEARCH_EXECUTE,
            threshold=SEARCH_EXECUTE_THRESHOLD,
            min_scale=SEARCH_EXECUTE_MIN_SCALE,
            max_scale=SEARCH_EXECUTE_MAX_SCALE,
            silent=True,
        )
        if execute:
            (lx, ly), tw, th = execute
            icx = lx + tw // 2
            icy = ly + th // 2
            w = win.shape[1]
            offset = int(w * layout.search_input_left_of_execute_ratio)
            x = ox + max(int(w * 0.20), icx - offset)
            y = oy + row_y1 + icy
            if is_search_row_screen_y(y):
                step("SEARCH", "点击搜索输入框（执行按钮左侧）")
                click_at(x, y, wait_after=0.35)
                click_at(x, y, wait_after=0.5)
                return True

    rect = get_window_rect()
    if rect:
        left, top, width, height = rect
        x = int(left + width * layout.search_input_x_ratio)
        y = int(top + height * layout.search_input_y_ratio)
        if is_search_row_screen_y(y):
            step("SEARCH", "点击搜索输入框（比例）")
            click_at(x, y, wait_after=0.35)
            click_at(x, y, wait_after=0.5)
            return True
    return False


def focus_search_input_when_open(search_box=None):
    if focus_search_input_for_replace():
        return search_box if search_box and search_box is not True else None
    if search_box and search_box is not True:
        return focus_search_input(search_box)
    if click_window_ratio(layout.search_input_x_ratio, layout.search_input_y_ratio, wait_after=0.5):
        return None
    return None


def ensure_ready_for_search():
    if is_search_panel_active():
        return True
    if is_in_warehouse():
        return True
    if is_on_character_detail():
        step("SEARCH", "当前在详情页，ESC 退回")
        return return_to_search_list_after_scan()
    step("SEARCH", "不在仓库，重新导航")
    return navigate_to_nikke_warehouse()


def activate_search_input(replace_mode=False):
    if not ensure_ready_for_search():
        error("SEARCH", "仓库未就绪，无法搜索")
        return None, False

    search_box, is_open = probe_search_panel()
    if is_open:
        step("SEARCH", "搜索框已激活" if search_box else "搜索栏已展开")
        return focus_search_input_when_open(search_box), True

    if replace_mode:
        step("SEARCH", "聚焦搜索栏（替换名字）")
        if focus_search_input_for_replace():
            return None, True
        error("SEARCH", "无法聚焦搜索栏（跳过蓝色开关以免收起搜索）")
        return None, False

    panel = open_search_panel()
    if panel:
        step("SEARCH", "搜索框已激活" if panel is not True else "搜索栏已展开")
        anchor = focus_search_input_when_open(None if panel is True else panel)
        return anchor, True

    error("SEARCH", "搜索框未激活")
    return None, False


def resolve_list_anchor_position(cached_match=None):
    if cached_match and isinstance(cached_match, tuple):
        cx, cy = match_center(cached_match)
        return cx, cy, "步骤A缓存搜索框"

    fresh = wait_for_search_box_active(retries=3)
    if fresh and fresh is not True:
        cx, cy = match_center(fresh)
        return cx, cy, "实时搜索框"

    execute = find_search_execute_icon()
    if execute:
        cx, cy = match_center(execute)
        rect = get_window_rect()
        if rect:
            left, _, width, _ = rect
            return int(left + width * layout.search_input_x_ratio), cy, "搜索输入比例"
        win, ox, oy = capture_with_offset()
        if win is not None:
            offset = int(win.shape[1] * layout.search_input_left_of_execute_ratio)
            return cx - offset, cy, "执行按钮左侧"

    win, ox, oy = capture_with_offset()
    if win is not None:
        h, w = win.shape[:2]
        header_roi = win[: int(h * layout.search_box_roi_height_ratio), :]
        filter_btn = find_image(
            header_roi,
            BTN_FILTER,
            threshold=0.75,
            min_scale=0.55,
            max_scale=1.35,
            silent=True,
        )
        if filter_btn:
            cx, cy = match_center(filter_btn)
            return ox + cx, oy + cy + 30, "筛选按钮下方"

    return None, None, None


def compute_first_result_position(cached_match=None):
    rect = get_window_rect()
    if rect:
        left, top, width, height = rect
        target_x = int(left + width * layout.first_result_col_x_ratio)
        target_y = int(top + height * layout.first_result_row_y_ratio)
        return (
            target_x,
            target_y,
            f"窗口比例 ({layout.first_result_col_x_ratio:.0%}W, {layout.first_result_row_y_ratio:.0%}H) "
            f"[{width}x{height}]",
        )

    win, ox, oy = capture_with_offset()
    if win is not None:
        sh, sw = win.shape[:2]
        return (
            int(ox + sw * layout.first_result_col_x_ratio),
            int(oy + sh * layout.first_result_row_y_ratio),
            f"窗口截图比例 ({layout.first_result_col_x_ratio:.0%}W, {layout.first_result_row_y_ratio:.0%}H)",
        )

    anchor_x, anchor_y, source = resolve_list_anchor_position(cached_match)
    if anchor_y is None:
        return None, None, None

    return (
        int(anchor_x * 0.25),
        int(anchor_y * 1.15),
        f"{source}+弱回退",
    )


def click_first_search_result(cached_match=None):
    target_x, target_y, _source = compute_first_result_position(cached_match)
    if target_x is None:
        return False
    click_at(target_x, target_y, wait_after=2.5)
    return True


def return_to_search_list_after_scan():
    time.sleep(0.4)

    if is_search_panel_active():
        step("SEARCH", "已在搜索界面")
        return True

    if is_in_warehouse():
        step("SEARCH", "已在仓库列表")
        return True

    if is_on_character_detail():
        press_game_key("esc", wait_after=1.0)
        if is_search_panel_active():
            step("SEARCH", "退回搜索列表")
            return True
        if is_in_warehouse():
            step("SEARCH", "退回仓库列表")
            return True
        warn("SEARCH", "详情页 ESC 后未回到搜索/仓库")
        return False

    warn("SEARCH", "当前界面未知")
    return False
