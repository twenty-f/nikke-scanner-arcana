import win32gui
import win32con
import win32process
import win32api
import ctypes
import time

def force_bring_to_front(window_title="胜利女神：新的希望"):
    """
    终极窗口抢占逻辑：绕过 Windows 限制，强制将游戏拉到最前 (安全隔离版)
    """
    print(f"🔍 正在系统进程中搜索: 【{window_title}】...")
    hwnd = win32gui.FindWindow(None, window_title)
    
    if not hwnd:
        print(f"⚠️ 未找到名为【{window_title}】的窗口！请确认游戏已开启且标题一致。")
        return False

    print("🎯 锁定目标窗口，正在强制接管显示器焦点...")
    
    # 引入 Windows 底层 API
    user32 = ctypes.windll.user32
    
    # 获取当前 Python 脚本的线程 ID 和游戏窗口的线程 ID
    current_thread = win32api.GetCurrentThreadId()
    window_thread, _ = win32process.GetWindowThreadProcessId(hwnd)

    # 1. ⭐️ 隔离全局配置修改：即使拒绝访问，也绝不影响后续核心置顶流程
    try:
        win32gui.SystemParametersInfo(win32con.SPI_SETFOREGROUNDLOCKTIMEOUT, 0, win32con.SPIF_SENDWININICHANGE | win32con.SPIF_UPDATEINIFILE)
    except Exception:
        # 静默跳过，普通权限运行程序时通常会走到这里
        pass

    try:
        # 2. 将当前脚本的输入处理机制“挂载”到游戏窗口上
        user32.AttachThreadInput(current_thread, window_thread, True)

        # 3. 检查窗口状态，如果是最小化则还原，否则直接显示
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        
        # 4. 把窗口拔高到最顶层（TOPMOST），然后再取消最顶层状态，确保它能越过所有其他软件
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
        win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
        
        # 5. 正式设置为前台活动窗口
        win32gui.SetForegroundWindow(hwnd)

    except Exception as e:
        print(f"⚠️ 核心置顶流程发生底层调用异常: {e}，尝试启用键盘唤醒备用方案...")
        # 备用方案：模拟按下 Alt 键唤醒系统焦点感知
        import pydirectinput
        pydirectinput.press('alt')
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception as e_alt:
             print(f"⚠️ 备用置顶方案也失败了: {e_alt}")
        
    finally:
        # 6. 解除线程挂载
        try:
            user32.AttachThreadInput(current_thread, window_thread, False)
        except:
            pass
        
    time.sleep(1.5) # 给画面渲染和切换留出时间
    print("✅ 窗口接管尝试完成！准备执行后续操作。")
    return True