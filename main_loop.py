import pydirectinput
import time
import os
import keyboard
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
        screen = get_screen()
        # 1. 优先校验是否已在仓库
        if find_image(screen, WAREHOUSE_FILTER_ICONS, threshold=0.8, show_result=False):
            print("✅ [初始化] 确认已在妮姬仓库页面。")
            return True
            
        # 2. 不在仓库则寻找底部妮姬按钮
        btn_info = find_image(screen, BTN_NIKKE, threshold=0.65, show_result=False)
        if btn_info:
            target_x = btn_info[0][0] + btn_info[1] // 2
            target_y = btn_info[0][1] + btn_info[2] // 2
            print(f"🖱️ [初始化] 锁定【妮姬】按钮 ({target_x}, {target_y})，正在跳转...")
            pydirectinput.click(target_x, target_y)
            time.sleep(3) # 等待长页面的切换加载动画
        else:
            print(f"⚠️ [初始化] 正在寻找入口... (重试 {attempt+1}/3)")
            time.sleep(2)
            
    return False

def start_main_auto_flow(selected_characters):
    """
    自动化执行总入口
    """
    # 强制接管并窗口置顶（自动适配多显示器）
    if not force_bring_to_front():
        print("🛑 窗口初始化失败，流程终止。")
        return

    # 智能导航到仓库
    if not navigate_to_nikke_warehouse():
        print("🛑 页面定位失败，请确保游戏界面已显示底部导航栏。")
        return

    total = len(selected_characters)
    print(f"\n======================================\n🚀 [指挥官] 自动化流程正式开始！目标干员：{total} 位\n======================================\n")

    for index, char_name in enumerate(selected_characters):
        print(f"\n🔄 ({index+1}/{total}) 处理干员: 【{char_name}】")
        
        # 执行单个角色的处理流程
        process_single_character(char_name)
        
        # 🌟 逻辑修复：判断是否为最后一个任务
        if index == total - 1:
            print("\n🎉======================================\n✅ [自动化结束] 任务已全部完成！\n======================================\n")
            break
            
        time.sleep(1)

# 如果想在 main_loop 独立测试
if __name__ == "__main__":
    print("🛡️ 请按 F12 键即可紧急停止脚本运行。")