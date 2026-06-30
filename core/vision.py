import cv2
import numpy as np
import os

def find_image(screen, template_target, threshold=0.75, show_result=False, min_scale=0.2, max_scale=3.0, silent=False):
    """
    通用多尺度图像识别模块（终极版）：
    1. 中文路径免乱码机制
    2. 多尺度动态扫描抗分辨率形变
    3. ⭐️ 原生支持【文件夹多模板盲扫】！
    """
    # 1. 解析屏幕截图
    if isinstance(screen, str):
        if not os.path.exists(screen) or os.path.isdir(screen):
            return None
        screen = cv2.imdecode(np.fromfile(screen, dtype=np.uint8), cv2.IMREAD_COLOR)
        
    if screen is None:
        return None
        
    # 2. 转换为灰度图 (针对截屏只需要做一次，节约算力)
    try:
        if len(screen.shape) == 3:
            gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        else:
            gray_screen = screen
    except Exception as e:
        print(f"⚠️ 屏幕灰度转换失败: {e}")
        return None

    # ==============================================================
    # ⭐️ 核心升级：构建待匹配模板池 (智能识别是文件还是文件夹)
    # ==============================================================
    templates_to_check = []
    
    if os.path.isdir(template_target):
        # 如果传入的是角色文件夹，提取里面所有的图片
        for file_name in os.listdir(template_target):
            if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                templates_to_check.append(os.path.join(template_target, file_name))
        if not templates_to_check:
            print(f"⚠️ 警告：文件夹 {template_target} 中没有任何图片！")
            return None
    elif os.path.exists(template_target):
        # 如果传入的是单张图片，直接放入池子
        templates_to_check.append(template_target)
    else:
        return None

    global_best_match = None

    # ==============================================================
    # 3. 遍历所有模板，执行多尺度扫描大乱斗
    # ==============================================================
    for t_path in templates_to_check:
        template = cv2.imdecode(np.fromfile(t_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if template is None:
            continue
            
        try:
            if len(template.shape) == 3:
                gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            else:
                gray_template = template
        except:
            continue

        # 对当前这张图片进行多尺度扫描（默认 0.2x ~ 3.0x，可按场景收窄）
        screen_h, screen_w = gray_screen.shape[:2]
        for scale in np.linspace(min_scale, max_scale, 20):
            width = int(gray_template.shape[1] * scale)
            height = int(gray_template.shape[0] * scale)

            if width == 0 or height == 0:
                continue

            resized_template = cv2.resize(gray_template, (width, height))

            # 尺寸越界锁：防止缩放后模板大于背景导致 matchTemplate 异常
            if resized_template.shape[1] > screen_w or resized_template.shape[0] > screen_h:
                continue

            result = cv2.matchTemplate(gray_screen, resized_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            # 只要发现得分更高的，就刷新全场最高分记录
            if global_best_match is None or max_val > global_best_match['max_val']:
                global_best_match = {
                    'max_val': max_val,
                    'max_loc': max_loc,
                    'width': width,
                    'height': height,
                    'scale': scale,
                    'file_name': os.path.basename(t_path)
                }

    # ==============================================================
    # 4. 最终裁决
    # ==============================================================
    if global_best_match and global_best_match['max_val'] >= threshold:
        # 如果需要打印日志，这行代码会告诉你到底命中了哪个皮肤、缩放了多少倍
        if show_result:
            pass # 保持静默，因为你的 main_loop.py 似乎有自己的打印逻辑
        
        # 你的日志里出现过 "✨ 多模板盲扫：成功匹配到【尼恩：蓝色海洋】的皮肤图片"，
        # 为了找回那种感觉，我在这里加一句内部打印：
        if not silent:
            pass  # 静默模式：命中细节不输出，减少终端噪音
        
        return (global_best_match['max_loc'], global_best_match['width'], global_best_match['height'])
        
    return None


def find_leftmost_image(
    screen,
    template_target,
    threshold=0.75,
    min_scale=0.2,
    max_scale=3.0,
    max_rel_x=None,
    silent=False,
):
    """
    在 screen 中取所有超过 threshold 的匹配，返回最左侧的一个。
    max_rel_x：匹配中心 x / screen 宽度 的上限（用于搜索开关等靠左 UI）。
    """
    if isinstance(screen, str):
        if not os.path.exists(screen) or os.path.isdir(screen):
            return None
        screen = cv2.imdecode(np.fromfile(screen, dtype=np.uint8), cv2.IMREAD_COLOR)

    if screen is None:
        return None

    try:
        gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY) if len(screen.shape) == 3 else screen
    except Exception:
        return None

    templates_to_check = []
    if os.path.isdir(template_target):
        for file_name in os.listdir(template_target):
            if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                templates_to_check.append(os.path.join(template_target, file_name))
    elif os.path.exists(template_target):
        templates_to_check.append(template_target)
    else:
        return None

    candidates = []
    screen_h, screen_w = gray_screen.shape[:2]

    for t_path in templates_to_check:
        template = cv2.imdecode(np.fromfile(t_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if template is None:
            continue
        try:
            gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if len(template.shape) == 3 else template
        except Exception:
            continue

        for scale in np.linspace(min_scale, max_scale, 20):
            width = int(gray_template.shape[1] * scale)
            height = int(gray_template.shape[0] * scale)
            if width == 0 or height == 0:
                continue
            resized_template = cv2.resize(gray_template, (width, height))
            if resized_template.shape[1] > screen_w or resized_template.shape[0] > screen_h:
                continue

            result = cv2.matchTemplate(gray_screen, resized_template, cv2.TM_CCOEFF_NORMED)
            loc = np.where(result >= threshold)
            for lx, ly in zip(loc[1], loc[0]):
                score = float(result[ly, lx])
                center_x = lx + width // 2
                if max_rel_x is not None and center_x / screen_w > max_rel_x:
                    continue
                candidates.append((center_x, score, lx, ly, width, height))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], -item[1]))
    _, _, lx, ly, width, height = candidates[0]
    return ((lx, ly), width, height)