import os
import sys
import keyboard
import threading
import webbrowser
import time
from flask import Flask, render_template, request, jsonify, send_from_directory
from main_loop import start_main_auto_flow
from core.updater import check_and_update_avatars
# ⭐️ 这里已经修正为最新的 force_bring_to_front
from core.window_manager import force_bring_to_front

# ==============================================================
# 🚨 全局紧急停止开关：任何时候按下 F12，瞬间击杀整个 Python 进程
# ==============================================================
def emergency_stop():
    print("\n\n🛑 [EMERGENCY STOP] 接收到 F12 急停指令！正在强制切断系统电源...")
    os._exit(0) # 物理级终结进程，立刻释放键鼠

keyboard.add_hotkey('f12', emergency_stop)
print("🛡️ 安全系统已上线：随时可按【F12】键紧急中止脚本！")
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

@app.route('/api/start', methods=['POST'])
def start_scan():
    data = request.json
    selected_characters = data.get('characters', [])
    
    if not selected_characters:
        return jsonify({"status": "error", "message": "No targets selected"}), 400

    print(f"🌐 [Web控制台] 收到扫描请求: {selected_characters}")
    
    # ⭐️ 这里也已经同步修正为调用 force_bring_to_front()
    threading.Thread(target=lambda: (force_bring_to_front(), start_main_auto_flow(selected_characters)), daemon=True).start()
    
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