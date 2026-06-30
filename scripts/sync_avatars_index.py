"""一次性同步 assets/avatars 与 nikke_index.json（可重复运行）。"""
import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AVATARS_DIR = os.path.join(PROJECT_ROOT, "assets", "avatars")
INDEX_PATH = os.path.join(PROJECT_ROOT, "nikke_index.json")

# 旧文件夹名 -> 新命名规则（JSON value）
LEGACY_FOLDER_TO_VALUE = {
    "伊莎贝尔": "伊莎贝尔",
    "小红帽": "小红帽_SR",
    "尼恩：蓝色海洋": "尼恩_蓝色海洋",
    "拉毗：小红帽": "拉毗_小红帽",
    "灰姑娘": "灰姑娘",
    "画皮": "画皮",
    "红莲": "红莲_AR",
    "红莲：暗影": "红莲_暗影",
    "迪塞尔：冬日甜心": "迪塞尔_冬日甜心",
    "阿尼斯：闪耀夏日": "阿妮斯_闪耀夏日",
    "阿妮斯：闪耀夏日": "阿妮斯_闪耀夏日",
    "鲁德米拉：冬日之主": "鲁德米拉_冬日之主",
}


def _list_avatar_folders():
    if not os.path.isdir(AVATARS_DIR):
        os.makedirs(AVATARS_DIR)
    return sorted(
        name
        for name in os.listdir(AVATARS_DIR)
        if os.path.isdir(os.path.join(AVATARS_DIR, name))
    )


def _resolve_target_folder(folder_name, index):
    if folder_name in index.values():
        return folder_name
    if folder_name in index:
        return index[folder_name]
    if folder_name in LEGACY_FOLDER_TO_VALUE:
        return LEGACY_FOLDER_TO_VALUE[folder_name]
    return None


def sync_avatars_with_index():
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        index = json.load(f)

    renames = []
    for folder in _list_avatar_folders():
        target = _resolve_target_folder(folder, index)
        if not target or target == folder:
            continue

        src = os.path.join(AVATARS_DIR, folder)
        dst = os.path.join(AVATARS_DIR, target)
        if os.path.exists(dst):
            print(f"[skip rename] target exists: {folder} -> {target}")
            continue

        os.rename(src, dst)
        renames.append((folder, target))
        print(f"[rename] {folder} -> {target}")

    folders = set(_list_avatar_folders())
    values = set(index.values())

    created = []
    for value in sorted(values):
        path = os.path.join(AVATARS_DIR, value)
        if value not in folders:
            os.makedirs(path, exist_ok=True)
            created.append(value)
            print(f"[mkdir] {value}")

    folders = set(_list_avatar_folders())
    added_to_json = []
    for folder in sorted(folders):
        if folder in values:
            continue
        index[folder] = folder
        added_to_json.append(folder)
        print(f"[json add] {folder}: {folder}")

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("--- summary ---")
    print(f"renamed: {len(renames)}")
    print(f"created: {len(created)}")
    print(f"json added: {len(added_to_json)}")
    print(f"total folders: {len(_list_avatar_folders())}")
    print(f"total json entries: {len(index)}")


if __name__ == "__main__":
    sync_avatars_with_index()
