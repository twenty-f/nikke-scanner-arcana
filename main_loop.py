import pydirectinput
import time
import os
import keyboard
import cv2
import numpy as np
from core.window_manager import get_window_rect, force_bring_to_front
from core.equipment_scanner import scan_current_character_equipment
from core.vision import find_image
from core.capture import get_screen

# 路径配置
BTN_NIKKE = "assets/ui/btn_nikke.png"           # 妮姬仓库按钮（已切除红点区域）
WAREHOUSE_FILTER_ICONS = "assets/ui/warehouse_filter_icons.png" # 妮姬仓库特征图

def scroll_down():
    """彻底击穿 Unity 引擎底层防误触机制的微步阻尼滑动"""
    rect = get_window_rect()
    if not rect:
        return
        
    left, top, width, height = rect
    safe_x = int(left + (width * 0.50))
    start_y = int(top + (height * 0.70))
    end_y = int(top + (height * 0.30))
    
    pydirectinput.moveTo(safe_x, start_y)
    time.sleep(0.1) 
    pydirectinput.mouseDown()
    time.sleep(0.25) 
    
    steps = 20
    y_step = (end_y - start_y) / steps
    for i in range(steps):
        current_y = int(start_y + y_step * (i + 1))
        pydirectinput.moveTo(safe_x, current_y)
        time.sleep(0.02) 
        
    time.sleep(0.5) 
    pydirectinput.mouseUp()
    time.sleep(2.0) # 给画面渲染留出时间

def process_single_character(char_name):
    """
    负责寻找角色头像并进入详情页进行装备扫描（带滑动寻敌功能）
    """
    print(f"🔍 [查找] 正在寻找【{char_name}】的头像...")
    avatar_folder = f"assets/avatars/{char_name}"
    
    max_scrolls = 15 # 最多往下滑动 15 次
    
    for attempt in range(max_scrolls):
        # 尝试在当前界面寻找角色头像
        target_pos = find_image(get_screen(), avatar_folder, threshold=0.75, show_result=False)
        
        if target_pos:
            # 获取坐标中心点并点击
            cx = target_pos[0][0] + (target_pos[1] // 2)
            cy = target_pos[0][1] + (target_pos[2] // 2)
            print(f"🎯 成功匹配到头像！位置 ({cx}, {cy})，点击进入详情页...")
            
            pydirectinput.moveTo(int(cx), int(cy))
            pydirectinput.click()
            
            # 等待详情弹窗渲染
            time.sleep(2.5) 
            
            # 执行扫描
            found_t10 = scan_current_character_equipment(char_name)
            
            if found_t10:
                print(f"🎉 角色【{char_name}】装备状态扫描成功，找到了 T10: {found_t10}")
            else:
                print(f"⏭️ 角色【{char_name}】未发现 T10 或扫描失败。")
                
            return True # 只要找到了头像并处理完，就返回成功
            
        else:
            print("⏳ 当前屏幕未找到目标，正在稳步下探...")
            scroll_down()
            
    print(f"❌ 翻页 {max_scrolls} 次后，仍未找到【{char_name}】的头像。")
    return False

def navigate_to_nikke_warehouse():
    """智能导航系统：自动检测当前页面并跳转至妮姬仓库"""
    print("\n🌐 [初始化] 正在智能检测当前游戏页面状态...")
    
    for attempt in range(3):
        screen_raw = get_screen()
        if isinstance(screen_raw, str):
            if not os.path.exists(screen_raw):
                print(f"⚠️ [初始化] 截屏失败，正在重试... ({attempt+1}/3)")
                time.sleep(2)
                continue
            screen = cv2.imdecode(np.fromfile(screen_raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        else:
            screen = screen_raw

        if screen is None:
            print(f"⚠️ [初始化] 截屏解码失败，正在重试... ({attempt+1}/3)")
            time.sleep(2)
            continue

        h = screen.shape[0]
        roi_y_offset = int(h * 0.5)

        # 1. 优先校验是否已在仓库
        if find_image(screen, WAREHOUSE_FILTER_ICONS, threshold=0.75, show_result=False):
            print("✅ [初始化] 确认已在妮姬仓库页面。")
            return True

        # 2. 不在仓库则仅在屏幕下半部寻找底部妮姬按钮
        roi_screen = screen[roi_y_offset:, :]
        btn_info = find_image(roi_screen, BTN_NIKKE, threshold=0.60, show_result=False)
        if btn_info:
            target_x = btn_info[0][0] + btn_info[1] // 2
            target_y = btn_info[0][1] + btn_info[2] // 2 + roi_y_offset
            print(f"🖱️ [初始化] 锁定【妮姬】按钮 ({target_x}, {target_y})，正在跳转...")
            pydirectinput.click(target_x, target_y)
            time.sleep(3) # 等待长页面的切换加载动画
        else:
            print(f"⚠️ [初始化] 正在寻找入口... (重试 {attempt+1}/3)")
            time.sleep(2)
            
    return False

def start_main_auto_flow(selected_characters):
    """
    自动化执行总入口：加入状态自愈与容错机制
    """
    if not force_bring_to_front():
        print("🛑 窗口初始化失败，流程终止。")
        return

    # 智能导航到仓库列表页
    if not navigate_to_nikke_warehouse():
        print("🛑 页面定位失败，请确保游戏界面已显示底部导航栏。")
        return

    total = len(selected_characters)
    print(f"\n======================================\n🚀 [指挥官] 自动化流程正式开始！目标干员：{total} 位\n======================================\n")

    for index, char_name in enumerate(selected_characters):
        print(f"\n🔄 ({index+1}/{total}) 处理干员: 【{char_name}】")
        
        # 1. 尝试处理该角色
        success = process_single_character(char_name)
        
        # 2. 状态自愈：如果处理失败或找不到头像，执行一次“回退重连”
        if not success:
            print(f"⚠️ 未找到或处理失败【{char_name}】，执行状态自愈：回退至列表页...")
            pydirectinput.press('esc')
            time.sleep(1.5)
            # 重新回到导航起点，确保后续翻页逻辑基于正确的列表页
            navigate_to_nikke_warehouse()
            # 如果你有 scroll_reset()，可以在这里调用，比如把滚动条拉回最顶端
            # scroll_reset() 
        
        # 3. 逻辑修复：判断是否为最后一个任务
        if index == total - 1:
            print("\n🎉======================================\n✅ [自动化结束] 任务已全部完成！\n======================================\n")
            break
            
        # 翻页与过渡逻辑 (如果有需要，这里可以继续翻页)
        time.sleep(1)
        
# 如果想在 main_loop 独立测试
if __name__ == "__main__":
    print("🛡️ 请按 F12 键即可紧急停止脚本运行。")