import os
import time
import pydirectinput
import mss
from core.vision import find_image

def get_screen(save_path="assets/current_screen.png"):
    """极速截屏"""
    with mss.mss() as sct:
        sct.shot(mon=1, output=save_path)
    return save_path

def scroll_down():
    """模拟真人鼠标拖拽翻页"""
    print("⏳ 当前页面未找到，正在向下翻页...")
    pydirectinput.moveTo(960, 800) 
    pydirectinput.mouseDown()
    pydirectinput.moveTo(960, 350, duration=0.6) # 用0.6秒平滑拖拽，防止拉过头
    pydirectinput.mouseUp()
    time.sleep(1.5) # 等待滚动动画完全停止

def find_character_by_skins(character_name):
    """
    核心：遍历某个角色的所有皮肤图片，只要有一张对上，就返回坐标
    """
    dir_path = f"assets/avatars/{character_name}"
    if not os.path.exists(dir_path):
        print(f"⚠️ 未找到角色【{character_name}】的头像文件夹，请检查路径！")
        return None
        
    # 获取该角色文件夹下的所有图片（比如 default.png, skin1.png 等）
    skin_files = [f for f in os.listdir(dir_path) if f.endswith(('.png', '.jpg'))]
    
    if not skin_files:
        print(f"⚠️ 【{character_name}】文件夹下没有头像图片！")
        return None
        
    screen = get_screen()
    
    # 挨个皮肤试一遍
    for skin in skin_files:
        full_skin_path = os.path.join(dir_path, skin)
        # 适当调低一点阈值（比如 0.82），防范分辨率轻微拉伸带来的误差
        result = find_image(screen, full_skin_path, threshold=0.82, show_result=False)
        if result:
            print(f"✨ 成功匹配到【{character_name}】的皮肤/原皮: {skin}")
            return result # 只要有一个皮肤中了，立刻返回坐标
            
    return None # 所有皮肤都试过了，当前屏幕没找到

def start_auto_scan_flow(selected_characters):
    """
    外层主控调度流
    :param selected_characters: 用户勾选的角色名列表，例如 ['爱丽丝', '神罚']
    """
    for name in selected_characters:
        print(f"\n🚀 [主控] 开始寻找妮姬: 【{name}】")
        found = False
        max_scrolls = 15 # 妮姬较多时可以适当增加最大翻页次数
        
        while max_scrolls > 0:
            # 1. 尝试用“多皮肤匹配”在当前屏幕找人
            target_pos = find_character_by_skins(name)
            
            if target_pos:
                # 2. 找到了，计算中心点并点击进去
                cx = target_pos[0][0] + (target_pos[1] // 2)
                cy = target_pos[0][1] + (target_pos[2] // 2)
                print(f"🎯 成功锁定【{name}】坐标 ({cx}, {cy})，准备点击进入详情页...")
                
                # 物理点击进入
                pydirectinput.moveTo(int(cx), int(cy))
                pydirectinput.click()
                time.sleep(2.5) # 等待进入角色界面的动画放完
                
                # 3. 执行我们之前已经完美调通的四连击装备检测
                print(f"⚙️ 正在扫描【{name}】的 T10 装备状态...")
                # ==================================================
                # 这里放我们上一步写好的 main_workflow() 里的四连击逻辑
                # ==================================================
                
                # 4. 扫描完一件，重置状态（按 ESC 返回妮姬列表页面）
                print(f"🔙 【{name}】扫描完毕，正在返回妮姬列表...")
                pydirectinput.press('esc')
                time.sleep(2) # 等待列表重新加载出来
                
                found = True
                break # 跳出当前的翻页循环，去列表里找下一个勾选的妮姬
            else:
                # 5. 当前屏幕没找到，向下翻页
                scroll_down()
                max_scrolls -= 1
                
        if not found:
            print(f"❌ 翻遍了游戏列表，也没能找到妮姬【{name}】，已跳过该角色。")

    print("\n🎉 [完美收工] 用户勾选的所有妮姬均已处理完毕！")

if __name__ == "__main__":
    # 模拟用户在前端/QQ群里勾选了这两个人
    user_choices = ["爱丽丝", "神罚"]
    
    print("⏳ 脚本将在 3 秒后启动，请将游戏切换到【妮姬列表页面】（图一）...")
    time.sleep(3)
    start_auto_scan_flow(user_choices)