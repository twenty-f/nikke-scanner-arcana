# 项目工程简报 · Nikke Scanner Arcana

> 最后更新：2026-06-29  
> 文档版本：1.0  
> 维护说明：intake 确认、栈变更、测试/安全策略升级、架构大改时更新。

## 1. 项目目的与范围

- **要解决的问题**：PC 版《胜利女神：Nikke》妮姬仓库中，自动搜索干员、进入详情、识别 T10（OVERLOAD）装备并截图，可选上传至阿卡中枢 OCR API。
- **不在范围内**：游戏内战斗自动化、非 T10 分析、国际服客户端适配（未验证）、云端头像热更新默认关闭时的远端同步。
- **成功标准**：
  - Web 控制台勾选干员 → 自动导航至仓库 → 搜索（含 `角色名|武器` 筛选）→ 扫描四槽 → 本地截图；配置 Token 后上传成功。
  - 多干员连续扫描时：搜索栏复用、武器筛选正确重置/切换。
  - 打包版 `NikkeScanner_Beta_v4` 在 Windows 上可独立运行。

## 2. 利益相关与约束

- **使用者 / 维护者**：本人及群友测试；后续可能他人接手自动化开发。
- **时间约束**：功能已可跑通；`main_loop` 已拆分为 orchestrator / navigation / search（P1 完成）。
- **运行环境**：Windows 10+；游戏窗口标题 **「胜利女神：新的希望」**；建议 16:9 窗口化（1596×928 等）；Flask `127.0.0.1:5000`。

## 3. 技术栈选择

| 层级 | 选择 | 备选/未采用 | 理由 |
|------|------|-------------|------|
| 语言 | Python 3.9 | — | 视觉自动化生态成熟 |
| 视觉/输入 | OpenCV、PyDirectInput、MSS | PyAutoGUI | 项目已统一 vision + 窗口裁剪 |
| Web 控制台 | Flask + `templates/index.html` | Electron | 轻量本地控制台 |
| 窗口控制 | pywin32 | — | 置顶、居中、rect |
| 打包 | PyInstaller（`NikkeScanner_Beta_v4.spec`） | 单文件 exe | 含 assets/templates |
| 配置 | `config.py`（热更新开关）、`user_settings.json`（Token） | 环境变量 alone | Token 由 Web 写入 |
| 名录 | `nikke_index.json` + `assets/avatars/` | 纯文件夹扫描 | 支持 `\|SR` 等 key |

## 4. 架构与工程原则（本项目）

- **模块/目录约定**：
  - `app.py`：Flask、API、扫描线程启动
  - `core/orchestrator.py`：扫描队列编排
  - `core/navigation/`：大厅 → 仓库导航
  - `core/search/`：搜索栏、武器筛选、单干员编排
  - `main_loop.py`：兼容 re-export（可选）
  - `core/`：vision、capture、window_manager、equipment_scanner、bot_client、aspect_layout 等
- **编排与实现分离（目标态）**：
  - 编排：`process_single_character`、队列清理
  - 实现：模板匹配、ROI、`core/game_screen.py` 统一坐标（**P0 已完成**）
  - 筛选重置：`core/search/filter.py` + `core/search/locators.py`
- **须遵守的 Skill**：
  - [x] engineering-core
  - [x] testing-engineering（L1；截图回归待建）
  - [x] security-engineering（L1：Token 不入库）
  - [x] python-engineering
- **项目文档**：`ARCHITECTURE_AND_STATUS.md`（模块现状）；本文件（选择与约束）

- **关键 UI 不变量**（勿破坏）：
  - 行1：搜索开关 / Burst / 筛选；行2：搜索框 + 执行放大镜；**重置筛选**在执行放大镜正下方。
  - 坐标必须基于 **游戏窗口裁剪**，禁止全屏比例混用。
  - 上一位有武器筛选时，下一位搜索前须 **重置筛选**。

## 5. 测试策略

- **级别**：**L1 轻量**（L2 截图回归脚本规划中）
- **框架与命令**：
  - 开发：`python app.py` → 浏览器控制台手动验收
  - 打包：`dist/NikkeScanner_Beta_v4/NikkeScanner_Beta_v4.exe`
  - Token：`POST /api/token/verify`
- **必跑场景 / 回归方式**：
  1. 单干员无武器筛选（如 伊芙）
  2. 带武器筛选（如 海伦\|SR）→ 下一位（如 桃乐丝\|AR）须先重置筛选再搜
  3. 搜索栏展开后聚焦**第二行输入框**，勿误点 Burst 行
- **CI**：无（待 GitHub 仓库建立后可加）

## 6. 安全与合规

- **级别**：**L1**
- **敏感数据**：阿卡 API Token 存 `user_settings.json`（**.gitignore**）；禁止提交 `config.py` 含密钥
- **信任边界**：本地 Flask 仅监听本机；阿卡 API 使用 `X-API-KEY`；`NO_PROXY` 直连
- **已知风险与待办**：
  - F12 急停 `os._exit` 硬终止
  - 全屏截屏 + 窗口居中假设；多显示器需验证
  - 上传失败不阻断扫描（仅 warn）

## 7. 协作与自动化

- **Git / 分支约定**：待 GitHub 远程仓库创建后首次 push；见下方「云端备份」说明
- **打包/发布**：`python -m PyInstaller NikkeScanner_Beta_v4.spec` → `dist/NikkeScanner_Beta_v4.zip`
- **Agent 接手提示**：
  1. 先读 **本文件** + `ARCHITECTURE_AND_STATUS.md`
  2. 改搜索/筛选逻辑 → `main_loop.py`、`core/aspect_layout.py`
  3. 勿删 `nikke_index.json`；打包时复制到 exe 同级
  4. 遵循 `engineering-intake`；大改前更新本简报

## 8. 当前状态与下一步

- **已完成**：
  - 搜索/武器筛选/重置筛选流程（海伦→桃乐丝多干员）
  - Web「测试 Token」、`/api/token/verify`
  - PyInstaller v4 打包
- **进行中**：
  - 截图离线验证脚本（搜索/重置坐标）
- **明确不做**（当前版本）：
  - 恢复 `main.py` 滚动头像匹配主流程
  - 默认开启 GitHub 头像热更新（远端命名未对齐）

## 9. 变更记录

| 日期 | 版本 | 变更摘要 | 确认 |
|------|------|----------|------|
| 2026-06-29 | 1.0 | 初版：固化栈、不变量、测试/安全 L1、打包 v4 | 用户确认 intake |

## 附录：云端备份（待办）

GitHub 远程仓库**尚未创建**。用户确认后将：

1. 在 GitHub 新建仓库  
2. `git remote add origin …`  
3. 推送含 `docs/PROJECT_CHARTER.md` 与工程 Skill 引用说明的分支  

届时更新本节为实际 remote URL 与默认分支名。
