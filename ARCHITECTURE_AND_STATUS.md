# Nikke Scanner Arcana — 架构与开发状态

> 最后梳理日期：2026-06-26  
> 技术栈：Python · OpenCV · PyDirectInput · MSS · Flask · Win32 API

---

## 1. 系统架构图 (System Architecture)

```
nikke-scanner-arcana/
│
├── app.py                          # 【入口 / Web 控制台】
│   ├── Flask 本地服务 (127.0.0.1:5000)
│   ├── F12 内核级急停 (pynput.Listener → os._exit)
│   ├── 启动序列：热更新检查 → 加载名录 → 自动打开浏览器
│   └── API：/api/config、/api/start → 拉起后台扫描线程
│
├── main_loop.py                    # 【导航与检索状态机 — 当前主流程】
│   ├── ESC 洗地 → 大厅 → 妮姬仓库（绝对寻址）
│   ├── 搜索框 Ctrl+V 剪贴板注入 + 武器类型二级筛选 (角色名|SR)
│   ├── 窗口比例盲点进入首位干员
│   └── 调度 equipment_scanner 完成装备扫描
│
├── main.py                         # 【已废弃】旧版「向下滚动 + 头像匹配」逻辑，未被 app 引用
│
├── config.py / config.example.py   # 热更新开关 HOT_UPDATE_ENABLED；config.py 不入库
├── nikke_index.json                # 干员名录 key → assets 文件夹 ID 映射（含 |武器 防重名）
├── user_settings.json              # 运行时持久化 Token（不入库）
│
├── templates/
│   └── index.html                  # 高对比度 Web 控制台：角色勾选 + Token 输入 + 启动确认
│
├── assets/
│   ├── avatars/{asset_id}/         # 角色封面图（default.png / skin*.png，现主要用于前端展示）
│   ├── ui/                         # 导航 UI 模板（搜索、筛选、武器类型、退出确认等）
│   ├── anchor_top.png              # 装备页双锚点：「小队」
│   ├── anchor_bottom.png           # 装备页双锚点：「全部解除」
│   ├── overload_logo.png           # T10 (OVERLOAD) 标识
│   ├── btn_close.png               # 装备详情关闭按钮（检测用，实际关闭走 ESC）
│   ├── current_screen.png          # 全屏截屏缓存
│   └── temp/                       # T10 词条截图临时目录（.gitignore）
│
├── core/
│   ├── vision.py                   # 【视觉引擎】多尺度灰度模板匹配；支持单图 / 文件夹盲扫
│   ├── capture.py                  # MSS 全屏截屏 + Win32 活动窗口裁剪 + auto_click 测试工具
│   ├── window_manager.py           # Win32 窗口抢占、多显示器居中、DPI 感知、get_window_rect
│   ├── equipment_scanner.py        # 【装备扫描】双锚点橡皮筋几何 → 四槽位 T10 检测 → 截图上传
│   ├── bot_client.py               # 【网络层】阿卡中枢 OCR API (X-API-KEY)，强制 NO_PROXY
│   ├── user_settings.py              # user_settings.json 读写（Token 持久化）
│   ├── nikke_index.py              # 名录加载 / 构建 / char_key → asset_id / search_name 解析
│   └── updater.py                    # GitHub 头像热更新（直连 → 国内镜像降级）
│
└── scripts/
    └── sync_avatars_index.py       # 一次性迁移脚本：旧文件夹命名 → 新 asset_id 规则
```

**模块依赖关系（运行时）：**

```
index.html ──POST /api/start──► app.py
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
           window_manager    main_loop.py    user_settings
                    │               │
                    │       ┌───────┴───────┐
                    │       ▼               ▼
                    │   capture.py    equipment_scanner.py
                    │       │               │
                    └───────┴─── vision.py ──┘
                                    │
                            bot_client.py ──► 阿卡中枢 API
```

---

## 2. 核心业务流 (Core Workflows)

### 2.1 应用启动

1. 执行 `app.py` → `run_startup_sequence()`。
2. `updater.check_and_update_avatars()`：若 `HOT_UPDATE_ENABLED=True`，从 GitHub 拉取缺失头像目录；有更新则 `os.execl` 重启进程。
3. `nikke_index.load_nikke_index()` 加载干员名录。
4. 1.5 秒后自动打开 `http://127.0.0.1:5000`；Flask 渲染角色卡片（数据来自 `nikke_index.json` + `assets/avatars`）。

### 2.2 前端触发 → 后端扫描线程

