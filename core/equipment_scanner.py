import os
import time
import pydirectinput
import cv2
import numpy as np
from core.vision import find_image
from core.capture import get_screen, capture_active_window
from core.bot_client import upload_equipment_image
# ==============================================================
# 🎯 动态比例系数（橡皮筋算法校准区）
# 因为你把上锚点换成了更高的“小队”，所以第一排离上锚点变远了，第二排离下锚点距离没变。
# 如果鼠标点击偏上，就把数字调大；如果点击偏下，就把数字调小。
# ==============================================================
RATIO_TOP_TO_ROW1 = 0.38    # 第一排装备：在双锚点总高度往下 28% 的位置 (原24%)
RATIO_BOTTOM_TO_ROW2 = 0.23 # 第二排装备：在双锚点总高度往上 21% 的位置 (原24%)

def scan_current_character_equipment(character_name):
    print(f"📸 [子任务] 正在等待【{character_name}】详情页加载，寻找双锚点（小队 & 全部解除）...")
    
    max_retries = 20
    wait_interval = 0.5
    
    top_anchor = None
    bottom_anchor = None
    
    for attempt in range(max_retries):
        screen = get_screen()
        
        if isinstance(screen, str):
            if not os.path.exists(screen):
                continue
            screen = cv2.imdecode(np.fromfile(screen, dtype=np.uint8), cv2.IMREAD_COLOR)
            
        if screen is None:
            continue
            
        h, w = screen.shape[:2]
        roi_x_start = int(w * 0.5)           
        roi_screen = screen[:, roi_x_start:] 

        # 换了独一无二的锚点，阈值可以非常放心地保持在 0.80
        top_roi = find_image(roi_screen, "assets/anchor_top.png", threshold=0.80, show_result=False)
        bottom_roi = find_image(roi_screen, "assets/anchor_bottom.png", threshold=0.80, show_result=False)
        
        if top_roi and bottom_roi:
            top_anchor = (
                (top_roi[0][0] + roi_x_start, top_roi[0][1]),
                top_roi[1], 
                top_roi[2]
            )
            bottom_anchor = (
                (bottom_roi[0][0] + roi_x_start, bottom_roi[0][1]),
                bottom_roi[1], 
                bottom_roi[2]
            )
            
            tx = top_anchor[0][0] + (top_anchor[1] // 2)
            ty = top_anchor[0][1] + (top_anchor[2] // 2)
            bx = bottom_anchor[0][0] + (bottom_anchor[1] // 2)
            by = bottom_anchor[0][1] + (bottom_anchor[2] // 2)

            # 空间拓扑学防御
            if by - ty < h * 0.15:
                print(f"⚠️ 空间拦截：两锚点垂直距离过近 ({by-ty}px)，重新扫描...")
                top_anchor = None
                bottom_anchor = None
                time.sleep(wait_interval)
                continue

            if abs(tx - bx) > w * 0.10:
                print(f"⚠️ 空间拦截：两锚点水平跨度过大 ({abs(tx-bx)}px)，重新扫描...")
                top_anchor = None
                bottom_anchor = None
                time.sleep(wait_interval)
                continue
            
            print(f"✅ 第 {attempt + 1} 次尝试：成功在右侧面板锁定【小队】与【全部解除】！")
            break
            
        time.sleep(wait_interval)
        
    if not top_anchor or not bottom_anchor:
        print(f"❌ [子任务] 详情页没找到真锚点！跳过该角色...")
        pydirectinput.press('esc')
        time.sleep(1.5)
        return []
        
    top_x = top_anchor[0][0] + (top_anchor[1] // 2)
    top_y = top_anchor[0][1] + (top_anchor[2] // 2)
    bottom_x = bottom_anchor[0][0] + (bottom_anchor[1] // 2)
    bottom_y = bottom_anchor[0][1] + (bottom_anchor[2] // 2)
    
    total_h = abs(bottom_y - top_y)
    
    # ⭐️ 使用你在顶部配置的新比例进行精准打击
    ROW_1_Y = int(top_y + total_h * RATIO_TOP_TO_ROW1)
    ROW_2_Y = int(bottom_y - total_h * RATIO_BOTTOM_TO_ROW2)
    
    LEFT_COL_X = min(top_x, bottom_x)
    RIGHT_COL_X = max(top_x, bottom_x)
    
    print(f"📐 几何引擎重算落点 -> 左列X:{LEFT_COL_X}, 右列X:{RIGHT_COL_X} | 顶排Y:{ROW_1_Y}, 底排Y:{ROW_2_Y}")

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
            upload_equipment_image(character_name, part_name, t10_img_path)
        else:
            print(f"⏭️ [子任务] 不是 T10，跳过。")
            
        close_btn = find_image(get_screen(), "assets/btn_close.png", threshold=0.88, show_result=False)

        if close_btn:
            print(f"✖️ [子任务] 检测到【{part_name}】详情面板，发送 ESC 关闭...")
        else:
            print(f"⚠️ [子任务] 未检测到关闭按钮，仍发送 ESC 兜底关闭...")

        pydirectinput.press('esc')
        time.sleep(1.2)
            
    print("🔙 角色装备扫描完毕，正在返回全员列表页面...")
    pydirectinput.press('esc')
    time.sleep(1.5) 
    
    return t10_records