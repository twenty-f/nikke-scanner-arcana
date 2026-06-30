import os

import requests
import urllib3

from core.nikke_index import build_nikke_index

try:
    from config import HOT_UPDATE_ENABLED
except ImportError:
    HOT_UPDATE_ENABLED = False

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
REPO_OWNER = "twenty-f"
REPO_NAME = "nikke-scanner-arcana"
API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/assets/avatars?ref=main"

MIRROR_POOL = [
    "https://mirror.ghproxy.com/",
    "https://ghproxy.net/",
]

DIRECT_TIMEOUT = 3
MIRROR_TIMEOUT = 15
NO_PROXY = {"http": None, "https": None}
_mirror_notice_printed = False


def _build_mirror_url(original_url, mirror_prefix):
    return f"{mirror_prefix}{original_url}"


def smart_get(session, url, headers=None, direct_timeout=DIRECT_TIMEOUT, mirror_timeout=MIRROR_TIMEOUT):
    """
    智能下载：官方 GitHub 直连（快速失败）-> 国内镜像池自动降级。
    成功返回 Response，全部失败返回 None。
    """
    global _mirror_notice_printed
    headers = headers or HEADERS

    try:
        response = session.get(
            url,
            headers=headers,
            timeout=direct_timeout,
            proxies=NO_PROXY,
        )
        response.raise_for_status()
        return response
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        pass

    for mirror_prefix in MIRROR_POOL:
        if not _mirror_notice_printed:
            print("⚠️ [热更新中枢] 官方源连接超时，已无缝切换至国内加速通道...")
            _mirror_notice_printed = True

        mirror_url = _build_mirror_url(url, mirror_prefix)
        try:
            response = session.get(
                mirror_url,
                headers=headers,
                timeout=mirror_timeout,
                proxies=NO_PROXY,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException:
            continue

    return None


def check_and_update_avatars():
    global _mirror_notice_printed
    _mirror_notice_printed = False

    if not HOT_UPDATE_ENABLED:
        print("⏸️ [热更新中枢] 热更新已暂时关闭（config.HOT_UPDATE_ENABLED = False），跳过远端同步。")
        return False

    print("🔄 正在检查指挥部最新的妮姬档案...")
    local_avatars_dir = os.path.join("assets", "avatars")

    if not os.path.exists(local_avatars_dir):
        os.makedirs(local_avatars_dir)

    session = requests.Session()
    session.verify = False

    response = smart_get(session, API_URL)
    if response is None:
        print("⚠️ [热更新中枢] 所有下载通道均不可用，已跳过热更新。")
        return False

    try:
        remote_chars = response.json()
    except ValueError:
        print("⚠️ [热更新中枢] 远端目录解析失败，已跳过热更新。")
        return False

    updated_count = 0

    for char_info in remote_chars:
        if char_info.get("type") != "dir":
            continue

        char_name = char_info["name"]
        local_char_dir = os.path.join(local_avatars_dir, char_name)

        if os.path.exists(local_char_dir):
            continue

        os.makedirs(local_char_dir)
        print(f"✨ 发现新妮姬档案：【{char_name}】，正在同步...")

        files_resp = smart_get(session, char_info["url"])
        if files_resp is None:
            print(f"⚠️ [热更新中枢] 无法获取【{char_name}】文件列表，跳过该角色。")
            continue

        try:
            file_list = files_resp.json()
        except ValueError:
            print(f"⚠️ [热更新中枢] 【{char_name}】目录解析失败，跳过该角色。")
            continue

        download_failed = False
        for file_info in file_list:
            if not file_info["name"].lower().endswith((".png", ".jpg", ".jpeg")):
                continue

            img_resp = smart_get(session, file_info["download_url"], mirror_timeout=20)
            if img_resp is None:
                print(f"⚠️ [热更新中枢] 下载失败: {file_info['name']}")
                download_failed = True
                break

            with open(os.path.join(local_char_dir, file_info["name"]), "wb") as f:
                f.write(img_resp.content)
            print(f"   + 已下载: {file_info['name']}")

        if download_failed:
            continue

        updated_count += 1

    if updated_count > 0:
        print(f"✅ 档案同步完成！新增 {updated_count} 名妮姬。")
        build_nikke_index()
        return True

    print("✅ 指挥部资料库已是最新。")
    return False
