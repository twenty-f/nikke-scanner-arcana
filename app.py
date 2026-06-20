import os
import threading
from flask import Flask, render_template, request, jsonify, send_from_directory
from main_loop import start_main_auto_flow

app = Flask(__name__)

def get_available_characters():
    """读取 avatars 目录，获取所有配置好的角色及封面图"""
    avatars_dir = os.path.join('assets', 'avatars')
    characters = []
    
    if os.path.exists(avatars_dir):
        # 遍历出所有角色名（文件夹名）
        for char_name in os.listdir(avatars_dir):
            char_path = os.path.join(avatars_dir, char_name)
            if os.path.isdir(char_path):
                # 寻找该文件夹下的一张图片作为前端的封面展示
                images = [f for f in os.listdir(char_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
                cover_img = images[0] if images else ""
                
                characters.append({
                    "name": char_name,
                    "cover": cover_img
                })
    return characters

@app.route('/')
def index():
    # 将角色列表传给前端 HTML
    chars = get_available_characters()
    return render_template('index.html', characters=chars)

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    # 允许前端访问 assets 里的图片用于展示
    return send_from_directory('assets', filename)

@app.route('/api/start', methods=['POST'])
def start_scan():
    data = request.json
    selected_characters = data.get('characters', [])
    
    if not selected_characters:
        return jsonify({"status": "error", "message": "No targets selected"}), 400

    print(f"🌐 [Web控制台] 收到扫描请求: {selected_characters}")
    
    # 使用新线程启动底层的物理自动化流程，防止阻塞 Web 服务器
    threading.Thread(target=start_main_auto_flow, args=(selected_characters,), daemon=True).start()
    
    return jsonify({"status": "success"})

if __name__ == '__main__':
    print("🚀 控制面板启动中... 请在浏览器访问 http://127.0.0.1:5000")
    # debug=False 防止启动时热重载导致的二次运行问题
    app.run(port=5000, debug=False)