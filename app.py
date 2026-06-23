import os
import sys
import keyboard
import threading
import webbrowser
import time
from pynput import keyboard
from flask import Flask, render_template, request, jsonify, send_from_directory
from main_loop import start_main_auto_flow
from core.updater import check_and_update_avatars
from core.user_settings import get_real_base_path, get_token, save_token
# ⭐️ 这里已经修正为最新的 force_bring_to_front
from core.window_manager import force_bring_to_front

# ==============================================================
# 🚨 全局紧急停止开关：任何时候按下 F12，瞬间击杀整个 Python 进程
# ==============================================================
# ⭐️ 使用 pynput 替代 keyboard，因为它拥有更高的系统事件穿透力
def on_press(key):
    try:
        if key == keyboard.Key.f12:
            print("\n🛑 [EMERGENCY STOP] 检测到 F12 急停指令！")
            os._exit(0)
    except Exception:
        pass

# 启动一个独立的守护线程进行内核级监听
listener = keyboard.Listener(on_press=on_press)
listener.start()
print("🛡️ 安全系统已升级为内核级监听：在任何窗口按下 F12 均可立刻中止脚本！")
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
    avatars_dir = get_resource_path(os.path.join('assets', 'avatars'))
    characters = []
    if os.path.exists(avatars_dir):
        for char_name in os.listdir(avatars_dir):
            char_path = os.path.join(avatars_dir, char_name)
            if os.path.isdir(char_path):
                images = [f for f in os.listdir(char_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
                cover_img = images[0] if images else ""
                characters.append({"name": char_name, "cover": cover_img})
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


@app.route('/api/start', methods=['POST'])
def start_scan():
    data = request.json or {}
    selected_characters = data.get('characters', [])
    token = (data.get('token') or '').strip()

    if not selected_characters:
        return jsonify({"status": "error", "message": "No targets selected"}), 400

    save_token(token)
    print(f"🌐 [Web控制台] 收到扫描请求: {selected_characters} | Token 已持久化至 {get_real_base_path()}")

    threading.Thread(
        target=lambda: (force_bring_to_front(), start_main_auto_flow(selected_characters)),
        daemon=True,
    ).start()

    return jsonify({"status": "success"})

def restart_program():
    print("🔄 正在重新启动客户端以加载新资源...")
    time.sleep(1)
    os.execl(sys.executable, sys.executable, *sys.argv)

def run_startup_sequence():
    print("--- 启动序列检查 ---")
    has_update = check_and_update_avatars()
    if has_update:
        restart_program()
        return 
        
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    print("--- 启动序列完成 ---")

if __name__ == '__main__':
    run_startup_sequence()
    print("🚀 控制面板启动中... 请在浏览器访问 http://127.0.0.1:5000")
    app.run(port=5000, debug=False)