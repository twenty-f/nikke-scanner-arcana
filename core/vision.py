import cv2
import numpy as np
import os

def cv_imread(file_path):
    """⭐️ 专治各种 OpenCV 不支持中文路径的绝招"""
    # 先用 numpy 按字节读取，再让 OpenCV 解码，完美绕过中文路径报错
    img = cv2.imdecode(np.fromfile(file_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    return img

def find_image(main_img_path, template_path, threshold=0.8, show_result=False):
    """
    视觉核心：寻找目标
    :param template_path: 可以是一个具体图片路径，也可以是一个头像文件夹路径
    """
    if not os.path.exists(main_img_path):
        print("⚠️ 找不到主图文件，请检查路径！")
        return None

    # 如果 template_path 是文件夹，则进行多模板盲扫
    if os.path.isdir(template_path):
        return _multi_template_match(main_img_path, template_path, threshold)
    
    # 否则，走之前的单图匹配逻辑
    if not os.path.exists(template_path):
        print(f"⚠️ 找不到目标图片: {template_path}，请检查！")
        return None
    return _single_template_match(main_img_path, template_path, threshold, show_result)

def _single_template_match(main_img_path, template_img_path, threshold, show_result):
    # ⭐️ 替换为支持中文的读取方式
    main_img = cv_imread(main_img_path)
    template = cv_imread(template_img_path)
    
    # 防御性编程：防止图片损坏或读取失败导致 NoneType 报错
    if main_img is None or template is None:
        return None

    h, w = template.shape[:2]

    result = cv2.matchTemplate(main_img, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= threshold:
        if show_result:
            top_left = max_loc
            bottom_right = (top_left[0] + w, top_left[1] + h)
            cv2.rectangle(main_img, top_left, bottom_right, (0, 0, 255), 2)
            cv2.imshow("Match Result (Press any key to close)", main_img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            
        return max_loc, w, h
    else:
        return None

def _multi_template_match(main_img_path, template_dir, threshold):
    """⭐️ 核心升级：文件夹盲扫多皮肤逻辑"""
    skin_files = [f for f in os.listdir(template_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
    
    if not skin_files:
        return None
        
    best_match = None
    max_best_val = -1.0
    
    # 挨个皮肤试一遍
    for skin in skin_files:
        full_skin_path = os.path.join(template_dir, skin)
        result = _single_template_match(main_img_path, full_skin_path, threshold, show_result=False)
        
        if result:
            # ⭐️ 同样替换为支持中文的读取方式
            main_img = cv_imread(main_img_path)
            template = cv_imread(full_skin_path)
            
            if main_img is None or template is None:
                continue

            res = cv2.matchTemplate(main_img, template, cv2.TM_CCOEFF_NORMED)
            _, current_val, _, _ = cv2.minMaxLoc(res)
            
            if current_val > max_best_val:
                max_best_val = current_val
                best_match = result
                
    if best_match:
        print(f"✨ 多模板盲扫：成功匹配到【{os.path.basename(template_dir)}】的皮肤图片，最佳匹配度: {max_best_val:.2f}")
        return best_match
    return None

if __name__ == "__main__":
    pass