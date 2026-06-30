"""
兼容入口：主流程已拆分至 core/orchestrator 与 core/search、core/navigation。
保留本模块以免旧引用失效。
"""

from core.orchestrator import start_main_auto_flow
from core.navigation.warehouse import navigate_to_nikke_warehouse
from core.search.character import process_single_character

__all__ = [
    "start_main_auto_flow",
    "navigate_to_nikke_warehouse",
    "process_single_character",
]


if __name__ == "__main__":
    from core.log_utils import info

    info("MAIN", "F12 紧急停止")
