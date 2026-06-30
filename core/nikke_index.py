import json
import os
import sys

from core.user_settings import get_real_base_path

NIKKE_INDEX_FILENAME = "nikke_index.json"


def _get_bundled_avatars_dir():
    """读取头像资源目录（开发模式为项目内 assets，打包后为 MEIPASS）。"""
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, "assets", "avatars")


def get_index_path():
    """名录 JSON 写入可写目录（开发模式为项目根，打包后为 .exe 同级）。"""
    return os.path.join(get_real_base_path(), NIKKE_INDEX_FILENAME)


def char_key_to_asset_id(char_key):
    """
    将名录 key 转为 assets 文件夹 ID（value 规则）：
    - 含 | 后缀：主名中「：」→「_」，再追加 _{后缀}
    - 仅含「：」：全部替换为 _
    - 否则保持原名
    """
    if "|" in char_key:
        base, suffix = char_key.rsplit("|", 1)
        return base.replace("：", "_") + f"_{suffix}"
    if "：" in char_key:
        return char_key.replace("：", "_")
    return char_key


def build_nikke_index():
    """
    扫描 assets/avatars 子文件夹，按标准规则生成映射表。
    若 nikke_index.json 已存在则保留手工维护版本，不覆盖。
    """
    index_path = get_index_path()
    if os.path.exists(index_path):
        return load_nikke_index()

    avatars_dir = _get_bundled_avatars_dir()
    index = {}

    if os.path.isdir(avatars_dir):
        for folder_name in sorted(os.listdir(avatars_dir)):
            char_path = os.path.join(avatars_dir, folder_name)
            if os.path.isdir(char_path):
                index[folder_name] = folder_name

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"[nikke_index] synced {len(index)} characters -> {index_path}")
    return index


def load_nikke_index(force_rebuild=False):
    """加载干员名录；文件不存在或 force_rebuild 时自动重建。"""
    index_path = get_index_path()
    if force_rebuild or not os.path.exists(index_path):
        return build_nikke_index()

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else build_nikke_index()
    except (OSError, json.JSONDecodeError):
        return build_nikke_index()


def get_asset_id(char_key):
    """根据名录 key 获取 assets/avatars 下的文件夹 ID（JSON value）。"""
    index = load_nikke_index()
    return index.get(char_key, char_key_to_asset_id(char_key))


def get_search_name(char_key):
    """游戏内搜索使用 key 的显示主名（去掉 |武器 后缀，保留中文冒号）。"""
    if "|" in char_key:
        return char_key.rsplit("|", 1)[0]
    return char_key


def parse_char_key(char_key):
    """解析名录 key → (search_name, weapon_type|None)。"""
    if "|" in char_key:
        search_name, weapon_type = char_key.rsplit("|", 1)
        return search_name.strip(), weapon_type.strip().upper()
    return char_key.strip(), None