1. 用户在 Web 控制台勾选干员、填写阿卡 Token，点击 **EXECUTE SCAN_**。
2. SweetAlert2 二次确认后，`POST /api/start` 提交 `{ characters, token }`。
3. `app.py` 校验角色非空 → `save_token(token)` 写入 `user_settings.json`。
4. 启动 **daemon 线程**：`force_bring_to_front()` → `start_main_auto_flow(selected_characters)`。
5. 前端收到 success 后立即清空勾选；扫描在后台独立推进。

### 2.3 导航寻人（main_loop 状态机）

| 阶段 | 行为 |
|------|------|
| 窗口就绪 | `force_bring_to_front("胜利女神：新的希望")`：FindWindow → 多显示器居中 → TOPMOST 抢占焦点 |
| ESC 洗地 | 最多 40 次 ESC，直至：检测退出确认框（触底大厅）/ 已在仓库 / 超时失败 |
| 进入仓库 | 大厅下半区 ROI 匹配 `btn_nikke.png`（阈值 0.60）→ 点击 → 等待搜索图标出现 |
| 步骤 A | 点击放大镜 → 严格匹配 `search_box_active.png`（上部 ROI + 尺度过滤）→ 剪贴板粘贴角色主名 → Enter |
| 步骤 B | 若 key 含 `\|武器`（如 `小红帽\|SR`），打开筛选面板 → 点击 `weapon_{TYPE}.png` → ESC 关闭 |
| 步骤 C | 按窗口宽高比例 (11%W, 50%H) 盲点列表最左列首位 → 进入角色详情 |
| 清理 | 清除搜索框名称 + 按需重置武器筛选，为下一位干员准备纯净环境 |

### 2.4 装备截图（equipment_scanner）

1. 等待详情页加载，在右半屏 ROI 同时匹配 `anchor_top`（小队）与 `anchor_bottom`（全部解除）。
2. **双锚点橡皮筋**：校验垂直间距 ≥ 15% 屏高、水平偏移 ≤ 10% 屏宽，否则重试（最多 20 次）。
3. 按比例计算四装备槽坐标：`RATIO_TOP_TO_ROW1=0.38`、`RATIO_BOTTOM_TO_ROW2=0.23`。
4. 逐槽点击 → 等待弹窗 → 匹配 `overload_logo.png` 判定 T10。
5. 若为 T10：`capture_active_window()` 截取前台游戏窗口 → 存 `assets/temp/{角色}_T10_{部位}.png` → 调用上传。
6. **统一 ESC 关闭**装备详情（无论是否检测到 `btn_close.png`）→ 扫描完毕再 ESC 退回列表。

### 2.5 组装 Payload 上传（bot_client）

1. `get_token()` 从 `user_settings.json` 读取；空 Token 则跳过上传、不阻断扫描。
2. `POST http://moti.x3322.net:9983/third/bot/nikke/v1/identifyStatImageAndUpdate?characterName={name}`
   - Header：`X-API-KEY: {token}`（自动剥离 `Bearer ` 前缀）
   - Query：`characterName` 由 `get_search_name(char_key)` 解析（去 `|武器` 后缀，保留中文冒号）
   - Body：`multipart/form-data`，字段 `file`
   - `proxies={"http": None, "https": None}`，`timeout=15s`
3. 解析响应 `data.slotNo` / `slotName` / `statInfos[]`，终端打印词条摘要；本地槽位与 API 不一致时打警告。
4. 上传成功后自动删除 `assets/temp/` 对应该截图；任何网络/HTTP/业务失败均返回 `False`，主流程继续。

### 2.6 批量收尾

- 队列中每位干员：`process_single_character()` → 失败则 `_abort_character_search()` 自愈后跳过，继续下一位。
- 全部完成后打印 `[自动化结束]` 日志，并调用 `GET getUserStatInfo` 拉取云端词条库校验摘要。
- 后台线程自然退出（无回调通知前端）。

---

## 3. 防腐与容错机制 (Fault Tolerance)

### 3.1 全局安全

| 机制 | 位置 | 说明 |
|------|------|------|
| F12 急停 | `app.py` | pynput 内核监听，任意窗口按下 F12 → `os._exit(0)` 瞬间终止进程 |
| PyDirectInput FAILSAFE | `capture.py` | 鼠标甩至屏幕四角触发异常停止 |
| 启动前二次确认 | `index.html` | SweetAlert 警告用户勿操作键鼠，强调 F12 热键 |

### 3.2 窗口与坐标

