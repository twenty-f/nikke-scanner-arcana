"""扫描队列编排：窗口就绪 → 导航 → 逐干员处理。"""

import time

from core.aspect_layout import configure_layout_from_window
from core.bot_client import ArcanaAuthError, print_user_stat_summary
from core.log_utils import error, info, warn
from core.navigation.warehouse import navigate_to_nikke_warehouse
from core.scan_session import abort_scan, begin_scan, finish_scan, mark_character_done, mark_progress, set_scan_phase
from core.search.character import process_single_character
from core.search.filter import set_weapon_filter_active
from core.search.session import get_search_session
from core.window_manager import force_bring_to_front


def start_main_auto_flow(selected_characters):
    get_search_session().reset()
    set_weapon_filter_active(False)

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
