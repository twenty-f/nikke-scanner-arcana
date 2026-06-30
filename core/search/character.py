"""单干员搜索 → 装备扫描编排。"""

import time

from core.automation.actions import paste_from_clipboard, press_game_key
from core.equipment_scanner import scan_current_character_equipment
from core.log_utils import info, step, warn
from core.navigation.screen_state import is_in_warehouse
from core.navigation.warehouse import navigate_to_nikke_warehouse
from core.nikke_index import parse_char_key
from core.search.filter import ensure_weapon_filter_cleared, is_weapon_filter_active
from core.search.panel import (
    activate_search_input,
    click_first_search_result,
    is_search_panel_active,
    return_to_search_list_after_scan,
)
from core.search.session import get_search_session
from core.search.weapon_filter import apply_weapon_filter


def prepare_search_for_next_character(used_weapon_filter):
    if not return_to_search_list_after_scan():
        warn("SEARCH", "未能回到搜索/仓库，尝试重导航")
        if not navigate_to_nikke_warehouse():
            return False

    if used_weapon_filter:
        ensure_weapon_filter_cleared(is_search_panel_active)

    step("SEARCH", "搜索界面已就绪")
    return True


def cleanup_search_state(weapon_type):
    if not prepare_search_for_next_character(used_weapon_filter=bool(weapon_type)):
        warn("SEARCH", "扫后清理未完全成功，下一位可能需重导航")


def abort_character_search(char_name, weapon_type=None, reason=""):
    suffix = f": {reason}" if reason else ""
    warn("SEARCH", f"{char_name} 检索失败{suffix}")
    if not prepare_search_for_next_character(used_weapon_filter=bool(weapon_type)):
        if not is_in_warehouse() and not is_search_panel_active():
            navigate_to_nikke_warehouse()
    return False


def process_single_character(char_name, replace_search=False):
    session = get_search_session()
    search_name, weapon_type = parse_char_key(char_name)
    label = f"{search_name}|{weapon_type}" if weapon_type else search_name
    step("SEARCH", f"检索 {label}")

    use_replace = replace_search or session.list_search_active
    if use_replace and is_weapon_filter_active():
        ensure_weapon_filter_cleared(is_search_panel_active)

    search_box, search_ready = activate_search_input(replace_mode=use_replace)
    if not search_ready:
        return abort_character_search(char_name, weapon_type, reason="搜索框未激活")

    paste_from_clipboard(search_name)
    press_game_key("enter", wait_after=1.5)
    step("SEARCH", f"已搜索 {search_name}")
    session.list_search_active = True

    if weapon_type and not apply_weapon_filter(weapon_type):
        return abort_character_search(char_name, weapon_type, reason=f"武器筛选 {weapon_type}")

    time.sleep(0.8)
    step("SEARCH", "点击首位结果")
    if not click_first_search_result(cached_match=search_box):
        return abort_character_search(char_name, weapon_type, reason="无法定位首位")

    scan_result = scan_current_character_equipment(char_name)
    if scan_result is None:
        return abort_character_search(char_name, weapon_type, reason="装备页锚点未找到")

    uploaded_parts, captured_count = scan_result
    if uploaded_parts:
        info("SCAN", f"{char_name} T10: {', '.join(uploaded_parts)}")
    elif captured_count > 0:
        warn("SCAN", f"{char_name} 本地已截 {captured_count} 张 T10，云端未入库")
    else:
        info("SCAN", f"{char_name} 无 T10")

    cleanup_search_state(weapon_type)
    return True