| 机制 | 位置 | 说明 |
|------|------|------|
| 窗口未找到拦截 | `window_manager` / `main_loop` | `force_bring_to_front` 失败则整个流程终止 |
| DPI 感知 | `window_manager` | `SetProcessDPIAware()` 获取真实物理像素 |
| 多显示器居中 | `window_manager` | `MonitorFromWindow` + 工作区居中，兼容副屏负坐标 |
| 置顶失败降级 | `window_manager` | 异常时模拟 Alt 键再尝试 `SetForegroundWindow` |
| 窗口比例盲点 | `main_loop` | 首位干员坐标基于 `get_window_rect` 比例，弱回退至全屏比例 / 搜索框锚点 |

### 3.3 导航与状态重置

| 机制 | 位置 | 说明 |
|------|------|------|
| ESC 洗地上限 | `main_loop` | `MAX_ESC_WASH=40`，防止无限循环 |
| 退出确认框严格检测 | `main_loop` | 阈值 0.88 + 尺度 0.55~1.35x，过滤 0.2x 误匹配 |
| 大厅就绪双条件 | `main_loop` | 妮姬入口可见 **且** 无退出确认框，带 12s 超时等待 |
| 已在仓库跳过洗地 | `main_loop` | 搜索图标可见则直接进入检索，无需 ESC |
| 搜索失败自愈 | `_abort_character_search` | ESC → 清武器筛选 → 清搜索框 → 重新 `navigate_to_nikke_warehouse()` |
| 单角色失败不阻断队列 | `start_main_auto_flow` | 跳过当前干员，继续扫描下一位 |

### 3.4 视觉识别

| 机制 | 位置 | 说明 |
|------|------|------|
| 中文路径兼容 | `vision.py` | `cv2.imdecode(np.fromfile(...))` 避免 OpenCV 中文路径乱码 |
| 多尺度匹配 | `vision.py` | 默认 0.2~3.0x 线性 20 档；关键 UI 可收窄尺度范围 |
| 尺寸越界锁 | `vision.py` | 缩放后模板大于屏幕则跳过，防 matchTemplate 异常 |
| ROI 分区 | `main_loop` / `equipment_scanner` | 大厅按钮限下半屏；搜索框限上部 35%；锚点限右半屏 |
| 搜索框最小宽度 | `main_loop` | `SEARCH_BOX_MIN_WIDTH=80`，拒绝过小误命中 |
| 模板轮询重试 | `main_loop` | `_wait_for_template` 默认 8 次 × 0.8s 间隔 |
| 双锚点空间拓扑校验 | `equipment_scanner` | 垂直/水平距离不合理则丢弃并重扫 |
| ESC 替代点击关闭 | `equipment_scanner` / `main_loop` | 面板关闭、筛选面板退出、详情退回均优先 ESC |

### 3.5 网络与鉴权

| 机制 | 位置 | 说明 |
|------|------|------|
| 代理强制 bypass | `bot_client.py` / `updater.py` | `proxies={"http": None, "https": None}` 防系统代理超时 |
| Token 空值拦截 | `bot_client.py` | 无 Token 跳过上传与云端校验，扫描照常 |
| 上传失败不抛异常 | `bot_client.py` | 网络/HTTP/JSON/业务错误均 catch 并返回 False |
| 槽位交叉校验 | `bot_client.py` | API 返回 slotNo 与本地点击部位不一致时打 ⚠️ 警告 |
| 临时截图清理 | `bot_client.py` | 上传成功后删除对应 `assets/temp/` 文件 |
| 扫描结束云端校验 | `bot_client.py` / `main_loop.py` | `getUserStatInfo` 拉取全账号词条摘要，失败仅打日志 |
| 热更新通道降级 | `updater.py` | GitHub 直连 3s 超时 → ghproxy 镜像池 15s |
| 热更新全失败跳过 | `updater.py` | 不阻断应用启动 |
| Token 持久化 | `user_settings.py` | 读写失败时 load 返回 `{}`，不崩溃 |

### 3.6 前端校验

| 机制 | 位置 | 说明 |
|------|------|------|
| 空队列拒绝 | `app.py` | 未选角色返回 HTTP 400 |
| Token 启动时保存 | `app.py` | 每次扫描请求覆盖写入（可为空字符串） |

---

## 4. 下一步开发备忘录 (Next Steps)

### 4.1 遗留 / 冗余代码

