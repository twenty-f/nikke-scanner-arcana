"""搜索栏会话状态（多干员连续搜索）。"""

from dataclasses import dataclass, field


@dataclass
class SearchSessionState:
    list_search_active: bool = False

    def reset(self):
        self.list_search_active = False


_session = SearchSessionState()


def get_search_session():
    return _session
