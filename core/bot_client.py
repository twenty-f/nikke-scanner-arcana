import os

import requests

from core.user_settings import get_token

API_URL = "http://moti.x3322.net:9983/third/bot/nikke/v1/identifyImage"
REQUEST_TIMEOUT = 15
NO_PROXY = {"http": None, "https": None}


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


def upload_equipment_image(character_name, equipment_part, image_path):
    """
    将装备截图上传至阿卡 Bot 生产环境，解析词条并打印终端日志。
    无论成功或失败均安全返回布尔值，绝不阻断主流程。
    """
    if not os.path.exists(image_path):
        print(f"⚠️ [阿卡中枢] 找不到截图文件: {image_path}")
        return False

    token = get_token()
    if not token:
        print("🛑 [网络层] 尚未配置 API Token，自动跳过词条上传环节")
        return False

    headers = _build_auth_headers(token)

    try:
        with open(image_path, "rb") as image_file:
            response = requests.post(
                API_URL,
                headers=headers,
                files={"file": image_file},
                timeout=REQUEST_TIMEOUT,
                proxies=NO_PROXY,
            )
    except requests.exceptions.RequestException as exc:
        print(f"⚠️ [阿卡中枢] 网络请求失败【{character_name} - {equipment_part}】: {exc}")
        return False

    if response.status_code != 200:
        print(
            f"⚠️ [阿卡中枢] HTTP {response.status_code}【{character_name} - {equipment_part}】"
            f" -> {response.text[:200]}"
        )
        return False

    try:
        payload = response.json()
    except ValueError:
        print(f"⚠️ [阿卡中枢] 响应非合法 JSON【{character_name} - {equipment_part}】")
        return False

    if not payload.get("success"):
        message = payload.get("message") or "未知错误"
        print(f"⚠️ [阿卡中枢] 识别失败【{character_name} - {equipment_part}】-> {message}")
        return False

    data = payload.get("data") or {}
    stat_infos = data.get("statInfos") or []
    stats_text = _format_stat_infos(stat_infos) if stat_infos else "无词条数据"

    print(
        f"🎉 [阿卡中枢] 【{character_name} - {equipment_part}】词条解析成功 "
        f"-> [{stats_text}]"
    )
    return True
