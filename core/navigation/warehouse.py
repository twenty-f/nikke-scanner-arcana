"""ESC 洗地、大厅进入妮姬仓库。"""

import time

from core.automation.actions import click_at, load_screen, press_game_key
from core.game_screen import capture_with_offset
from core.log_utils import error, step
from core.navigation.constants import (
    ESC_WASH_INTERVAL,
    LOBBY_READY_INTERVAL,
    LOBBY_READY_SETTLE,
    MAX_ESC_WASH,
    NAV_TEMPLATE_INTERVAL,
    WAREHOUSE_CLICK_SETTLE,
    WAREHOUSE_LOAD_INTERVAL,
)
from core.navigation.screen_state import (
    find_lobby_nikke_btn,
    find_quit_confirm,
    is_in_warehouse,
    is_lobby_ready,
    is_quit_confirm_visible,
)


def wait_until_lobby_ready(max_wait_sec=8, interval=LOBBY_READY_INTERVAL):
    deadline = time.time() + max_wait_sec
    while time.time() < deadline:
        if is_lobby_ready():
            time.sleep(LOBBY_READY_SETTLE)
            return True

        screen = load_screen()
        if screen is not None and find_lobby_nikke_btn(screen) and not find_quit_confirm(screen):
            time.sleep(LOBBY_READY_SETTLE)
            return True

        time.sleep(interval)

    error("NAV", "大厅就绪超时")
    return False


def dismiss_quit_confirm_and_wait():
    press_game_key("esc", wait_after=0.6)

    if is_quit_confirm_visible():
        press_game_key("esc", wait_after=0.6)

    return wait_until_lobby_ready()


def enter_nikke_warehouse_from_lobby():
    if not is_lobby_ready() and not wait_until_lobby_ready():
        return False

    btn_info = None
    screen = None
    ox, oy = 0, 0

    for attempt in range(4):
        screen, ox, oy = capture_with_offset()
        if screen is None:
            time.sleep(NAV_TEMPLATE_INTERVAL)
            continue

        btn_info = find_lobby_nikke_btn(screen)
        if btn_info and not find_quit_confirm(screen):
            break

        if attempt < 3:
            time.sleep(NAV_TEMPLATE_INTERVAL)

    if not btn_info or screen is None:
        error("NAV", "未找到妮姬入口")
        return False

    from core.aspect_layout import layout

    h = screen.shape[0]
    roi_y_offset = int(h * layout.lobby_roi_y_start)
    target_x = ox + btn_info[0][0] + btn_info[1] // 2
    target_y = oy + btn_info[0][1] + btn_info[2] // 2 + roi_y_offset
    click_at(target_x, target_y, wait_after=WAREHOUSE_CLICK_SETTLE)

    for attempt in range(8):
        if is_in_warehouse():
            step("NAV", "已进入妮姬仓库")
            return True
        if attempt < 7:
            time.sleep(WAREHOUSE_LOAD_INTERVAL)

    error("NAV", "进入仓库失败")
    return False


def navigate_to_nikke_warehouse():
    if is_in_warehouse():
        step("NAV", "已在仓库，跳过导航")
        return True

    if is_lobby_ready():
        step("NAV", "大厅 -> 仓库")
        return enter_nikke_warehouse_from_lobby()

    step("NAV", "ESC 洗地中")

    esc_count = 0
    while True:
        press_game_key("esc", wait_after=ESC_WASH_INTERVAL)
        esc_count += 1

        screen = load_screen()
        if screen is None:
            if esc_count >= MAX_ESC_WASH:
                error("NAV", "洗地后仍无法截屏")
                return False
            continue

        if find_quit_confirm(screen):
            step("NAV", "关闭退出确认框")
            if not dismiss_quit_confirm_and_wait():
                return False
            return enter_nikke_warehouse_from_lobby()

        if is_in_warehouse():
            step("NAV", f"洗地 {esc_count} 次后进入仓库")
            return True

        if is_lobby_ready():
            step("NAV", f"洗地 {esc_count} 次后到达大厅")
            return enter_nikke_warehouse_from_lobby()

        if esc_count >= MAX_ESC_WASH:
            error("NAV", "洗地超时")
            return False

        if esc_count % 3 == 0:
            step("NAV", f"洗地 {esc_count}/{MAX_ESC_WASH}")
