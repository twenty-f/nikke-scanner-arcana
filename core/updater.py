import os
import requests
import time
import urllib3

# ⭐️ 禁用关闭 SSL 校验后产生的烦人警告信息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 定义一个通用的请求头，防止 GitHub 拦截
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
# GitHub API 地址 (请确保这三个变量在你的代码里是对的)
REPO_OWNER = "twenty-f"
REPO_NAME = "nikke-scanner-arcana"
# ⭐️ 核心修改：在 URL 末尾追加 ?ref=main 来强制指定读取 main 分支
API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/assets/avatars?ref=main"

def check_and_update_avatars():
    print("🔄 正在检查指挥部最新的妮姬档案...")
    local_avatars_dir = os.path.join("assets", "avatars")
    
    if not os.path.exists(local_avatars_dir):
        os.makedirs(local_avatars_dir)

    try:
        # 使用 session 可以复用连接
        session = requests.Session()
        # ⭐️ 核心修复：全局关闭此 Session 的 SSL 证书严格校验，无视任何代理环境
        session.verify = False 
        
        # 1. 获取远端目录清单
        response = session.get(API_URL, headers=HEADERS, timeout=15)
        response.raise_for_status() 
        
        remote_chars = response.json()
        updated_count = 0
        
        for char_info in remote_chars:
            if char_info['type'] == 'dir':
                char_name = char_info['name']
                local_char_dir = os.path.join(local_avatars_dir, char_name)
                
                if not os.path.exists(local_char_dir):
                    os.makedirs(local_char_dir)
                    print(f"✨ 发现新妮姬档案：【{char_name}】，正在同步...")
                    
                    # 2. 获取该角色目录下的文件列表
                    files_resp = session.get(char_info['url'], headers=HEADERS, timeout=15)
                    files_resp.raise_for_status()
                    
                    for file_info in files_resp.json():
                        if file_info['name'].lower().endswith(('.png', '.jpg', '.jpeg')):
                            # 3. 下载文件
                            img_url = file_info['download_url']
                            img_resp = session.get(img_url, headers=HEADERS, timeout=20)
                            
                            with open(os.path.join(local_char_dir, file_info['name']), 'wb') as f:
                                f.write(img_resp.content)
                            print(f"   + 已下载: {file_info['name']}")
                    
                    updated_count += 1
                    
        if updated_count > 0:
            print(f"✅ 档案同步完成！新增 {updated_count} 名妮姬。")
            return True  # 告诉主程序有更新发生
        else:
            print("✅ 指挥部资料库已是最新。")
            return False # 告诉主程序没有更新

    except requests.exceptions.SSLError:
        print("⚠️ SSL 连接依然受阻：请检查网络。")
        return False
    except requests.exceptions.ConnectionError:
        print("⚠️ 网络连接中断：请检查互联网连接。")
        return False
    except Exception as e:
        print(f"⚠️ 热更新同步失败: {type(e).__name__} - {e}")
        return False