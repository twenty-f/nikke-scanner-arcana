import os
import time

import cv2
import numpy as np
import pydirectinput
import pyperclip

from core.aspect_layout import configure_layout_from_window, layout
from core.bot_client import ArcanaAuthError, print_user_stat_summary
from core.capture import get_screen
from core.equipment_scanner import scan_current_character_equipment
from core.log_utils import error, info, step, warn
from core.scan_session import abort_scan, begin_scan, finish_scan, mark_character_done, mark_progress, set_scan_phase
from core.vision import find_image
from core.window_manager import force_bring_to_front, get_window_rect

# UI 特征图路径
BTN_NIKKE = "assets/ui/btn_nikke.png"
QUIT_GAME_CONFIRM = "assets/ui/quit_game_confirm.png"
# 第二行右侧灰色放大镜（执行搜索）；第一行蓝色开关无单独模板，用比例点击
BTN_SEARCH_EXECUTE = "assets/ui/btn_search_icon.png"
SEARCH_BOX_ACTIVE = "assets/ui/search_box_active.png"
BTN_FILTER = "assets/ui/btn_filter.png"
BTN_FILTER_CLEAR = "assets/ui/btn_filter_clear.png"

# 搜索流程偏移量（输入框/清除按钮仍用相对搜索框模板的小偏移）
SEARCH_INPUT_OFFSET_X = -80
SEARCH_CLEAR_OFFSET_X = 60

# 退出确认框严格检测参数（过滤 0.2x 等小尺度误匹配）
QUIT_CONFIRM_THRESHOLD = 0.88
QUIT_CONFIRM_MIN_SCALE = 0.55
QUIT_CONFIRM_MAX_SCALE = 1.35

# 搜索框严格检测（限第二行 ROI，过滤小尺度误匹配）
SEARCH_BOX_THRESHOLD = 0.70
SEARCH_BOX_MIN_SCALE = 0.55
SEARCH_BOX_MAX_SCALE = 1.35
SEARCH_BOX_MIN_WIDTH = 80
# 第二行灰色执行放大镜
SEARCH_EXECUTE_THRESHOLD = 0.62
SEARCH_EXECUTE_MIN_SCALE = 0.55
SEARCH_EXECUTE_MAX_SCALE = 1.35
# 第一行搜索开关（与执行按钮同图标，限 filter_toolbar ROI）
SEARCH_TOGGLE_THRESHOLD = 0.55
SEARCH_TOGGLE_MIN_SCALE = 0.55
SEARCH_TOGGLE_MAX_SCALE = 1.35
# 武器筛选面板内匹配
WEAPON_FILTER_THRESHOLD = 0.78
WEAPON_FILTER_MIN_SCALE = 0.55
WEAPON_FILTER_MAX_SCALE = 1.35
FILTER_BTN_THRESHOLD = 0.78
FILTER_CLEAR_THRESHOLD = 0.72
FILTER_CLEAR_MIN_SCALE = 0.55
FILTER_CLEAR_MAX_SCALE = 1.35
MAX_ESC_WASH = 40
TEMPLATE_FIND_RETRIES = 8
TEMPLATE_FIND_INTERVAL = 0.8
# 导航阶段专用：更短轮询，加快启动与 ESC 洗地
NAV_TEMPLATE_RETRIES = 5
NAV_TEMPLATE_INTERVAL = 0.35
ESC_WASH_INTERVAL = 0.65
LOBBY_READY_INTERVAL = 0.35
LOBBY_READY_SETTLE = 0.35
WAREHOUSE_LOAD_INTERVAL = 0.55
WAREHOUSE_CLICK_SETTLE = 2.0

# 上一位干员搜索成功后，搜索栏保持展开；下一位只点输入框，不点放大镜
_list_search_active = False


