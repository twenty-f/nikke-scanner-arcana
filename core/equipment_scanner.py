import os
import time

import cv2

from core.aspect_layout import layout
from core.automation.actions import click_at, press_game_key
from core.bot_client import ArcanaAuthError, upload_character_equipment_batch
from core.capture import capture_active_window
from core.game_screen import capture_with_offset
from core.log_utils import error, info, step, warn
from core.nikke_index import get_asset_id
from core.vision import find_image

OVERLOAD_TEMPLATE = "assets/overload_logo.png"
CLOSE_TEMPLATE = "assets/btn_close.png"

OVERLOAD_THRESHOLD = 0.72
POPUP_CLOSE_THRESHOLD = 0.82
OVERLOAD_MIN_SCALE = 0.55
OVERLOAD_MAX_SCALE = 1.45
UPLOAD_JPEG_QUALITY = 85
UPLOAD_MAX_WIDTH = 1280
SLOT_SCAN_ORDER = ("头盔", "衣服", "手套", "鞋子")
POPUP_POLL_INTERVAL = 0.35
POPUP_POLL_MAX = 12
DEBUG_POPUP_PATH = os.path.join("assets", "temp", "debug_popup_last.jpg")


def _layout_popup_roi(screen):
    h, w = screen.shape[:2]
    x1 = int(w * layout.popup_roi_x[0])
    x2 = int(w * layout.popup_roi_x[1])
    y1 = int(h * layout.popup_roi_y[0])
    y2 = int(h * layout.popup_roi_y[1])
    return screen[y1:y2, x1:x2], x1, y1


def _overload_search_rois(screen):
    """
    OVERLOAD 检测用 ROI（仅检测，不改 layout 上传裁剪）。
    弹窗在右侧装备栏时，原 popup_roi 可能盖不住，追加 detail 半屏。
    """
    if screen is None:
        return []
    h, w = screen.shape[:2]
    main, _, _ = _layout_popup_roi(screen)
    detail_x = int(w * layout.detail_roi_x_start)
    return [main, screen[:, detail_x:]]


def _match_template(screen, template_path, threshold):
    if screen is None:
        return False
    return bool(
        find_image(
            screen,
            template_path,
            threshold=threshold,
            min_scale=OVERLOAD_MIN_SCALE,
            max_scale=OVERLOAD_MAX_SCALE,
            silent=True,
        )
    )


def _detect_t10_in_popup(screen):
    """全窗口 + 分 ROI 检测 OVERLOAD。"""
    if _match_template(screen, OVERLOAD_TEMPLATE, OVERLOAD_THRESHOLD):
        return True
    for roi in _overload_search_rois(screen):
        if roi is None or roi.size == 0:
            continue
        if find_image(
            roi,
            OVERLOAD_TEMPLATE,
            threshold=OVERLOAD_THRESHOLD,
            min_scale=OVERLOAD_MIN_SCALE,
            max_scale=OVERLOAD_MAX_SCALE,
            silent=True,
        ):
            return True
    return False


def _is_equipment_popup_open(screen):
    if _match_template(screen, CLOSE_TEMPLATE, POPUP_CLOSE_THRESHOLD):
        return True
    roi, _, _ = _layout_popup_roi(screen)
    return bool(
        find_image(
            roi,
            CLOSE_TEMPLATE,
            threshold=POPUP_CLOSE_THRESHOLD,
            min_scale=OVERLOAD_MIN_SCALE,
            max_scale=OVERLOAD_MAX_SCALE,
            silent=True,
        )
    )


def _capture_game_bgr_after_click():
    """
    点击槽位后轮询截屏（capture_with_offset 内已 ensure_game_focus）。
    返回 (screen, 't10'|'popup'|None)。
    """
    last_screen = None
    for _ in range(POPUP_POLL_MAX):
        time.sleep(0.08)
        screen, _, _ = capture_with_offset()
        last_screen = screen
        if screen is None:
            time.sleep(POPUP_POLL_INTERVAL)
            continue
        if _detect_t10_in_popup(screen):
            return screen, "t10"
        if _is_equipment_popup_open(screen):
            return screen, "popup"
        time.sleep(POPUP_POLL_INTERVAL)
    return last_screen, None


def _save_debug_popup(screen):
    if screen is None:
        return
    try:
        os.makedirs(os.path.dirname(DEBUG_POPUP_PATH), exist_ok=True)
        ok, encoded = cv2.imencode(".jpg", screen, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ok:
            encoded.tofile(DEBUG_POPUP_PATH)
    except OSError:
        pass


def _save_popup_crop_for_upload(screen, image_path):
    """保存弹窗 ROI 为 JPEG（沿用 layout.popup_roi，与历史行为一致）。"""
    if screen is None:
        capture_active_window(image_path)
        return image_path

    crop, _, _ = _layout_popup_roi(screen)

    if crop.shape[1] > UPLOAD_MAX_WIDTH:
        scale = UPLOAD_MAX_WIDTH / crop.shape[1]
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    if not image_path.lower().endswith(".jpg"):
        image_path = os.path.splitext(image_path)[0] + ".jpg"

    ok, encoded = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, UPLOAD_JPEG_QUALITY])
    if not ok:
        capture_active_window(image_path)
        return image_path
    encoded.tofile(image_path)
    return image_path


