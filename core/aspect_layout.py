"""按游戏窗口宽高比（4:3 / 16:9 / 21:9）提供 UI 点击与 ROI 比例。"""

from core.log_utils import step
from core.window_manager import get_window_rect

# 标准预设宽高比
AR_4_3 = 4 / 3
AR_16_9 = 16 / 9
AR_21_9 = 21 / 9


class LayoutProfile:
    __slots__ = (
        "name",
        "first_result_col_x_ratio",
        "first_result_row_y_ratio",
        # 第一行：搜索开关（筛选栏最左放大镜，居中而非贴窗口左缘）
        "search_toggle_x_ratio",
        "search_toggle_y_ratio",
        "search_toggle_left_of_filter_ratio",
        "filter_toolbar_roi_x",
        "filter_toolbar_roi_y",
        # 第二行：搜索输入框（在右侧灰放大镜左边）
        "search_input_x_ratio",
        "search_input_y_ratio",
        "search_row_roi_y",
        "search_input_left_of_execute_ratio",
        "search_box_roi_height_ratio",
        "filter_clear_roi_x",
        "filter_clear_roi_y",
        "filter_clear_x_ratio",
        "filter_clear_y_ratio",
        "filter_clear_below_execute_ratio",
        "filter_clear_min_x_ratio",
        "filter_panel_roi_x",
        "filter_panel_roi_y",
        "popup_roi_x",
        "popup_roi_y",
        "ratio_top_to_row1",
        "ratio_bottom_to_row2",
        "detail_roi_x_start",
        "lobby_roi_y_start",
    )

    def __init__(self, name, **kwargs):
        self.name = name
        for key in self.__slots__:
            if key == "name":
                continue
            setattr(self, key, kwargs[key])


# UI 布局（两行）：
# 行1（居中）[搜索开关🔍][I][II][III]…[战斗力▼]
# 行2 [搜索输入框………………][灰放大镜=执行搜索]
PROFILES = {
    "4:3": LayoutProfile(
        name="4:3",
        first_result_col_x_ratio=0.13,
        first_result_row_y_ratio=0.50,
        search_toggle_x_ratio=0.368,
        search_toggle_y_ratio=0.206,
        search_toggle_left_of_filter_ratio=0.240,
        filter_toolbar_roi_x=(0.12, 0.88),
        filter_toolbar_roi_y=(0.17, 0.26),
        search_input_x_ratio=0.26,
        search_input_y_ratio=0.246,
        search_row_roi_y=(0.22, 0.37),
        search_input_left_of_execute_ratio=0.14,
        search_box_roi_height_ratio=0.36,
        filter_clear_roi_x=(0.50, 0.74),
        filter_clear_roi_y=(0.27, 0.36),
        filter_clear_x_ratio=0.58,
        filter_clear_y_ratio=0.305,
        filter_clear_below_execute_ratio=0.050,
        filter_clear_min_x_ratio=0.50,
        filter_panel_roi_x=(0.22, 0.78),
        filter_panel_roi_y=(0.18, 0.75),
        popup_roi_x=(0.06, 0.64),
        popup_roi_y=(0.12, 0.88),
        ratio_top_to_row1=0.38,
        ratio_bottom_to_row2=0.23,
        detail_roi_x_start=0.48,
        lobby_roi_y_start=0.50,
    ),
    "16:9": LayoutProfile(
        name="16:9",
        first_result_col_x_ratio=0.11,
        first_result_row_y_ratio=0.50,
        search_toggle_x_ratio=0.368,
        search_toggle_y_ratio=0.206,
        search_toggle_left_of_filter_ratio=0.237,
        filter_toolbar_roi_x=(0.15, 0.85),
        filter_toolbar_roi_y=(0.18, 0.26),
        search_input_x_ratio=0.24,
        search_input_y_ratio=0.246,
        search_row_roi_y=(0.22, 0.36),
        search_input_left_of_execute_ratio=0.14,
        search_box_roi_height_ratio=0.35,
        filter_clear_roi_x=(0.50, 0.72),
        filter_clear_roi_y=(0.27, 0.36),
        filter_clear_x_ratio=0.58,
        filter_clear_y_ratio=0.305,
        filter_clear_below_execute_ratio=0.050,
        filter_clear_min_x_ratio=0.50,
        filter_panel_roi_x=(0.25, 0.75),
        filter_panel_roi_y=(0.18, 0.72),
        popup_roi_x=(0.08, 0.62),
        popup_roi_y=(0.12, 0.88),
        ratio_top_to_row1=0.38,
        ratio_bottom_to_row2=0.23,
        detail_roi_x_start=0.50,
        lobby_roi_y_start=0.50,
    ),
    "21:9": LayoutProfile(
        name="21:9",
        first_result_col_x_ratio=0.09,
        first_result_row_y_ratio=0.50,
        search_toggle_x_ratio=0.368,
        search_toggle_y_ratio=0.206,
        search_toggle_left_of_filter_ratio=0.255,
        filter_toolbar_roi_x=(0.18, 0.82),
        filter_toolbar_roi_y=(0.17, 0.25),
        search_input_x_ratio=0.20,
        search_input_y_ratio=0.246,
        search_row_roi_y=(0.21, 0.35),
        search_input_left_of_execute_ratio=0.12,
        search_box_roi_height_ratio=0.34,
        filter_clear_roi_x=(0.52, 0.70),
        filter_clear_roi_y=(0.26, 0.35),
        filter_clear_x_ratio=0.56,
        filter_clear_y_ratio=0.300,
        filter_clear_below_execute_ratio=0.048,
        filter_clear_min_x_ratio=0.48,
        filter_panel_roi_x=(0.28, 0.72),
        filter_panel_roi_y=(0.18, 0.72),
        popup_roi_x=(0.10, 0.58),
        popup_roi_y=(0.12, 0.88),
        ratio_top_to_row1=0.38,
        ratio_bottom_to_row2=0.23,
        detail_roi_x_start=0.52,
        lobby_roi_y_start=0.50,
    ),
}

layout = PROFILES["16:9"]


def detect_aspect_label(width, height):
    """根据窗口宽高判定最接近的游戏预设比例档。"""
    if width <= 0 or height <= 0:
        return "16:9"

    aspect = width / height
    mid_4_16 = (AR_4_3 + AR_16_9) / 2
    mid_16_21 = (AR_16_9 + AR_21_9) / 2

    if aspect < mid_4_16:
        return "4:3"
    if aspect < mid_16_21:
        return "16:9"
    return "21:9"


def apply_layout(label):
    """切换当前生效的比例档。"""
    global layout
    if label not in PROFILES:
        label = "16:9"
    layout = PROFILES[label]
    return layout


def configure_layout_from_window(window_title="胜利女神：新的希望"):
    """
    读取游戏窗口尺寸并应用对应比例档。
    返回 (比例档名称, 窗口宽, 窗口高)。
    """
    rect = get_window_rect(window_title)
    if not rect:
        apply_layout("16:9")
        step("WIN", "UI 比例档 16:9（未能读取窗口，使用默认）")
        return "16:9", 0, 0

    _, _, width, height = rect
    label = detect_aspect_label(width, height)
    apply_layout(label)
    step("WIN", f"UI 比例档 {label}（{width}x{height}）")
    return label, width, height
