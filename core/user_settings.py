import json
import os
import sys

SETTINGS_FILENAME = "user_settings.json"


def get_real_base_path():
    """返回可写入用户配置的根目录（开发模式为项目根，打包后为 .exe 同级）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_settings_path():
    return os.path.join(get_real_base_path(), SETTINGS_FILENAME)


def load_settings():
    settings_path = _get_settings_path()
    if not os.path.exists(settings_path):
        return {}
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_token(token):
    token = str(token).strip() if token else ""
    if not token:
        return
    settings = load_settings()
    settings["token"] = token
    settings_path = _get_settings_path()
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def get_token():
    token = load_settings().get("token", "")
    return str(token).strip() if token else ""