def _escape_equipment_ui():
    for _ in range(3):
        press_game_key("esc", wait_after=0.8)


def _anchor_center(anchor, ox, oy):
    (lx, ly), tw, th = anchor
    return ox + lx + tw // 2, oy + ly + th // 2


def scan_current_character_equipment(character_name):
    """
    扫描当前角色四槽装备。
    返回：None=锚点失败；(uploaded_parts, captured_count)=扫描结果。
    uploaded_parts 为 API 确认部位名；captured_count 为本地 T10 截图张数。
    """
    step("SCAN", f"{character_name} 等待装备页")

    max_retries = 20
    wait_interval = 0.5
    top_anchor = None
    bottom_anchor = None
    anchor_ox, anchor_oy = 0, 0

    for _attempt in range(max_retries):
        screen, ox, oy = capture_with_offset()
        if screen is None:
            time.sleep(wait_interval)
            continue

        h, w = screen.shape[:2]
        roi_x_start = int(w * layout.detail_roi_x_start)
        roi_screen = screen[:, roi_x_start:]

        top_roi = find_image(roi_screen, "assets/anchor_top.png", threshold=0.80, silent=True)
        bottom_roi = find_image(roi_screen, "assets/anchor_bottom.png", threshold=0.80, silent=True)

        if top_roi and bottom_roi:
            top_anchor = (
                (top_roi[0][0] + roi_x_start, top_roi[0][1]),
                top_roi[1],
                top_roi[2],
            )
            bottom_anchor = (
                (bottom_roi[0][0] + roi_x_start, bottom_roi[0][1]),
                bottom_roi[1],
                bottom_roi[2],
            )

            tx, ty = _anchor_center(top_anchor, ox, oy)
            bx, by = _anchor_center(bottom_anchor, ox, oy)

            if by - ty < h * 0.15 or abs(tx - bx) > w * 0.10:
                top_anchor = None
                bottom_anchor = None
                time.sleep(wait_interval)
                continue

            anchor_ox, anchor_oy = ox, oy
            break

        time.sleep(wait_interval)

    if not top_anchor or not bottom_anchor:
        error("SCAN", f"{character_name} 未找到装备锚点，跳过")
        press_game_key("esc", wait_after=1.5)
        return None

    top_x, top_y = _anchor_center(top_anchor, anchor_ox, anchor_oy)
    bottom_x, bottom_y = _anchor_center(bottom_anchor, anchor_ox, anchor_oy)
    total_h = abs(bottom_y - top_y)

    row_1_y = int(top_y + total_h * layout.ratio_top_to_row1)
    row_2_y = int(bottom_y - total_h * layout.ratio_bottom_to_row2)
    left_col_x = min(top_x, bottom_x)
    right_col_x = max(top_x, bottom_x)

    equip_slots = {
        "头盔": (left_col_x, row_1_y),
        "衣服": (right_col_x, row_1_y),
        "手套": (left_col_x, row_2_y),
        "鞋子": (right_col_x, row_2_y),
    }

    temp_dir = "assets/temp"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    t10_images = []

    for part_name in SLOT_SCAN_ORDER:
        x, y = equip_slots[part_name]
        click_at(x, y, wait_after=0.15)

        popup_screen, popup_kind = _capture_game_bgr_after_click()

        if popup_kind == "t10":
            file_stem = get_asset_id(character_name)
            img_path = os.path.join(temp_dir, f"{file_stem}_T10_{len(t10_images)}.jpg")
            saved = _save_popup_crop_for_upload(popup_screen, img_path)
            if saved:
                img_path = saved
            t10_images.append(img_path)
            info("SCAN", f"{character_name} {part_name} T10，已截图")
        elif popup_kind == "popup":
            info("SCAN", f"{character_name} {part_name} 非 T10，跳过")
        else:
            _save_debug_popup(popup_screen)
            warn(
                "SCAN",
                f"{character_name} {part_name} 未检测到装备弹窗"
                f"（排查用截图: {DEBUG_POPUP_PATH}）",
            )

        press_game_key("esc", wait_after=1.2)

    if not t10_images:
        return [], 0

    step("SCAN", f"{character_name} 批量上传 {len(t10_images)} 张 T10")
    try:
        uploaded = upload_character_equipment_batch(character_name, t10_images)
    except ArcanaAuthError:
        _escape_equipment_ui()
        raise

    captured = len(t10_images)
    if captured and not uploaded:
        warn(
            "SCAN",
            f"{character_name} 已截取 {captured} 张 T10，上传未成功（请检查 Token 或网络）",
        )
    return uploaded, captured
