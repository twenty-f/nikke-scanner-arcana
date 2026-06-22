import os
import time
import pydirectinput
import cv2
import numpy as np
from core.vision import find_image
from core.capture import get_screen, capture_active_window
from core.bot_client import send_to_bot
# ⭐️ 引入窗口管理器，用于获取游戏边界
from core.window_manager import get_window_rect

# 装备详情页基准锚点距离
BASE_Y_OFFSET_TOP = 70  
BASE_Y_OFFSET_BOTTOM = 70 

def scan_current_character_equipment(character_name):
    """⭐️ 封装好的核心：具备网络自适应、动态缩放与越界点击安全锁"""
    print(f"📸 [子任务] 正在等待【{character_name}】详情页加载，寻找双锚点定位装备槽...")
    
    max_retries = 20
    wait_interval = 0.5
    
    top_anchor = None
    bottom_anchor = None
    
    for attempt in range(max_retries):
        screen = get_screen()
        
        top_anchor = find_image(screen, "assets/anchor_top.png", show_result=False)
        bottom_anchor = find_image(screen, "assets/anchor_bottom.png", show_result=False)
        
        if top_anchor and bottom_anchor:
            print(f"✅ 第 {attempt + 1} 次尝试：页面加载完毕，成功定位双锚点！")
            break
            
        time.sleep(wait_interval)
        
    if not top_anchor or not bottom_anchor:
        print(f"❌ [子任务] 网络超时！详情页没找到锚点！跳过该角色...")
        pydirectinput.press('esc')
        time.sleep(1.5)
        return []
        
    # 获取锚点的中心坐标
    top_x = top_anchor[0][0] + (top_anchor[1] // 2)
    top_y = top_anchor[0][1] + (top_anchor[2] // 2)
    bottom_x = bottom_anchor[0][0] + (bottom_anchor[1] // 2)
    bottom_y = bottom_anchor[0][1] + (bottom_anchor[2] // 2)
    
    # 动态缩放比例计算
    try:
        top_img = cv2.imdecode(np.fromfile("assets/anchor_top.png", dtype=np.uint8), cv2.IMREAD_COLOR)
        original_top_h = top_img.shape[0]
        bottom_img = cv2.imdecode(np.fromfile("assets/anchor_bottom.png", dtype=np.uint8), cv2.IMREAD_COLOR)
        original_bottom_h = bottom_img.shape[0]
        
        scale_top = top_anchor[2] / original_top_h
        scale_bottom = bottom_anchor[2] / original_bottom_h
        avg_scale = (scale_top + scale_bottom) / 2.0
        
        dynamic_offset_top = int(BASE_Y_OFFSET_TOP * avg_scale)
        dynamic_offset_bottom = int(BASE_Y_OFFSET_BOTTOM * avg_scale)
    except Exception as e:
        dynamic_offset_top = BASE_Y_OFFSET_TOP
        dynamic_offset_bottom = BASE_Y_OFFSET_BOTTOM

    LEFT_COL_X = top_x
    RIGHT_COL_X = bottom_x
    ROW_1_Y = top_y + dynamic_offset_top
    ROW_2_Y = bottom_y - dynamic_offset_bottom

    equip_slots = {
        "头盔": (LEFT_COL_X, ROW_1_Y),
        "衣服": (RIGHT_COL_X, ROW_1_Y),
        "鞋子": (LEFT_COL_X, ROW_2_Y),
        "手套": (RIGHT_COL_X, ROW_2_Y)
    }

    t10_records = []
    temp_dir = "assets/temp"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    for part_name, (x, y) in equip_slots.items():
        print(f"\n🖱️ [子任务] 准备检查【{part_name}】...")
        pydirectinput.moveTo(int(x), int(y))
        pydirectinput.mouseDown()
        time.sleep(0.15)
        pydirectinput.mouseUp()
        
        time.sleep(1.2) 
        
        popup_screen = get_screen()
        is_t10 = find_image(popup_screen, "assets/overload_logo.png", threshold=0.75, show_result=False)
        
        if is_t10:
            print(f"🎉 [子任务] 确认为 T10！提取窗口词条截图...")
            t10_img_path = os.path.join(temp_dir, f"{character_name}_T10_{part_name}.png")
            capture_active_window(t10_img_path) 
            t10_records.append(part_name)
            send_to_bot(character_name, part_name, t10_img_path)
        else:
            print(f"⏭️ [子任务] 不是 T10，跳过。")
            
        # ==============================================================
        # ⭐️ 核心安全升级：高精度识别与物理边界安全锁
        # ==============================================================
        # 1. 提高阈值到 0.88，不放过任何瑕疵，杜绝错认浏览器
        close_btn = find_image(get_screen(), "assets/btn_close.png", threshold=0.88, show_result=False)
        
        if close_btn:
            cx = close_btn[0][0] + (close_btn[1] // 2)
            cy = close_btn[0][1] + (close_btn[2] // 2)
            
            # 2. 获取当前游戏窗口的真实边界
            rect = get_window_rect()
            is_safe_to_click = True
            
            if rect:
                left, top, width, height = rect
                # 3. 校验鼠标坐标是否在游戏窗口之内
                if not (left <= cx <= left + width and top <= cy <= top + height):
                    is_safe_to_click = False

            if is_safe_to_click:
                print(f"✖️ [子任务] 关闭【{part_name}】面板...")
                pydirectinput.moveTo(int(cx), int(cy))
                pydirectinput.click()
                time.sleep(1)
            else:
                # 触发拦截！
                print("🛑 [安全系统拦截] 危险！识别到的【关闭按钮】在游戏窗口之外！已放弃鼠标点击，转用物理热键。")
                pydirectinput.press('esc')
                time.sleep(1.2)
        else:
            print("⚠️ 详情页没找到关闭按钮，按 ESC 尝试...")
            pydirectinput.press('esc')
            time.sleep(1.2)
        # ==============================================================
            
    print("🔙 角色装备扫描完毕，正在返回全员列表页面...")
    pydirectinput.press('esc')
    time.sleep(1.5) 
    
    return t10_records