import os

import requests

from core.log_utils import error, info, warn
from core.nikke_index import get_search_name, load_nikke_index
from core.user_settings import get_token


class ArcanaAuthError(Exception):
    """阿卡 API Key 无效或过期，需立即停止扫描并通知用户。"""

    def __init__(self, message, character_name=None, equipment_part=None, status_code=None):
        self.character_name = character_name
        self.equipment_part = equipment_part
        self.status_code = status_code
        detail = message
        if character_name and equipment_part:
            detail = f"【{character_name} - {equipment_part}】{message}"
        super().__init__(detail)


API_BASE = "http://moti.x3322.net:9983/third/bot/nikke/v1"
IDENTIFY_AND_UPDATE_URL = f"{API_BASE}/identifyStatImageAndUpdate"
USER_STAT_INFO_URL = f"{API_BASE}/getUserStatInfo"
REQUEST_TIMEOUT = 15
BATCH_REQUEST_TIMEOUT = 45
NO_PROXY = {"http": None, "https": None}

# 本地槽位名 -> API slotNo（0 头 / 1 衣 / 2 手 / 3 鞋）
LOCAL_PART_TO_SLOT_NO = {
    "头盔": 0,
    "衣服": 1,
    "手套": 2,
    "鞋子": 3,
}
SLOT_NO_TO_LOCAL_PART = {v: k for k, v in LOCAL_PART_TO_SLOT_NO.items()}


def _build_auth_headers(token):
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return {"X-API-KEY": token}


def _format_stat_infos(stat_infos):
    parts = []
    for stat in stat_infos:
        name = stat.get("statName") or stat.get("statShortName") or "未知词条"
        value = stat.get("statValue", "?")
        level = stat.get("statValueLevel", "?")
        parts.append(f"{name}: {value} (Lv.{level})")
    return " | ".join(parts)


def _parse_json_response(response):
    try:
        return response.json()
    except ValueError:
        return None


def _is_auth_error_message(message):
    if not message:
        return False
    msg = message.lower()
    keywords = ("api key", "apikey", "无效", "过期", "未授权", "unauthorized", "forbidden")
    return any(keyword in msg for keyword in keywords)


def _raise_if_auth_failure(response, payload=None, character_name=None, equipment_part=None):
    if payload is None:
        payload = _parse_json_response(response)

    message = (payload or {}).get("message") or ""
    if response.status_code in (401, 403) or _is_auth_error_message(message):
        raise ArcanaAuthError(
            message or f"HTTP {response.status_code}",
            character_name=character_name,
            equipment_part=equipment_part,
            status_code=response.status_code,
        )


def _remove_temp_image(image_path):
    try:
        os.remove(image_path)
    except OSError as exc:
        warn("API", f"临时截图清理失败: {exc}")


def _remove_temp_images(image_paths):
    for path in image_paths:
        _remove_temp_image(path)


def _parse_equipment_results(data_list):
    """解析批量入库响应，返回 API 确认有效的部位名列表。"""
    confirmed = []
    for item in data_list or []:
        slot_no = item.get("slotNo")
        slot_name = item.get("slotName") or "?"
        stat_infos = item.get("statInfos") or []
        if slot_no is None or slot_no < 0 or not stat_infos:
            continue
        part_name = SLOT_NO_TO_LOCAL_PART.get(slot_no, slot_name)
        confirmed.append(part_name)
    return confirmed


def upload_character_equipment_batch(character_name, image_paths):
    """
    一次性上传一位干员的多张 T10 装备截图（multipart 字段 files[]）。
    部位由 API OCR 自动识别，本地无需标注槽位。

    image_paths: 截图路径列表（1~4 张均可）。
    返回 API 确认入库的部位名列表；无 Token / 网络失败 / 业务失败返回 []。
    API Key 无效/过期时抛出 ArcanaAuthError。
    """
    valid = [path for path in image_paths if path and os.path.exists(path)]
    if not valid:
        warn("API", f"{character_name} 无有效截图可上传")
        return []

    token = get_token()
    if not token:
        warn("API", "未配置 Token，跳过上传")
        return []

    api_character_name = get_search_name(character_name)
    headers = _build_auth_headers(token)
    params = {"characterName": api_character_name}

    file_handles = []
    multipart_files = []
    try:
        for index, path in enumerate(valid):
            handle = open(path, "rb")
            file_handles.append(handle)
            multipart_files.append(
                ("files", (f"equip_{index}.jpg", handle, "image/jpeg"))
            )

        response = requests.post(
            IDENTIFY_AND_UPDATE_URL,
            headers=headers,
            params=params,
            files=multipart_files,
            timeout=BATCH_REQUEST_TIMEOUT,
            proxies=NO_PROXY,
        )
    except requests.exceptions.RequestException as exc:
        warn("API", f"{character_name} 批量上传网络失败: {exc}")
        return []
    finally:
        for handle in file_handles:
            handle.close()

    payload = _parse_json_response(response)

    if response.status_code != 200:
        message = (payload or {}).get("message") or (response.text or "")[:200]
        warn("API", f"{character_name} 批量上传 HTTP {response.status_code}: {message}")
        _remove_temp_images(valid)
        _raise_if_auth_failure(
            response,
            payload,
            character_name=character_name,
            equipment_part="批量",
        )
        return []

    if payload is None:
        warn("API", f"{character_name} 批量上传响应非 JSON")
        return []

    if not payload.get("success"):
        message = payload.get("message") or "未知错误"
        warn("API", f"{character_name} 批量入库失败: {message}")
        _remove_temp_images(valid)
        _raise_if_auth_failure(
            response,
            payload,
            character_name=character_name,
            equipment_part="批量",
        )
        return []

    data_list = payload.get("data") or []
    confirmed = _parse_equipment_results(data_list)

    for item in data_list:
        slot_no = item.get("slotNo")
        slot_name = item.get("slotName") or "?"
        stat_infos = item.get("statInfos") or []
        if slot_no is not None and slot_no >= 0 and stat_infos:
            stats_text = _format_stat_infos(stat_infos)
            info("API", f"{character_name}/{slot_name} -> {stats_text}")

    _remove_temp_images(valid)
    return confirmed


