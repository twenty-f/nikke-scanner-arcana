import time
import pydirectinput
from core.vision import find_image
from core.capture import get_screen, capture_active_window

# 装备详情页锚点距离微调
Y_OFFSET_TOP = 70  # 纵向：在“装备”锚点下方偏移
Y_OFFSET_BOTTOM = 70 # 纵向：在“全部解除”锚点上方偏移

def scan_current_character_equipment():
    """⭐️ 封装好的核心：在角色详情页扫描四个装备格"""
    print("📸 [子任务] 正在详情页寻找双锚点定位装备槽...")
    screen = get_screen()
    
    # 1. 寻找详情页上下锚点
    top_anchor = find_image(screen, "assets/anchor_top.png", show_result=False)
    bottom_anchor = find_image(screen, "assets/anchor_bottom.png", show_result=False)
    
    if not top_anchor or not bottom_anchor:
        print("❌ [子任务] 详情页没找到锚点！跳过该角色扫描...")
        return
        
    # 获取锚点的中心坐标
    top_x = top_anchor[0][0] + (top_anchor[1] // 2)
    top_y = top_anchor[0][1] + (top_anchor[2] // 2)
    bottom_x = bottom_anchor[0][0] + (bottom_anchor[1] // 2)
    bottom_y = bottom_anchor[0][1] + (bottom_anchor[2] // 2)
    
    print(f"✅ [子任务] 定位成功！上方锚点:{top_x},{top_y} | 下方锚点:{bottom_x},{bottom_y}")

    # ==========================================
    # 🛠️ 坐标微调区 (根据你调通的数值填写)
    # ==========================================
    LEFT_COL_X = top_x
    RIGHT_COL_X = bottom_x
    ROW_1_Y = top_y + Y_OFFSET_TOP
    ROW_2_Y = bottom_y - Y_OFFSET_BOTTOM

    equip_slots = {
        "头盔": (LEFT_COL_X, ROW_1_Y),
        "衣服": (RIGHT_COL_X, ROW_1_Y),
        "鞋子": (LEFT_COL_X, ROW_2_Y),
        "手套": (RIGHT_COL_X, ROW_2_Y)
    }

    t10_records = []

    # 2. 开始循环点击 4 个部位并验证
    for name, (x, y) in equip_slots.items():
        print(f"\n🖱️ [子任务] 准备检查【{name}】...")
        # 底层物理点击
        pydirectinput.moveTo(int(x), int(y))
        pydirectinput.mouseDown()
        time.sleep(0.15)
        pydirectinput.mouseUp()
        # 等待详情弹窗
        time.sleep(1.2) 
        
        # 3. 验证是否为 T10 (找 OVERLOAD 标志)
        popup_screen = get_screen()
        is_t10 = find_image(popup_screen, "assets/overload_logo.png", threshold=0.75, show_result=False)
        
        if is_t10:
            print(f"🎉 [子任务] 确认为 T10！提取窗口词条截图...")
            t10_img_path = f"assets/temp/t10_{name}.png"
            capture_active_window(t10_img_path) # 精准抠图
            t10_records.append(name)
        else:
            print(f"⏭️ [子任务] 不是 T10，跳过。")
            
        # 4. 点击右上角的 X 关闭弹窗
        close_btn = find_image(get_screen(), "assets/btn_close.png", show_result=False)
        if close_btn:
            cx = close_btn[0][0] + (close_btn[1] // 2)
            cy = close_btn[0][1] + (close_btn[2] // 2)
            print(f"✖️ [子任务] 关闭【{name}】面板...")
            pydirectinput.moveTo(int(cx), int(cy))
            pydirectinput.click()
            time.sleep(1)
        else:
            print("⚠️ 详情页没找到关闭按钮，按 ESC 尝试...")
            pydirectinput.press('esc')
            time.sleep(1.2)
    return t10_records