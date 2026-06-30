import os
import sys
import logging
import threading
import webbrowser
import time
from pynput import keyboard
from flask import Flask, render_template, request, jsonify, send_from_directory
from core.orchestrator import start_main_auto_flow
from core.log_utils import info, warn
from core.nikke_index import get_asset_id, load_nikke_index
from core.scan_session import get_scan_status, is_running
from core.updater import check_and_update_avatars
from core.bot_client import build_cloud_sync_map, fetch_user_stat_info
from core.user_settings import get_real_base_path, get_token, save_token

logging.getLogger("werkzeug").setLevel(logging.ERROR)

# ==============================================================
# 🚨 全局紧急停止开关：任何时候按下 F12，瞬间击杀整个 Python 进程
# ==============================================================
# ⭐️ 使用 pynput 替代 keyboard，因为它拥有更高的系统事件穿透力
def on_press(key):
    try:
        if key == keyboard.Key.f12:
            warn("APP", "F12 急停")
            time.sleep(0.1)
            os._exit(0)
    except Exception:
        pass

listener = keyboard.Listener(on_press=on_press)
listener.start()
info("APP", "F12 急停已启用")
# ==============================================================

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

template_dir = get_resource_path('templates')
app = Flask(__name__, template_folder=template_dir)

def get_available_characters():
    """从 nikke_index.json 读取干员名录，封面图仍取自 assets/avatars。"""
    avatars_dir = get_resource_path(os.path.join("assets", "avatars"))
    index = load_nikke_index()
    characters = []

    for char_name in index.keys():
        asset_id = get_asset_id(char_name)
        candidates = [asset_id, char_name, index.get(char_name, "")]
        cover_img = ""
        avatar_folder = ""
        for folder_name in candidates:
            if not folder_name:
                continue
            char_path = os.path.join(avatars_dir, folder_name)
            if os.path.isdir(char_path):
                avatar_folder = folder_name
                images = sorted(
                    f for f in os.listdir(char_path) if f.endswith((".png", ".jpg", ".jpeg"))
                )
                if images:
                    cover_img = next(
                        (f for f in images if f.lower().startswith("default")),
                        images[0],
                    )
                break
        characters.append({
            "name": char_name,
            "avatar_folder": avatar_folder,
            "cover": cover_img,
        })

    return characters

@app.route('/')
def index():
    return render_template('index.html', characters=get_available_characters())

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory(get_resource_path('assets'), filename)

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({"token": get_token()})


@app.route('/api/scan/status', methods=['GET'])
def scan_status():
    return jsonify(get_scan_status())


@app.route('/api/cloud/stats', methods=['POST'])
def cloud_stats():
    data = request.json or {}
    token = (data.get('token') or get_token() or '').strip()
    if not token:
        return jsonify({
            "success": False,
            "message": "请先输入阿卡 API Token",
            "auth_error": False,
            "characters": [],
        })

    result = build_cloud_sync_map(token)
    status_code = 401 if result.get("auth_error") else 200
    if not result.get("success") and not result.get("auth_error"):
        status_code = 200
    return jsonify(result), status_code


@app.route('/api/token/verify', methods=['POST'])
def verify_token():
    """测试阿卡 API Token 是否可用（不启动扫描）。"""
    data = request.json or {}
    token = (data.get('token') or get_token() or '').strip()
    if not token:
        return jsonify({
            "valid": False,
            "message": "请先输入阿卡 API Token",
            "auth_error": False,
        })

    result = fetch_user_stat_info(token)
    if result["success"]:
        save_token(token)
        count = len(result["data"] or [])
        return jsonify({
            "valid": True,
            "message": f"Token 有效，云端共有 {count} 位角色词条数据",
            "auth_error": False,
            "character_count": count,
        })

    return jsonify({
        "valid": False,
        "message": result.get("message") or "Token 验证失败",
        "auth_error": bool(result.get("auth_error")),
    }), 401 if result.get("auth_error") else 200


@app.route('/api/start', methods=['POST'])
def start_scan():
    data = request.json or {}
    selected_characters = data.get('characters', [])
    token_from_request = (data.get('token') or '').strip()
    token = token_from_request or get_token()

    if not selected_characters:
        return jsonify({"status": "error", "message": "No targets selected"}), 400

    if is_running():
        return jsonify({"status": "error", "message": "扫描任务进行中，请等待当前任务结束"}), 409

    if token_from_request:
        save_token(token_from_request)
    elif not token:
        warn("APP", "未配置 Token，扫描将截图但不上传云端")

    info("APP", f"扫描启动: {len(selected_characters)} 位干员")

    threading.Thread(
        target=lambda: start_main_auto_flow(selected_characters),
        daemon=True,
    ).start()

    return jsonify({"status": "success"})

def restart_program():
    info("APP", "重启以加载新资源")
    time.sleep(1)
    os.execl(sys.executable, sys.executable, *sys.argv)

def run_startup_sequence():
    info("APP", "启动检查")
    has_update = check_and_update_avatars()
    load_nikke_index()
    if has_update:
        restart_program()
        return

    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()

if __name__ == '__main__':
    run_startup_sequence()
    info("APP", "控制台 http://127.0.0.1:5000")
    app.run(port=5000, debug=False)