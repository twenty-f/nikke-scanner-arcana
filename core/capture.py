import time
import pydirectinput
import mss
import mss.tools
import os
import sys
import ctypes
from ctypes import wintypes

# 确保能正常引入其他核心模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.vision import find_image

# 安全机制：如果鼠标失控，把鼠标用力甩到屏幕四个角落的任意一个，程序就会强制报错停止！
pydirectinput.FAILSAFE = True

def get_screen(save_path="assets/current_screen.png"):
    """使用 mss 极速截取当前全屏并保存"""
    with mss.mss() as sct:
        # mon=1 代表抓取主显示器
        sct.shot(mon=1, output=save_path)
    return save_path

def capture_active_window(save_path):
    """仅截取当前活动窗口（也就是你的游戏客户端）并保存"""
    user32 = ctypes.windll.user32
    # 获取当前最顶层的活动窗口句柄
    hwnd = user32.GetForegroundWindow()
    
    # 获取该窗口的边界坐标
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    
    # 组装 mss 要求的裁剪区域
    region = {
        "top": rect.top,
        "left": rect.left,
        "width": rect.right - rect.left,
        "height": rect.bottom - rect.top
    }
    
    with mss.mss() as sct:
        # 仅抓取游戏窗口区域
        sct_img = sct.grab(region)
        # 转换为 PNG 并保存
        mss.tools.to_png(sct_img.rgb, sct_img.size, output=save_path)

def auto_click(template_path):
    """自动截屏，寻找目标并点击（保留用于单项功能的快速测试）"""
    print("📸 正在截取屏幕...")
    screen_path = get_screen()

    print(f"🔍 正在屏幕中寻找目标: {template_path} ...")
    result = find_image(screen_path, template_path, show_result=False)

    if result:
        max_loc, w, h = result
        center_x = max_loc[0] + (w // 2)
        center_y = max_loc[1] + (h // 2)
        
        print(f"🖱️ [底层输入] 准备移动到中心点 ({center_x}, {center_y}) 并点击...")
        pydirectinput.moveTo(center_x, center_y)
        pydirectinput.mouseDown()
        time.sleep(0.15) 
        pydirectinput.mouseUp()
        print("✅ 点击完成！\n")
        return True
    else:
        print("❌ 屏幕上未发现目标！\n")
        return False

if __name__ == "__main__":
    # 本地单独测试此模块时才会运行
    pass