def _load_screen():
    """将 get_screen 返回值解码为 OpenCV 图像。"""
    screen_raw = get_screen()
    if isinstance(screen_raw, str):
        if not os.path.exists(screen_raw):
            return None
        return cv2.imdecode(np.fromfile(screen_raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    return screen_raw


def _match_center(match):
    """将 find_image 返回值转换为中心坐标 (cx, cy)。"""
    loc, width, height = match
    return loc[0] + width // 2, loc[1] + height // 2


def _wait_for_template(template_path, threshold=0.75, retries=TEMPLATE_FIND_RETRIES, interval=TEMPLATE_FIND_INTERVAL):
    """轮询截屏，直到找到模板或超时。"""
    for attempt in range(retries):
        screen = _load_screen()
        if screen is None:
            time.sleep(interval)
            continue

        match = find_image(screen, template_path, threshold=threshold, show_result=False)
        if match:
            return match

        if attempt < retries - 1:
            time.sleep(interval)
    return None


def _click_at(x, y, wait_after=0.5):
    """移动并点击指定坐标。"""
    pydirectinput.moveTo(int(x), int(y))
    time.sleep(0.15)
    pydirectinput.click()
    time.sleep(wait_after)


def _click_template(template_path, threshold=0.75, offset_x=0, offset_y=0, retries=TEMPLATE_FIND_RETRIES):
    """寻找模板并点击其中心（可附加偏移）。"""
    match = _wait_for_template(template_path, threshold=threshold, retries=retries)
    if not match:
        return False

    cx, cy = _match_center(match)
    _click_at(cx + offset_x, cy + offset_y)
    return True


def _parse_char_name(char_name):
    """解析 char_name，支持「角色名|武器类型」格式。"""
    if "|" in char_name:
        search_name, weapon_type = char_name.rsplit("|", 1)
        return search_name.strip(), weapon_type.strip().upper()
    return char_name.strip(), None


def _paste_from_clipboard(text):
    """通过剪贴板注入中文；先全选再粘贴，确保输入框已获得焦点。"""
    pyperclip.copy(text)
    time.sleep(0.2)
    pydirectinput.keyDown("ctrl")
    pydirectinput.press("a")
    time.sleep(0.05)
    pydirectinput.press("v")
    pydirectinput.keyUp("ctrl")
    time.sleep(0.3)


def _filter_toolbar_slice(image):
    """第一行居中筛选栏 ROI（搜索开关 / Burst / 战斗力）。"""
    h, w = image.shape[:2]
    x1 = int(w * layout.filter_toolbar_roi_x[0])
    x2 = int(w * layout.filter_toolbar_roi_x[1])
    y1 = int(h * layout.filter_toolbar_roi_y[0])
    y2 = int(h * layout.filter_toolbar_roi_y[1])
    return image[y1:y2, x1:x2], x1, y1


def _search_input_row_slice(image):
    """第二行输入区 ROI（严格在筛选栏下方，避免与开关放大镜混淆）。"""
    h = image.shape[0]
    y1 = int(h * layout.filter_toolbar_roi_y[1])
    y2 = int(h * layout.search_row_roi_y[1])
    if y2 <= y1 + 4:
        y1 = int(h * layout.search_row_roi_y[0])
        y2 = int(h * layout.search_row_roi_y[1])
    return image[y1:y2, :], y1


def _search_row_slice(image):
    """第二行搜索栏 ROI：输入框 + 右侧灰色执行放大镜。"""
    h = image.shape[0]
    y1 = int(h * layout.search_row_roi_y[0])
    y2 = int(h * layout.search_row_roi_y[1])
    return image[y1:y2, :], y1


def _match_in_roi_to_screen(match, ox, oy, roi_y1, roi_x1=0):
    if not match:
        return None
    (lx, ly), tw, th = match
    return ((lx + roi_x1 + ox, ly + roi_y1 + oy), tw, th)


def _find_in_filter_toolbar(template_path, threshold, min_scale, max_scale, screen=None):
    if screen is None:
        win, ox, oy = _get_game_window_screen()
    else:
        win, ox, oy = screen, 0, 0
    if win is None:
        return None

    row, rx1, row_y1 = _filter_toolbar_slice(win)
    match = find_image(
        row,
        template_path,
        threshold=threshold,
        min_scale=min_scale,
        max_scale=max_scale,
        silent=True,
    )
    return _match_in_roi_to_screen(match, ox, oy, row_y1, rx1)


def _find_search_toggle_icon(screen=None):
    """第一行筛选栏最左侧搜索开关（与第二行执行按钮区分 ROI）。"""
    return _find_in_filter_toolbar(
        BTN_SEARCH_EXECUTE,
        SEARCH_TOGGLE_THRESHOLD,
        SEARCH_TOGGLE_MIN_SCALE,
        SEARCH_TOGGLE_MAX_SCALE,
        screen=screen,
    )


def _find_filter_sort_button(screen=None):
    """第一行「战斗力」排序下拉（用作搜索开关水平锚点）。"""
    return _find_in_filter_toolbar(
        BTN_FILTER,
        FILTER_BTN_THRESHOLD,
        0.55,
        1.35,
        screen=screen,
    )


def _match_in_row_to_screen(match, ox, oy, row_y1, row_x1=0):
    return _match_in_roi_to_screen(match, ox, oy, row_y1, row_x1)


def _find_search_box_active(screen=None):
    """在第二行输入区 ROI 内匹配空搜索框占位条。"""
    if screen is None:
        win, ox, oy = _get_game_window_screen()
        if win is None:
            return None
        row, row_y1 = _search_input_row_slice(win)
        match = find_image(
            row,
            SEARCH_BOX_ACTIVE,
            threshold=SEARCH_BOX_THRESHOLD,
            min_scale=SEARCH_BOX_MIN_SCALE,
            max_scale=SEARCH_BOX_MAX_SCALE,
            silent=True,
        )
        return _match_in_row_to_screen(match, ox, oy, row_y1)

    row, row_y1 = _search_input_row_slice(screen)
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
    (lx, ly), tw, th = match
    return ((lx, row_y1 + ly), tw, th)


def _wait_for_search_box_active(retries=TEMPLATE_FIND_RETRIES, interval=TEMPLATE_FIND_INTERVAL):
    """轮询直至搜索栏展开（占位条 / 执行按钮 / 双放大镜）。"""
    for attempt in range(retries):
        screen = _load_screen()
        box, is_open = _probe_search_panel(screen)
        if is_open:
            return box if box else True
        if attempt > 0 and attempt % 3 == 0:
            step("SEARCH", f"等待搜索栏 ({attempt + 1}/{retries})")
        if attempt < retries - 1:
            time.sleep(interval)
    return None


def _probe_search_panel(screen=None):
    """返回 (搜索框模板或 None, 是否已展开)。展开以输入区执行按钮为准。"""
    if screen is None:
        screen = _load_screen()
    if screen is None:
        return None, False

    execute = _find_search_execute_icon(screen)
    if execute:
        return _find_search_box_active(screen), True

    return None, False


def _focus_search_input_when_open(search_box=None):
    """搜索栏已确认展开时聚焦输入框。"""
    if search_box and search_box is not True:
        return _focus_search_input(search_box)
    if _focus_search_input_for_replace():
        return None
    if _click_window_ratio(layout.search_input_x_ratio, layout.search_input_y_ratio, wait_after=0.5):
        return None
    return None


def _get_game_window_screen():
    """裁剪游戏客户端区域，返回 (图像, 屏幕偏移 ox, oy)。"""
    screen = _load_screen()
    rect = get_window_rect()
    if screen is None or not rect:
        return screen, 0, 0

    left, top, width, height = rect
    sh, sw = screen.shape[:2]
    x1 = max(0, min(left, sw))
    y1 = max(0, min(top, sh))
    x2 = max(x1, min(left + width, sw))
    y2 = max(y1, min(top + height, sh))
    if x2 <= x1 or y2 <= y1:
        return screen, 0, 0
    return screen[y1:y2, x1:x2], x1, y1


def _click_window_ratio(x_ratio, y_ratio, wait_after=0.5):
    rect = get_window_rect()
    if not rect:
        return False
    left, top, width, height = rect
    _click_at(int(left + width * x_ratio), int(top + height * y_ratio), wait_after=wait_after)
    return True


def _find_search_execute_icon(screen=None):
    """在筛选栏下方输入区匹配灰色执行放大镜（排除第一行开关）。"""
    if screen is None:
        win, ox, oy = _get_game_window_screen()
    else:
        win, ox, oy = screen, 0, 0
    if win is None:
        return None

    h = win.shape[0]
    min_cy = int(h * layout.filter_toolbar_roi_y[1])
    row, row_y1 = _search_row_slice(win)
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

    return _match_in_row_to_screen(match, ox, oy, row_y1)


def _click_search_toggle():
    """点击第一行居中筛选栏最左侧搜索开关，展开第二行搜索栏。"""
    for attempt in range(3):
        toggle = _find_search_toggle_icon()
        if toggle:
            cx, cy = _match_center(toggle)
            step("SEARCH", "点击搜索开关")
            _click_at(cx, cy, wait_after=0.6)
            return True

        filt = _find_filter_sort_button()
        rect = get_window_rect()
        if filt and rect:
            fcx, fcy = _match_center(filt)
            _, _, width, _ = rect
            tx = int(fcx - width * layout.search_toggle_left_of_filter_ratio)
            step("SEARCH", "点击搜索开关（战斗力左侧）")
            _click_at(tx, fcy, wait_after=0.6)
            return True

        if attempt < 2:
            time.sleep(0.35)

    step("SEARCH", "点击搜索开关（比例回退）")
    return _click_window_ratio(
        layout.search_toggle_x_ratio,
        layout.search_toggle_y_ratio,
        wait_after=0.6,
    )


def _is_search_row_visible():
    """第二行搜索栏是否可见。"""
    _, is_open = _probe_search_panel(_load_screen())
    return is_open


def _focus_search_input_for_replace():
    """
    搜索栏已展开且含文字：在第二行定位输入框。
    优先空框模板 → 灰色执行按钮左侧 → 窗口比例。
    """
    win, ox, oy = _get_game_window_screen()
    if win is not None:
        row, row_y1 = _search_input_row_slice(win)
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
            _click_at(x, y, wait_after=0.35)
            _click_at(x, y, wait_after=0.5)
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
            icx, icy = _match_center(execute)
            w = win.shape[1]
            offset = int(w * layout.search_input_left_of_execute_ratio)
            x = ox + max(int(w * 0.20), icx - offset)
            y = oy + row_y1 + icy
            _click_at(x, y, wait_after=0.35)
            _click_at(x, y, wait_after=0.5)
            return True

    if not _click_window_ratio(layout.search_input_x_ratio, layout.search_input_y_ratio, wait_after=0.35):
        return False
    return _click_window_ratio(layout.search_input_x_ratio, layout.search_input_y_ratio, wait_after=0.5)


def _focus_search_input_by_ratio():
    """按窗口比例聚焦搜索输入框（与 replace 模式共用坐标）。"""
    return _focus_search_input_for_replace()


def _is_search_bar_expanded():
    """第二行搜索栏是否可见（空框或灰色执行按钮）。"""
    return _is_search_row_visible()


def _is_search_panel_active():
    return _is_search_bar_expanded()


def _activate_search_input(replace_mode=False):
    """
    打开搜索面板并激活输入框。返回 (锚点或 None, 是否成功)。
    replace_mode=True：搜索栏已展开，只点第二行输入框替换名字，禁止点蓝色开关。
    replace_mode=False：首次搜索，点第一行蓝色开关展开空搜索框。
    """
    if not _ensure_ready_for_search():
        error("SEARCH", "仓库未就绪，无法搜索")
        return None, False

    screen = _load_screen()
    search_box, is_open = _probe_search_panel(screen)
    if is_open:
        step("SEARCH", "搜索框已激活" if search_box else "搜索栏已展开")
        return _focus_search_input_when_open(search_box), True

    if replace_mode:
        step("SEARCH", "聚焦搜索栏（替换名字）")
        if _focus_search_input_for_replace():
            return None, True
        error("SEARCH", "无法聚焦搜索栏（跳过蓝色开关以免收起搜索）")
        return None, False

    panel = _open_search_panel()
    if panel:
        step("SEARCH", "搜索框已激活" if panel is not True else "搜索栏已展开")
        anchor = _focus_search_input_when_open(None if panel is True else panel)
        return anchor, True

    error("SEARCH", "搜索框未激活")
    return None, False


def _resolve_list_anchor_position(cached_match=None):
    """
    解析首位盲点用的锚点坐标。
    武器筛选后 search_box_active 可能无法再次匹配，优先复用步骤 A 缓存。
    """
    if cached_match and isinstance(cached_match, tuple):
        cx, cy = _match_center(cached_match)
        return cx, cy, "步骤A缓存搜索框"

    fresh = _wait_for_search_box_active(retries=3)
    if fresh and fresh is not True:
        cx, cy = _match_center(fresh)
        return cx, cy, "实时搜索框"

    screen = _load_screen()
    if screen is None:
        return None, None, None

    h = screen.shape[0]
    header_roi = screen[: int(h * layout.search_box_roi_height_ratio), :]

    filter_btn = find_image(
        header_roi,
        BTN_FILTER,
        threshold=0.75,
        min_scale=0.55,
        max_scale=1.35,
        silent=True,
    )
    if filter_btn:
        cx, cy = _match_center(filter_btn)
        return cx, cy + 30, "筛选按钮下方"

    execute = _find_search_execute_icon(screen)
    if execute:
        cx, cy = _match_center(execute)
        rect = get_window_rect()
        if rect:
            left, _, width, _ = rect
            return int(left + width * layout.search_input_x_ratio), cy, "搜索输入比例"
        return cx - int(screen.shape[1] * layout.search_input_left_of_execute_ratio), cy, "执行按钮左侧"

    return None, None, None


def _compute_first_result_position(cached_match=None):
    """
    计算首位干员盲点坐标（全程使用窗口/屏幕比例，不用固定像素）。
    妮姬列表左对齐：筛选后即使只剩 1 人，卡片仍在【最左列】。
    """
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

    screen = _load_screen()
    if screen is not None:
        sh, sw = screen.shape[:2]
        target_x = int(sw * layout.first_result_col_x_ratio)
        target_y = int(sh * layout.first_result_row_y_ratio)
        return (
            target_x,
            target_y,
            f"全屏比例 ({layout.first_result_col_x_ratio:.0%}W, {layout.first_result_row_y_ratio:.0%}H)",
        )

    _anchor_x, anchor_y, source = _resolve_list_anchor_position(cached_match)
    if anchor_y is None:
        return None, None, None

    return (
        int(_anchor_x * 0.25),
        int(anchor_y * 1.15),
        f"{source}+弱回退",
    )


def _click_first_search_result(cached_match=None):
    """点击搜索/筛选结果网格最左列首位干员（单人结果亦在左侧）。"""
    target_x, target_y, source = _compute_first_result_position(cached_match)
    if target_x is None:
        return False

    _click_at(target_x, target_y, wait_after=2.5)
    return True


def _is_filter_toolbar_visible(screen):
    """第一行筛选工具栏是否可见（搜索栏收起时仍可用于判定仓库页）。"""
    header = _search_header_roi(screen)
    return bool(
        find_image(
            header,
            BTN_FILTER,
            threshold=FILTER_BTN_THRESHOLD,
            min_scale=0.55,
            max_scale=1.35,
            silent=True,
        )
    )


def _is_in_warehouse():
    """检测是否已在妮姬仓库列表（非角色详情页，且顶部筛选/搜索区可见）。"""
    screen = _load_screen()
    if screen is None:
        return False

    h, w = screen.shape[:2]
    roi = screen[:, int(w * layout.detail_roi_x_start):]
    top = find_image(roi, "assets/anchor_top.png", threshold=0.80, silent=True)
    bottom = find_image(roi, "assets/anchor_bottom.png", threshold=0.80, silent=True)
    if top and bottom:
        return False

    if _is_search_row_visible():
        return True
    return _is_filter_toolbar_visible(screen)


def _find_quit_confirm(screen):
    """严格检测退出确认框，排除小尺度误匹配。"""
    return find_image(
        screen,
        QUIT_GAME_CONFIRM,
        threshold=QUIT_CONFIRM_THRESHOLD,
        min_scale=QUIT_CONFIRM_MIN_SCALE,
        max_scale=QUIT_CONFIRM_MAX_SCALE,
        silent=True,
    )


def _find_lobby_nikke_btn(screen):
    """在大厅下半区寻找妮姬入口按钮。"""
    if screen is None:
        return None
    h = screen.shape[0]
    roi_y_offset = int(h * layout.lobby_roi_y_start)
    return find_image(screen[roi_y_offset:, :], BTN_NIKKE, threshold=0.60, silent=True)


def _is_quit_confirm_visible():
    """严格检测退出确认框是否仍在屏幕上。"""
    screen = _load_screen()
    if screen is None:
        return False
    return bool(_find_quit_confirm(screen))


def _is_lobby_ready():
    """大厅就绪：妮姬入口可见，且严格模式下无退出确认框。"""
    screen = _load_screen()
    if screen is None:
        return False
    if _find_quit_confirm(screen):
        return False
    return bool(_find_lobby_nikke_btn(screen))


def _wait_until_lobby_ready(max_wait_sec=8, interval=LOBBY_READY_INTERVAL):
    """
    等待大厅可操作：优先以【妮姬入口可见 + 无真实确认框】为准，
    避免 0.2x 误匹配导致无限等待。
    """
    deadline = time.time() + max_wait_sec
    while time.time() < deadline:
        if _is_lobby_ready():
            time.sleep(LOBBY_READY_SETTLE)
            return True

        screen = _load_screen()
        if screen is not None and _find_lobby_nikke_btn(screen) and not _find_quit_confirm(screen):
            time.sleep(LOBBY_READY_SETTLE)
            return True

        time.sleep(interval)

    error("NAV", "大厅就绪超时")
    return False


def _dismiss_quit_confirm_and_wait():
    pydirectinput.press("esc")
    time.sleep(0.6)

    if _is_quit_confirm_visible():
        pydirectinput.press("esc")
        time.sleep(0.6)

    return _wait_until_lobby_ready()


def _enter_nikke_warehouse_from_lobby():
    if not _is_lobby_ready() and not _wait_until_lobby_ready():
        return False

    btn_info = None
    screen = None

    for attempt in range(4):
        screen = _load_screen()
        if screen is None:
            time.sleep(NAV_TEMPLATE_INTERVAL)
            continue

        btn_info = _find_lobby_nikke_btn(screen)
        if btn_info and not _find_quit_confirm(screen):
            break

        if attempt < 3:
            time.sleep(NAV_TEMPLATE_INTERVAL)

    if not btn_info or screen is None:
        error("NAV", "未找到妮姬入口")
        return False

    h = screen.shape[0]
    roi_y_offset = int(h * layout.lobby_roi_y_start)
    target_x = btn_info[0][0] + btn_info[1] // 2
    target_y = btn_info[0][1] + btn_info[2] // 2 + roi_y_offset
    _click_at(target_x, target_y, wait_after=WAREHOUSE_CLICK_SETTLE)

    for attempt in range(8):
        if _is_in_warehouse():
            step("NAV", "已进入妮姬仓库")
            return True
        if attempt < 7:
            time.sleep(WAREHOUSE_LOAD_INTERVAL)

    error("NAV", "进入仓库失败")
    return False


def navigate_to_nikke_warehouse():
    if _is_in_warehouse():
        step("NAV", "已在仓库，跳过导航")
        return True

    if _is_lobby_ready():
        step("NAV", "大厅 -> 仓库")
        return _enter_nikke_warehouse_from_lobby()

    step("NAV", "ESC 洗地中")

    esc_count = 0
    while True:
        pydirectinput.press("esc")
        time.sleep(ESC_WASH_INTERVAL)
        esc_count += 1

        screen = _load_screen()
        if screen is None:
            if esc_count >= MAX_ESC_WASH:
                error("NAV", "洗地后仍无法截屏")
                return False
            continue

        if _find_quit_confirm(screen):
            step("NAV", "关闭退出确认框")
            if not _dismiss_quit_confirm_and_wait():
                return False
            return _enter_nikke_warehouse_from_lobby()

        if _is_in_warehouse():
            step("NAV", f"洗地 {esc_count} 次后进入仓库")
            return True

        if _is_lobby_ready():
            step("NAV", f"洗地 {esc_count} 次后到达大厅")
            return _enter_nikke_warehouse_from_lobby()

        if esc_count >= MAX_ESC_WASH:
            error("NAV", "洗地超时")
            return False

        if esc_count % 3 == 0:
            step("NAV", f"洗地 {esc_count}/{MAX_ESC_WASH}")


def _is_on_character_detail():
    """是否在角色装备详情页（双锚点可见，且不在仓库列表）。"""
    if _is_in_warehouse():
        return False

    screen = _load_screen()
    if screen is None:
        return False

    h, w = screen.shape[:2]
    roi = screen[:, int(w * layout.detail_roi_x_start):]
    top = find_image(roi, "assets/anchor_top.png", threshold=0.80, silent=True)
    bottom = find_image(roi, "assets/anchor_bottom.png", threshold=0.80, silent=True)
    return bool(top and bottom)


def _return_to_search_list_after_scan():
    """
    扫描完成后退回搜索/列表界面。
    搜索 UI 上按 ESC 会回大厅，因此最多从详情页按 1 次 ESC。
    """
    time.sleep(0.4)

    if _is_search_panel_active():
        step("SEARCH", "已在搜索界面")
        return True

    if _is_in_warehouse():
        step("SEARCH", "已在仓库列表")
        return True

    if _is_on_character_detail():
        pydirectinput.press("esc")
        time.sleep(1.0)
        if _is_search_panel_active():
            step("SEARCH", "退回搜索列表")
            return True
        if _is_in_warehouse():
            step("SEARCH", "退回仓库列表")
            return True
        warn("SEARCH", "详情页 ESC 后未回到搜索/仓库")
        return False

    warn("SEARCH", "当前界面未知")
    return False


def _find_filter_clear_match():
    """在搜索栏下方区域匹配「重置筛选」按钮（仅游戏窗口内）。"""
    win, ox, oy = _get_game_window_screen()
    if win is None:
        return None

    h, w = win.shape[:2]
    x1 = int(w * layout.filter_clear_roi_x[0])
    x2 = int(w * layout.filter_clear_roi_x[1])
    y1 = int(h * layout.filter_clear_roi_y[0])
    y2 = int(h * layout.filter_clear_roi_y[1])
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
    return ((lx + x1 + ox, ly + y1 + oy), tw, th)


def _reset_weapon_filter_on_search_ui():
    """在搜索界面直接点击「重置筛选」，不使用 ESC。"""
    match = _find_filter_clear_match()
    if match:
        cx, cy = _match_center(match)
        _click_at(cx, cy, wait_after=0.8)
        step("SEARCH", "重置武器筛选")
        time.sleep(1.0)
        return True

    if _click_window_ratio(layout.filter_clear_x_ratio, layout.filter_clear_y_ratio, wait_after=0.8):
        step("SEARCH", "重置筛选（比例回退）")
        time.sleep(1.0)
        return True

    warn("SEARCH", "未找到重置筛选按钮")
    return False


def _prepare_search_for_next_character(used_weapon_filter):
    """
    一位干员完成后准备下一位：
    - 保持搜索栏展开，不清空、不收起（下一位直接改名字）
    - 若上一位用了枪种筛选，点「重置筛选」
    """
    if not _return_to_search_list_after_scan():
        warn("SEARCH", "未能回到搜索/仓库，尝试重导航")
        if not navigate_to_nikke_warehouse():
            return False

    if used_weapon_filter:
        _reset_weapon_filter_on_search_ui()

    step("SEARCH", "搜索界面已就绪")
    return True


def _ensure_ready_for_search():
    """搜索前确保位于可搜索状态（搜索栏展开或仓库列表）。"""
    if _is_search_panel_active():
        return True

    if _is_in_warehouse():
        return True

    if _is_on_character_detail():
        step("SEARCH", "当前在详情页，ESC 退回")
        return _return_to_search_list_after_scan()

    step("SEARCH", "不在仓库，重新导航")
    return navigate_to_nikke_warehouse()


def _return_to_warehouse_list():
    """退回仓库/搜索列表；仅在无法恢复时才重导航。"""
    if _return_to_search_list_after_scan():
        return True

    warn("SEARCH", "退回失败，重导航")
    return navigate_to_nikke_warehouse()


def _ensure_warehouse_list(max_esc=4):
    return _return_to_warehouse_list()


def _open_search_panel():
    screen = _load_screen()
    box, is_open = _probe_search_panel(screen)
    if is_open:
        return box if box else True

    if not _click_search_toggle():
        warn("SEARCH", "未找到搜索开关")
        return None

    time.sleep(0.8)
    panel = _wait_for_search_box_active(retries=8)
    if not panel:
        warn("SEARCH", "搜索框未展开")
    return panel


def _focus_search_input(search_box):
    (lx, ly), tw, th = search_box
    input_x = lx + tw // 4
    cy = ly + th // 2
    _click_at(input_x, cy, wait_after=0.35)
    _click_at(input_x, cy, wait_after=0.5)
    return search_box


def _clear_search_input_text(search_box):
    cx, cy = _match_center(search_box)
    clear_x = cx + SEARCH_CLEAR_OFFSET_X
    _click_at(clear_x, cy, wait_after=0.6)

    input_x = cx + SEARCH_INPUT_OFFSET_X
    _click_at(input_x, cy, wait_after=0.3)
    pyperclip.copy("")
    pydirectinput.keyDown("ctrl")
    pydirectinput.press("a")
    time.sleep(0.05)
    pydirectinput.press("v")
    pydirectinput.keyUp("ctrl")
    time.sleep(0.2)
    pydirectinput.press("enter")
    time.sleep(1.0)


def _collapse_search_panel():
    """收起搜索面板，使下一位干员从统一初始态启动。"""
    if _find_search_box_active(_load_screen()):
        pydirectinput.press("esc")
        time.sleep(0.8)


def _reset_name_search():
    return _prepare_search_for_next_character(used_weapon_filter=False)


def _clear_search_box():
    """兼容旧调用。"""
    return _reset_name_search()


def _search_header_roi(screen):
    """第一行筛选工具栏 ROI（Burst / 筛选 / 战斗力等）。"""
    row, _, _ = _filter_toolbar_slice(screen)
    return row


def _filter_panel_slice(screen):
    """筛选弹窗 ROI（武器类型按钮仅在此区域内匹配）。"""
    if screen is None:
        return None, 0, 0
    h, w = screen.shape[:2]
    x1 = int(w * layout.filter_panel_roi_x[0])
    x2 = int(w * layout.filter_panel_roi_x[1])
    y1 = int(h * layout.filter_panel_roi_y[0])
    y2 = int(h * layout.filter_panel_roi_y[1])
    return screen[y1:y2, x1:x2], x1, y1


def _click_template_in_roi(roi, roi_x1, roi_y1, template_path, threshold=0.75, min_scale=0.55, max_scale=1.35):
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
    cx, cy = _match_center(match)
    _click_at(cx + roi_x1, cy + roi_y1)
    return True


def _click_filter_entry():
    """点击顶部筛选入口（限第一行 filter_toolbar ROI）。"""
    screen = _load_screen()
    if screen is None:
        return False
    header = _search_header_roi(screen)
    match = find_image(
        header,
        BTN_FILTER,
        threshold=FILTER_BTN_THRESHOLD,
        min_scale=0.55,
        max_scale=1.35,
        silent=True,
    )
    if not match:
        return False
    h, w = screen.shape[:2]
    rx1 = int(w * layout.filter_toolbar_roi_x[0])
    ry1 = int(h * layout.filter_toolbar_roi_y[0])
    cx, cy = _match_center(match)
    _click_at(cx + rx1, cy + ry1, wait_after=0.6)
    return True


def _apply_weapon_filter(weapon_type):
    weapon_img = f"assets/ui/weapon_{weapon_type}.png"

    if not os.path.exists(weapon_img):
        error("FILTER", f"武器图不存在: {weapon_type}")
        return False

    step("FILTER", f"打开筛选 → {weapon_type}")
    if not _click_filter_entry():
        error("FILTER", "未找到筛选入口")
        return False
    time.sleep(0.9)

    screen = _load_screen()
    panel, px1, py1 = _filter_panel_slice(screen)
    if panel is None:
        warn("FILTER", "无法截取筛选面板")
        pydirectinput.press("esc")
        time.sleep(0.5)
        return False

    if not _click_template_in_roi(
        panel,
        px1,
        py1,
        weapon_img,
        threshold=WEAPON_FILTER_THRESHOLD,
        min_scale=WEAPON_FILTER_MIN_SCALE,
        max_scale=WEAPON_FILTER_MAX_SCALE,
    ):
        warn("FILTER", f"筛选页内未找到 {weapon_type}")
        pydirectinput.press("esc")
        time.sleep(0.5)
        return False

    step("FILTER", f"已选 {weapon_type}")
    pydirectinput.press("esc")
    time.sleep(1.5)
    return True


def _clear_weapon_filter():
    """清除武器筛选：优先在搜索界面点「重置筛选」，避免 ESC 回大厅。"""
    return _reset_weapon_filter_on_search_ui()


def _cleanup_search_state(weapon_type):
    if not _prepare_search_for_next_character(used_weapon_filter=bool(weapon_type)):
        warn("SEARCH", "扫后清理未完全成功，下一位可能需重导航")


def _abort_character_search(char_name, weapon_type=None, reason=""):
    suffix = f": {reason}" if reason else ""
    warn("SEARCH", f"{char_name} 检索失败{suffix}")
    if not _prepare_search_for_next_character(used_weapon_filter=bool(weapon_type)):
        if not _is_in_warehouse() and not _is_search_panel_active():
            navigate_to_nikke_warehouse()
    return False


def process_single_character(char_name, replace_search=False):
    global _list_search_active

    search_name, weapon_type = _parse_char_name(char_name)
    label = f"{search_name}|{weapon_type}" if weapon_type else search_name
    step("SEARCH", f"检索 {label}")

    use_replace = replace_search or _list_search_active
    search_box, search_ready = _activate_search_input(replace_mode=use_replace)
    if not search_ready:
        return _abort_character_search(char_name, weapon_type, reason="搜索框未激活")

    _paste_from_clipboard(search_name)
    pydirectinput.press("enter")
    time.sleep(1.5)
    step("SEARCH", f"已搜索 {search_name}")
    _list_search_active = True

    if weapon_type and not _apply_weapon_filter(weapon_type):
        return _abort_character_search(char_name, weapon_type, reason=f"武器筛选 {weapon_type}")

    time.sleep(0.8)
    step("SEARCH", "点击首位结果")
    if not _click_first_search_result(cached_match=search_box):
        return _abort_character_search(char_name, weapon_type, reason="无法定位首位")

    found_t10 = scan_current_character_equipment(char_name)
    if found_t10:
        info("SCAN", f"{char_name} T10: {', '.join(found_t10)}")
    else:
        info("SCAN", f"{char_name} 无 T10")

    _cleanup_search_state(weapon_type)
    return True


def start_main_auto_flow(selected_characters):
    global _list_search_active
    _list_search_active = False

    begin_scan(selected_characters)
    set_scan_phase("正在接管游戏窗口…")

    if not force_bring_to_front():
        error("MAIN", "窗口初始化失败")
        abort_scan("window", "窗口初始化失败，请确认游戏已启动且窗口标题正确。")
        return

    configure_layout_from_window()

    set_scan_phase("正在导航至妮姬仓库…")
    if not navigate_to_nikke_warehouse():
        error("MAIN", "导航失败")
        abort_scan("navigation", "未能进入妮姬仓库，请确认游戏界面状态后重试。")
        return

    total = len(selected_characters)
    info("MAIN", f"开始扫描 {total} 位干员")

    aborted_for_auth = False

    for index, char_name in enumerate(selected_characters):
        info("MAIN", f"[{index + 1}/{total}] {char_name}")
        mark_progress(index, char_name)

        try:
            success = process_single_character(char_name, replace_search=index > 0)
        except ArcanaAuthError as exc:
            aborted_for_auth = True
            error("API", f"Token 失效，扫描中止: {exc}")
            abort_scan(
                "api_auth",
                "阿卡 API Token 无效或已过期，扫描已停止。请在控制台更新 Token 后重新执行。",
                detail=str(exc),
            )
            break

        if not success:
            warn("MAIN", f"跳过 {char_name}")

        mark_character_done(index)

        if index < total - 1:
            time.sleep(1.0)

    if aborted_for_auth:
        return

    info("MAIN", "扫描完成")
    finish_scan(f"已完成 {total} 位干员的扫描任务。")
    print_user_stat_summary()


if __name__ == "__main__":
    info("MAIN", "F12 紧急停止")
