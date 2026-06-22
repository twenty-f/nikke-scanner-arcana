import time
import os
import pydirectinput
from core.capture import get_screen
from core.vision import find_image
from core.equipment_scanner import scan_current_character_equipment
# ⭐️ 引入我们刚刚新写的获取窗口尺寸的函数
from core.window_manager import get_window_rect 

def navigate_to_nikke_warehouse():
    """
    智能检测并导航到妮姬仓库页面。直接视觉锁定，彻底抛弃像素偏移！
    """
    print("\n🌐 [初始化] 正在智能检测当前游戏页面状态...")
    
    # 你的两张特征图路径
    WAREHOUSE_FILTER_ICONS = "assets/ui/warehouse_filter_icons.png"
    BTN_NIKKE = "assets/ui/btn_nikke.png"

    for attempt in range(3):
        screen = get_screen()
        
        # 1. 最高优先级：直接看是不是已经在仓库页面了
        is_warehouse = find_image(screen, WAREHOUSE_FILTER_ICONS, threshold=0.8, show_result=False)
        if is_warehouse:
            print("✅ [初始化] 确认当前已在妮姬仓库页面。自动化流程即将开始...")
            return True
            
        # 2. 如果不在仓库，直接在全屏寻找底部的【妮姬】入口按钮
        print("🗺️ [初始化] 当前不在仓库页面，正在寻找底部【妮姬】入口...")
        btn_info = find_image(screen, BTN_NIKKE, threshold=0.65, show_result=False)
        
        if btn_info:
            # 找到按钮了，视觉模块会返回边界，我们直接算出它的中心点并点击
            target_x = btn_info[0][0] + btn_info[1] // 2
            target_y = btn_info[0][1] + btn_info[2] // 2
            
            print(f"🖱️ [初始化] 成功锁定【妮姬】按钮坐标 ({target_x}, {target_y})，执行跨界点击...")
            pydirectinput.moveTo(target_x, target_y)
            time.sleep(0.15)
            pydirectinput.mouseDown()
            time.sleep(0.15)
            pydirectinput.mouseUp()
            
            # 等待长页面的切换加载动画
            time.sleep(3) 
            
            # 3. 再次校验是否成功进入了仓库
            screen_after_click = get_screen()
            if find_image(screen_after_click, WAREHOUSE_FILTER_ICONS, threshold=0.8, show_result=False):
                print("✅ [初始化] 导航成功！即将开始自动化流程...")
                return True
        else:
            print(f"⚠️ [初始化] 找不到【妮姬】按钮，可能被遮挡或处于全屏战斗中，重试第 {attempt+1}/3 次...")
            time.sleep(2)
             
    print("❌ [初始化] 智能导航失败。请确保游戏客户端处于已知页面（部队/大厅/物品栏/队员招募）。")
    return False

def scroll_down():
    """彻底击穿 Unity 引擎底层防误触机制的微步阻尼滑动"""
    print("⏳ 当前屏幕未找到目标，正在稳步下探...")
    
    rect = get_window_rect()
    if not rect:
        print("⚠️ 找不到游戏窗口，无法执行翻页操作！")
        return
        
    left, top, width, height = rect
    
    safe_x = int(left + (width * 0.50))
    # 稍微拉长一点滑动距离，确保画面能翻动：从 70% 高度滑到 30% 高度
    start_y = int(top + (height * 0.70))
    end_y = int(top + (height * 0.30))
    
    # 1. 移动到起点
    pydirectinput.moveTo(safe_x, start_y)
    time.sleep(0.1) 
    
    # 2. 模拟真实手指按下
    pydirectinput.mouseDown()
    
    # ⭐️ 核心破解 1：按下后必须死死按住不动，强迫游戏引擎注册“Touch Begin”事件
    time.sleep(0.25) 
    
    # ⭐️ 核心破解 2：物理级切片滑动 (将一段距离切成 20 份，每一份强制停顿)
    steps = 20
    y_step = (end_y - start_y) / steps
    
    for i in range(steps):
        current_y = int(start_y + y_step * (i + 1))
        pydirectinput.moveTo(safe_x, current_y)
        # 极短的睡眠，模拟鼠标的真实刷新率回报
        time.sleep(0.02) 
        
    # 3. 核心刹车：到达终点后，按住不动，清空游戏的滚动动能
    time.sleep(0.5) 
    
    # 4. 原地松手，完成一次极其逼真的物理拖拽
    pydirectinput.mouseUp()
    
    # 给界面惯性和下一帧渲染留出足够的读取时间
    time.sleep(2.0)

# ... 下面的 start_main_auto_flow 保持不变 ...
def start_main_auto_flow(selected_characters):
  # 🌟 修改2：智能导航。初始化自动化环境。
    if not navigate_to_nikke_warehouse():
        print("🛑 [主循环] 页面检测失败，自动化流程被迫终止。")
        return # 导航失败则退出主流程


    # 窗口抢占已由外层完成，这里直接执行扫描流
    for character_name in selected_characters:
        print(f"\n======================================")
        print(f"🚀 [指挥官] 开始寻找并处理妮姬: 【{character_name}】")
        print(f"======================================")
        
        avatar_folder = f"assets/avatars/{character_name}"
        if not os.path.exists(avatar_folder):
            print(f"⚠️ 未找到妮姬【{character_name}】的头像文件夹，请检查路径!")
            continue
            
        found = False
        max_scrolls = 15 
        
        while max_scrolls > 0:
            screen = get_screen()
            target_pos = find_image(screen, avatar_folder, show_result=False)
            
            if target_pos:
                cx = target_pos[0][0] + (target_pos[1] // 2)
                cy = target_pos[0][1] + (target_pos[2] // 2)
                print(f"🎯 成功匹配到头像！位置 ({cx}, {cy})，点击进入详情页...")
                
                pydirectinput.moveTo(int(cx), int(cy))
                pydirectinput.click()
                time.sleep(2.5) 
                
                # ✅ 正确的代码 (注意括号里的参数名，如果你在 for 循环里用的变量名叫 character，就传 character)
                found_t10 = scan_current_character_equipment(char_name)
                if found_t10 is not None:
                    print(f"🎉 角色【{character_name}】装备状态扫描成功，找到了 T10: {found_t10}")
                
                print(f"🔙 扫描完毕，正在返回全员列表页面...")
                pydirectinput.press('esc')
                time.sleep(2) 
                
                found = True
                break 
            else:
                scroll_down()
                max_scrolls -= 1
                
        if not found:
            print(f"❌ 翻遍了游戏列表，也没能找到妮姬【{character_name}】，已跳过。")

    print("\n🎉======================================")
    print("✅ [自动化主循环结束] 用户勾选的所有妮姬均已处理完毕！")
    print("======================================")