| 项 | 说明 |
|----|------|
| **`main.py` 整文件** | 旧版「滚动翻页 + 多皮肤头像匹配」主控，已被 `main_loop.py` 完全替代；`app.py` 不再 import |
| **`app.py` 重复 import** | 同时 `import keyboard`（未使用）与 `from pynput import keyboard`（F12 监听实际使用后者） |
| **`config.py` 中 `NIKKE_BOT_TOKEN`** | 定义但全项目无引用；Token 实际来源为 Web 控制台 → `user_settings.json` |
| **`core/capture.py` → `auto_click()`** | 独立测试工具，主流程未调用 |
| **`core/nikke_index.py` → `get_search_name()`** | 已实现但 `main_loop` 自行 `_parse_char_name` 解析，函数未被引用 |
| **`main.py` 内联 `get_screen()`** | 与 `core/capture.py` 重复实现；legacy 文件自带副本 |
| **`assets/ui/warehouse_filter_icons.png`** | 资源存在，代码中无引用 |
| **`assets/template_test.png`** | 测试用模板，主流程未引用 |

### 4.2 架构演进中的未完成 / 盲点

| 项 | 说明 |
|----|------|
| **视觉引擎 Alpha Mask** | 当前 `vision.py` 为纯灰度多尺度匹配，未实现 Alpha 通道 Mask 加权；大厅妮姬入口依赖 ROI + 低阈值 (0.60) 而非透明背景 Mask 算法 |
| **前端封面路径** | `index.html` 图片 URL 使用 `char.name`（含 `\|` 的 key），而实际文件夹为 `asset_id`（如 `小红帽_SR`）；`app.py` 已用 `get_asset_id` 找封面，但模板渲染路径可能不匹配，部分角色卡片或无法显示头像 |
| **扫描完成无前端反馈** | 后台线程结束后 Web 控制台状态仍为「系统就绪」，无 WebSocket / 轮询通知进度或结果 |
| **热更新与本地命名分叉** | `HOT_UPDATE_ENABLED=False` 时 GitHub 仍用旧文件夹名；本地已通过 `sync_avatars_index.py` 迁移至 `角色_后缀` 规则，远端同步前不宜开启热更新 |
| **`build_nikke_index()` 不覆盖已有 JSON** | 若 `nikke_index.json` 已存在则跳过自动重建；新增 avatar 文件夹需手动维护 JSON 或跑 sync 脚本 |
| **游戏窗口标题硬编码** | `"胜利女神：新的希望"` 写死在 `window_manager.py`；国际服 / 其他语言客户端需配置化 |
| **截屏策略** | 主流程截全屏 (`mon=1`) 而非游戏窗口区域；多显示器 / 非全屏游戏时坐标依赖窗口居中假设 |
| **T10 截图范围** | `capture_active_window()` 截取当前前台窗口全帧，非装备弹窗局部 ROI；上传图片可能含多余 UI |
| **装备扫描失败返回** | 锚点未找到时 ESC 退回但 `process_single_character` 仍返回 `True`，队列不会触发自愈重导航 |
| **README 不完整** | `README.md` 安装说明在 `pip install` 行处截断，缺少完整依赖列表与运行步骤 |

### 4.3 名录与资源一致性

- `nikke_index.json` 支持 `角色名|武器类型` key（如 `小红帽|SR` → 文件夹 `小红帽_SR`）。
- Git 状态中可见大量 avatar 文件夹从中文冒号命名迁移为下划线命名（如 `尼恩：蓝色海洋` → `尼恩_蓝色海洋`），迁移脚本 `scripts/sync_avatars_index.py` 含 `LEGACY_FOLDER_TO_VALUE` 映射表。
- 武器类型 UI 资源已齐备：`weapon_AR/SR/SMG/SG/MG/RL.png`。

### 4.4 依赖清单（从 import 推断，README 未完整列出）

```
opencv-python, numpy, pydirectinput, mss, flask, pyperclip,
pynput, requests, pywin32, urllib3
```

---

## 附录：关键配置速查

| 配置项 | 文件 | 默认值 / 说明 |
|--------|------|---------------|
| `HOT_UPDATE_ENABLED` | `config.py` | `False`（远端命名同步前保持关闭） |
| Token 存储 | `user_settings.json` | Web 控制台写入，打包后在 `.exe` 同级 |
| 游戏窗口标题 | `window_manager.py` | `胜利女神：新的希望` |
| 阿卡 API（识别入库） | `bot_client.py` | `POST .../identifyStatImageAndUpdate?characterName=` |
| 阿卡 API（校验读库） | `bot_client.py` | `GET .../getUserStatInfo` |
| 急停热键 | `app.py` | `F12` |
| Flask 端口 | `app.py` | `5000` |
