import time
import os
import pydirectinput
from core.capture import get_screen
from core.vision import find_image
# 引入核心装备扫描子逻辑
from core.equipment_scanner import scan_current_character_equipment

def scroll_down():
    """模拟真人鼠标拖拽翻页逻辑"""
    print("⏳ 当前屏幕未找到，正在向下翻页寻找...")
    # 把鼠标移动到屏幕中央偏下的安全位置（避免点到特定角色按钮）
    pydirectinput.moveTo(960, 800) 
    # 按住左键向下拖
    pydirectinput.mouseDown()
    # 用 0.6 秒平滑向上拖动到 Y=350 的位置（向上拖即是把页面往下拉）
    pydirectinput.moveTo(960, 350, duration=0.6) 
    pydirectinput.mouseUp()
    # 等待惯性滑动停止和画面加载
    time.sleep(1.5) 

def start_main_auto_flow(selected_characters):
    """
    ⭐️ [主指挥官] 自动化总调度流程
    :param selected_characters: 用户勾选的角色名列表，例如 ['爱丽丝', '神罚', '红莲']
    """
    for character_name in selected_characters:
        print(f"\n======================================")
        print(f"🚀 [指挥官] 开始寻找并处理妮姬: 【{character_name}】")
        print(f"======================================")
        
        # 构造头像文件夹路径
        avatar_folder = f"assets/avatars/{character_name}"
        if not os.path.exists(avatar_folder):
            print(f"⚠️ 未找到妮姬【{character_name}】的头像文件夹，请检查路径!")
            continue
            
        found = False
        max_scrolls = 15 # 安全机制：一个全角色账号最多翻 15 页，防止死循环
        
        while max_scrolls > 0:
            screen = get_screen()
            
            # 1. 尝试用“多皮肤头像匹配”找当前屏幕有没有人
            target_pos = find_image(screen, avatar_folder, show_result=False)
            
            if target_pos:
                # 2. 找到角色头像，计算坐标点进去
                cx = target_pos[0][0] + (target_pos[1] // 2)
                cy = target_pos[0][1] + (target_pos[2] // 2)
                print(f"🎯 成功匹配到头像！位置 ({cx}, {cy})，点击进入详情页...")
                
                # 物理点击进入
                pydirectinput.moveTo(int(cx), int(cy))
                pydirectinput.click()
                
                # 等待角色页面的进入动画放完
                time.sleep(2.5) 
                
                # ==================================================
                # 3. ⭐️ 执行装备扫描核心逻辑 (调用核心子函数)
                # ==================================================
                found_t10 = scan_current_character_equipment()
                if found_t10 is not None:
                    print(f"🎉 角色【{character_name}】装备状态扫描成功，找到了 T10: {found_t10}")
                
                # 4. 处理完毕，重置状态：按 ESC 返回妮姬列表页面
                print(f"🔙 扫描完毕，正在返回全员列表页面...")
                pydirectinput.press('esc')
                # 等待列表重新加载出来
                time.sleep(2) 
                
                found = True
                break # 跳出当前的翻页寻找循环，进入下一个角色的寻找
            else:
                # 5. 当前屏幕没找到，执行翻页
                scroll_down()
                max_scrolls -= 1
                
        if not found:
            print(f"❌ 翻遍了游戏列表，也没能找到妮姬【{character_name}】，已跳过。")

    print("\n🎉======================================")
    print("✅ [自动化主循环结束] 用户勾选的所有妮姬均已处理完毕！")
    print("======================================")

if __name__ == "__main__":
    # 模拟用户在前端或者QQ群里勾选的名单
    user_choices = ["红莲"] # 你可以根据你建的头像文件夹来改这里，支持皮肤
    
    print("⏳ 自动化测试即将开始！你有 3 秒钟把游戏界面切换到【妮姬列表页面】...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1...")
    time.sleep(1)
    
    start_main_auto_flow(user_choices)