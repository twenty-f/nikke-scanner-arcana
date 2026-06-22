import win32gui
import win32con
import win32process
import win32api
import ctypes
import time

# ⭐️ 核心修复：强行唤醒 Python 的系统级 DPI 感知能力，获取跨屏最真实的物理像素
try:
    ctypes.windll.user32.SetProcessDPIAware()
except:
    pass

def force_bring_to_front(window_title="胜利女神：新的希望"):
    """
    终极窗口抢占逻辑：带原生多显示器追踪、屏幕内居中、DPI感知和权限提权的强化版
    """
    print(f"🔍 正在系统进程中搜索: 【{window_title}】...")
    hwnd = win32gui.FindWindow(None, window_title)
    
    if not hwnd:
        print(f"⚠️ 未找到名为【{window_title}】的窗口！请确认游戏已开启且标题一致。")
        return False

    print("🎯 锁定目标窗口，正在强制接管显示器焦点...")
    
    user32 = ctypes.windll.user32
    current_thread = win32api.GetCurrentThreadId()
    window_thread, _ = win32process.GetWindowThreadProcessId(hwnd)

    # 1. 解除焦点锁定
    try:
        win32gui.SystemParametersInfo(
            win32con.SPI_SETFOREGROUNDLOCKTIMEOUT, 
            0, 
            win32con.SPIF_SENDWININICHANGE | win32con.SPIF_UPDATEINIFILE
        )
    except Exception:
        pass

    try:
        # 2. 挂载线程并唤醒窗口
        user32.AttachThreadInput(current_thread, window_thread, True)
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            
        # ==============================================================
        # ⭐️ 核心升级：原生多显示器追踪与当前屏幕居中对齐
        # ==============================================================
        rect = win32gui.GetWindowRect(hwnd)
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        
        try:
            # 智能探测：获取当前窗口所在的那个具体显示器的句柄 (MONITOR_DEFAULTTONEAREST)
            monitor_handle = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
            # 获取该显示器的具体信息（包括副屏的负坐标偏移和专属分辨率）
            monitor_info = win32api.GetMonitorInfo(monitor_handle)
            # 提取该显示器的工作区（已扣除该屏幕上的任务栏）
            screen_l, screen_t, screen_r, screen_b = monitor_info['Work']
        except Exception as e:
            print(f"⚠️ 多显示器探测失败，退回主屏幕模式: {e}")
            work_area = win32gui.SystemParametersInfo(win32con.SPI_GETWORKAREA)
            screen_l, screen_t, screen_r, screen_b = work_area

        screen_width = screen_r - screen_l
        screen_height = screen_b - screen_t

        # 核心算法：以当前屏幕的左上角 (screen_l, screen_t) 为基准进行居中偏移
        # 完美兼容副屏的负坐标系统！
        center_x = screen_l + (screen_width - width) // 2
        center_y = screen_t + (screen_height - height) // 2

        if abs(left - center_x) > 5 or abs(top - center_y) > 5:
            print(f"🧲 正在将游戏客户端强制校准至【当前所在屏幕】的正中心...")
            win32gui.SetWindowPos(
                hwnd, 0, center_x, center_y, 0, 0, 
                win32con.SWP_NOZORDER | win32con.SWP_NOSIZE
            )
            time.sleep(0.6) 
        # ==============================================================

        # 3. 顶层越权与前台设置
        win32gui.SetWindowPos(
            hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        )
        win32gui.SetWindowPos(
            hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, 
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        )
        win32gui.SetForegroundWindow(hwnd)

    except Exception as e:
        print(f"⚠️ 核心置顶流程发生底层异常: {e}")
        import pydirectinput
        pydirectinput.press('alt')
        try:
            win32gui.SetForegroundWindow(hwnd)
        except:
            pass
        
    finally:
        try:
            user32.AttachThreadInput(current_thread, window_thread, False)
        except:
            pass
        
    time.sleep(1.5) 
    print("✅ 窗口位置校验通过！已接管显示焦点。")
    return True

def get_window_rect(window_title="胜利女神：新的希望"):
    """
    获取目标窗口在整个跨屏虚拟桌面上的真实绝对坐标
    """
    hwnd = win32gui.FindWindow(None, window_title)
    if not hwnd:
        return None
        
    try:
        rect = win32gui.GetWindowRect(hwnd)
        left = rect[0]
        top = rect[1]
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        
        return (left, top, width, height)
    except Exception as e:
        print(f"⚠️ 获取窗口尺寸失败: {e}")
        return None