def upload_equipment_image(character_name, equipment_part, image_path):
    """兼容旧调用：单张截图走批量接口。"""
    return upload_character_equipment_batch(character_name, [image_path])


def fetch_user_stat_info(token=None):
    """
    拉取阿卡云端词条库。
    返回 {"success": bool, "data": list|None, "message": str, "auth_error": bool}
    """
    token = (token or get_token() or "").strip()
    if not token:
        return {"success": False, "data": None, "message": "未配置 Token", "auth_error": False}

    headers = _build_auth_headers(token)

    try:
        response = requests.get(
            USER_STAT_INFO_URL,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            proxies=NO_PROXY,
        )
    except requests.exceptions.RequestException as exc:
        return {"success": False, "data": None, "message": str(exc), "auth_error": False}

    payload = _parse_json_response(response)

    if response.status_code != 200:
        auth_error = response.status_code in (401, 403)
        message = response.text[:200]
        if payload and payload.get("message"):
            message = payload["message"]
            auth_error = auth_error or _is_auth_error_message(message)
        return {
            "success": False,
            "data": None,
            "message": message,
            "auth_error": auth_error,
        }

    if payload is None:
        return {"success": False, "data": None, "message": "响应非合法 JSON", "auth_error": False}

    if not payload.get("success"):
        message = payload.get("message") or "未知错误"
        return {
            "success": False,
            "data": None,
            "message": message,
            "auth_error": _is_auth_error_message(message),
        }

    return {
        "success": True,
        "data": payload.get("data") or [],
        "message": "",
        "auth_error": False,
    }


def build_cloud_sync_map(token=None):
    """
    将云端词条与本地名录 key 对齐。
    匹配规则：get_search_name(local_key) == API characterName
    """
    result = fetch_user_stat_info(token)
    if not result["success"]:
        return {**result, "characters": []}

    cloud_by_name = {}
    for char_info in result["data"]:
        name = char_info.get("characterName")
        if name:
            cloud_by_name[name] = char_info

    matched = []
    for local_key in load_nikke_index().keys():
        search_name = get_search_name(local_key)
        cloud = cloud_by_name.get(search_name)
        if not cloud:
            continue

        equipments = cloud.get("equipmentInfos") or []
        slots_with_data = [e for e in equipments if e.get("statInfos")]
        if not slots_with_data:
            continue

        slot_labels = [
            e.get("slotName") or f"slot{e.get('slotNo', '?')}"
            for e in slots_with_data
        ]
        matched.append({
            "local_key": local_key,
            "cloud_name": search_name,
            "slot_count": len(slots_with_data),
            "slots": slot_labels,
        })

    return {
        "success": True,
        "characters": matched,
        "cloud_total": len(result["data"]),
        "message": "",
        "auth_error": False,
    }


def format_user_stat_summary(characters):
    """将云端角色列表格式化为简洁摘要行。"""
    lines = []
    for char_info in characters:
        char_name = char_info.get("characterName") or "?"
        equipments = char_info.get("equipmentInfos") or []
        slots = [
            e.get("slotName") or str(e.get("slotNo", "?"))
            for e in equipments
            if e.get("statInfos")
        ]
        if slots:
            lines.append(f"  {char_name}: {'/'.join(slots)}")
        else:
            lines.append(f"  {char_name}: (无词条)")
    return lines


def print_user_stat_summary():
    result = fetch_user_stat_info()
    if not result["success"]:
        if result["message"] != "未配置 Token":
            warn("API", f"云端校验失败: {result['message']}")
        return False

    characters = result["data"]
    if not characters:
        info("API", "云端暂无已入库角色")
        return True

    info("API", f"云端词条摘要 ({len(characters)} 角色)")
    for line in format_user_stat_summary(characters):
        print(line, flush=True)
    return True
