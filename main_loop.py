import time
import os
import pydirectinput
from core.capture import get_screen
from core.vision import find_image
from core.equipment_scanner import scan_current_character_equipment

def scroll_down():
    """模拟真人鼠标拖拽翻页逻辑（强化版）"""
    print("⏳ 当前屏幕未找到目标，正在模拟物理拖拽翻页...")
    
    # 找一个绝对安全的空白区域（比如右侧滚动条附近，或者角色列表的缝隙）
    # 如果 960, 800 会点到角色，尝试更偏右的位置，比如 1300, 800 (根据你的屏幕分辨率调整)
    safe_x = 960
    start_y = 800
    end_y = 150 # 拖得更长一点，翻页幅度更大
    
    pydirectinput.moveTo(safe_x, start_y)
    time.sleep(0.3) # 停顿一下再按下
    pydirectinput.mouseDown()
    
    # 将拖动过程拆分成两段，模拟人手先快后慢的阻尼感
    pydirectinput.moveTo(safe_x, 500, duration=0.3) 
    pydirectinput.moveTo(safe_x, end_y, duration=0.4)
    
    # 停顿一下再松开，防止被判定为快速滑动抛出
    time.sleep(0.2)
    pydirectinput.mouseUp()
    
    # ⭐️ 增加等待时间，确保游戏列表的惯性滚动彻底停止，且画面渲染完成
    time.sleep(1.5)

def start_main_auto_flow(selected_characters):
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
                
                found_t10 = scan_current_character_equipment()
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