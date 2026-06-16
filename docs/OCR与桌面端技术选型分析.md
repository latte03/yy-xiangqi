# 象棋残局 OCR 识别 + 桌面端打包 技术选型分析

> 适用项目：xiangqi-endgame（Vue 3 + Vite + TS + Konva + naive-ui + Pinia + fairy-stockfish-nnue.wasm）
> 目标：①自定义残局新增「截图识别自动布局」；②引入本地后端保证识别效率/准确性；③将应用打包为跨平台桌面 App
> 输入来源（已确认）：**仅《燕云十六声》游戏内象棋盘**——游戏截图，或手机翻拍游戏画面/屏幕（**单一皮肤**）
> 目标平台（已确认）：Windows（主）+ macOS；后端可用 Python
> 日期：2026-06-16

---

## 0. 结论速览（TL;DR）

| 决策点 | 推荐方案 | 一句话理由 |
|---|---|---|
| 桌面框架 | **Tauri 2** | 复用现有 Vue 前端，使用系统 WebView，壳体通常明显小于 Electron；最终包体主要取决于 Python 后端 |
| 后端形态 | **本地 sidecar 进程**（Python + FastAPI，PyInstaller 打包） | 离线可用、随 App 分发；Tauri 支持嵌入并启动外部二进制，健康检查/重启/关闭清理由应用实现 |
| 识别核心 | **不是通用 OCR，而是「棋盘定位 + 棋格分类」** | 单一固定皮肤，定位+分类比文字 OCR 更准更快更小 |
| 分类模型 | **小型 CNN/ONNX**（多背景合成训练） | 棋盘半透明、底色随场景变，CNN 比模板更稳；当前实施已决定直接走模型 |
| OCR 兜底 | **基本不需要** PaddleOCR | 单一皮肤场景下无陌生汉字识别需求，可省掉这块重依赖 |

核心判断：**这个任务的难点不在「OCR」三个字，而在「把棋盘网格切出来 + 判断每格是哪个子」。** 想清楚这点，方案会简单很多。

> ⭐ **范围已大幅收窄**：只服务《燕云十六声》一种棋盘皮肤。这意味着——棋子样式、配色、棋盘布局全部固定且已知。
> - **游戏截图**：结构稳定，适合直接用小型 CNN 覆盖；识别后保留人工纠正。
> - **手机翻拍游戏画面**：唯一稍难的场景（透视、屏幕反光、摩尔纹），但仍是同一皮肤，用「合成数据 + 少量真实翻拍样本」训练一个小 CNN 即可稳定覆盖。
> 因此整体复杂度比通用方案低很多，PaddleOCR 这类重型 OCR **基本用不上**。

---

## 1. 识别方案分析（最关键的部分）

### 1.1 为什么不要一上来就上「通用 OCR」

通用 OCR（Tesseract/PaddleOCR）是为「任意排版的文字」设计的。但象棋残局图有非常强的结构先验：

- 棋盘是固定的 **9 列 × 10 行 = 90 个交叉点**；
- 棋子只有 **14 种**（红：帥仕相俥傌炮兵；黑：將士象車馬砲卒）+ 空位，共 15 类；
- App 截图里棋子是规整的圆盘，背景、字体、配色在同一皮肤内完全一致。

直接对整张图跑文字 OCR，会遇到：定位不到底是哪个交叉点、圆盘描边/底纹干扰、"将/帅"等字形相近误判、空位无法表达等问题。**把它当成「90 个格子的图像分类问题」远比「文字识别问题」简单且可靠。**

### 1.2 推荐的识别流水线（Pipeline）

```
截图输入
  │
  ├─ ① 棋盘定位 (Board Localization)
  │     - 检测棋盘外框/网格线 (OpenCV: 边缘检测 + 霍夫直线 / 轮廓最大矩形)
  │     - 对 App 截图：通常可用固定比例裁剪 + 棋盘锚点辅助定位
  │     - 透视校正 (warpPerspective) → 得到正方形/标准长宽的棋盘
  │
  ├─ ② 切分 90 个交叉点 (Grid Slicing)
  │     - 已知 9×10 网格 → 按比例切出每个交叉点周围的小图块
  │
  ├─ ③ 每格分类 (Cell Classification) ← 准确率核心
  │     - 小型 CNN/ONNX：15 分类，合成数据 + 真实裁剪训练（当前实施路线）
  │
  └─ ④ 输出 FEN / 内部布局格式 → 填入自定义残局编辑器
```

第 ④ 步要和现有代码对接：象棋有通用的 **FEN 记法**（fairy-stockfish 本身就吃 FEN），识别结果直接产出 FEN，能无缝复用现有引擎与棋盘渲染逻辑，几乎不用改核心。

### 1.3 三种分类方案对比

| 方案 | 游戏截图 | 手机翻拍游戏画面 | 实现难度 | 体积 | 适用阶段 |
|---|---|---|---|---|---|
| **模板匹配**（OpenCV matchTemplate / 特征点） | 单图可用，跨图弱 | 中（透视/反光会降准） | ★☆☆ 低 | 极小 | 已废弃，不作为运行时路线 |
| **小型 CNN → ONNX**（15 分类） | 高 | 高（需含翻拍样本训练） | ★★☆ 中 | 小（量化后 1–5MB） | 当前唯一运行时路线 |
| **通用 OCR**（PaddleOCR） | — | — | ★★☆ 中 | 重（50–200MB+） | 本项目不需要 |

**当前落地顺序**：直接训练小型 CNN 并导出 ONNX，作为运行时唯一分类器。训练数据由「程序化合成棋子」+「真实截图裁剪」组成，叠加随机透视/亮度/反光/摩尔纹生成大量样本。因为皮肤唯一，CNN 几乎可「程序化无限生成」训练数据，泛化压力相对可控。

### 1.4 从实际截图得到的《燕云十六声》专属观察

（基于一张「王大演的棋局」游戏截图）

- **棋盘是半透明叠层**：棋盘面板叠在游戏 3D 场景之上，背景会透出，不同关卡/场景底色不同。→ 不能用固定像素坐标 + 固定底色硬匹配；**必须先做棋盘定位**，且分类模型要用「多背景合成」训练以抗底色变化。
- **棋子高对比、易分**：圆盘偏亮且不透明度高，红子=红字、黑子=黑/深字，**靠字色区分红黑**（取红色通道即可）。字区受背景透出影响小，是稳定的判别区域。
- **分辨率/缩放会变**：用户可能在 1080p / 2K / 超宽屏 / 手机截图，面板随之缩放。→ 必须**检测棋盘外框 + 网格线 + 九宫斜线**来定位，禁止写死坐标。好在该棋盘矩形外框、九宫「米」字线很清晰，定位锚点充足。
- **字形为标准 7 类/方**：帅将、仕士、相象、车車、马馬、炮砲、兵卒，与通用象棋一致，**FEN 对接无障碍**。
- **视角不翻转（已确认）**：红方恒在下，游戏内几乎不出现黑方在下。→ **无需朝向归一化**，定位后直接按固定方向映射到 90 个交叉点。
- **透出背景较暗且一致（已确认）**：棋盘面板背景在各残局间基本一致、偏暗。→ 多底色干扰比预想小，**截图场景圆盘/字区很稳定**。

#### 两类输入、两套难度（基于三张样例）

| 输入类型 | 样例特征 | 难度 | 处理要点 |
|---|---|---|---|
| **游戏截图**（PC/手机原生截图） | 棋盘正对、清晰、底色一致 | 低 | 检测外框→切 90 格→CNN 分类；识别后人工核对 |
| **手机翻拍屏幕**（拍笔记本/显示器） | 梯形透视、屏幕高光反光、摩尔纹、偏灰、可能有手指遮挡 | 高 | **四角透视校正 (warpPerspective)** → CNN（带透视/高光/摩尔纹/白平衡增强训练）；遮挡格需人工补 |

> 据此最终结论：**截图路和翻拍路统一走轻量 CNN/ONNX**；**翻拍路是工作量重心**，必须做透视校正 + 抗高光/摩尔纹的数据增强。两路共用同一套「定位→切格→分类→FEN」骨架，只是定位与增强强度不同。

### 1.5 关于 PaddleOCR

由于只服务单一游戏皮肤、不存在识别陌生汉字的需求，**本项目不需要 PaddleOCR**，可省掉这块重依赖。仅作知识备查：PaddleOCR 官方 PP-OCRv5 面向多场景文字识别，支持简体中文、繁体中文、英文、日文等文字类型；若将来要扩展到任意象棋 App、印刷棋谱或真实棋盘照片，再考虑作为可选识别后端引入。

---

## 2. 后端形态分析

你的诉求是「保证 OCR 高效准确」，并已选定**本地后端进程**。这是对的——把 OpenCV / ONNX 推理放进后端，比在前端 wasm 里硬跑更省心、更快、生态更全。

### 2.1 后端语言选型

| 语言 | CV/OCR 生态 | 实现难度 | 与打包配合 | 评价 |
|---|---|---|---|---|
| **Python + FastAPI**（推荐） | 最强（OpenCV、PaddleOCR、ONNX Runtime、PyTorch 训练全在 Python） | 低 | PyInstaller 打成单二进制，作 Tauri sidecar | **首选**，训练与推理同语言，迭代快 |
| Rust（Tauri 原生） | 一般（opencv-rust 绑定可用，OCR 生态弱） | 高 | 无需 sidecar，直接进主进程，体积最小 | 体积/性能最佳，但开发成本高 |
| Node.js | 中（opencv4nodejs / onnxruntime-node） | 中 | 可作 sidecar，但 CV 生态不如 Python | 折中，但不如 Python 顺手 |

**推荐 Python + FastAPI**：模型训练用 Python，推理也用 Python，零语言切换；OpenCV/ONNX/PaddleOCR 一应俱全。用 PyInstaller 打成单文件二进制，作为 Tauri 的 sidecar 分发，**用户无需安装 Python 环境，离线可用**。

### 2.2 通信方式

前端（WebView）↔ 后端（sidecar）走 **本地 HTTP（127.0.0.1:随机端口）** 或 stdin/stdout。HTTP 最直观：前端把截图 POST 给 `/recognize`，后端返回 FEN + 置信度 + 每格分类结果。

HTTP 方式建议补齐这些工程细节：

- 后端仅监听 `127.0.0.1`，不要监听 `0.0.0.0`。
- 端口由主进程分配随机空闲端口，避免固定端口被占用。
- Tauri 启动 sidecar 后做 `/health` 轮询，确认服务 ready 后再开放 OCR UI。
- 请求附带一次性或会话级 token，降低本机其他进程误调用接口的概率。
- sidecar 崩溃时提示用户重试，并由主进程负责重启。
- App 退出、返回首页或 OCR 页面销毁时，确保关闭 sidecar 或取消正在进行的任务。

如果后续想进一步降低本地 HTTP 暴露面，也可以切到 stdin/stdout 协议；但调试体验和前后端解耦会比 HTTP 差一些。

### 2.3 代价提醒

引入 Python sidecar 是体积的主要来源：**PyInstaller 打包后，纯 OpenCV+ONNX 的后端通常会到几十 MB；若带上 PaddleOCR，体积会显著上升**。具体大小取决于 Python 版本、平台、OpenCV/ONNX Runtime 构建方式、是否单文件打包、是否包含调试符号等，需要以阶段一原型的实际产物为准。

这也是为什么建议「主力用轻量 CNN、PaddleOCR 仅按需」——能把后端体积控制在小工具可以接受的范围内。

---

## 3. 桌面打包框架分析

### 3.1 Tauri 2 vs Electron 核心对比

| 维度 | **Tauri 2**（推荐） | Electron |
|---|---|---|
| 渲染层 | 复用操作系统 WebView（Windows 为 WebView2） | 内置 Chromium + Node.js |
| 安装包体积 | 壳体通常较小；最终包体主要由 Python sidecar、模型和 Windows WebView2 安装策略决定 | 壳体通常较大，因为自带 Chromium/Node.js |
| 内存占用 | 低 | 高（每个窗口一套 Chromium） |
| 后端 | Rust 主进程 + sidecar（可放 Python） | Node.js 主进程，直接跑 JS 后端 |
| 复用现有 Vue 前端 | ✅ 直接复用 Vite 产物 | ✅ 直接复用 |
| 跨平台 | Win / macOS / Linux（+移动端实验性） | Win / macOS / Linux |
| 上手难度 | 中（需少量 Rust 配置；业务逻辑可全在前端+Python） | 低（纯 JS 团队最熟） |
| 主要风险 | 各平台 WebView 兼容性、sidecar 权限配置、签名/公证、WebView2 分发策略 | 体积大、资源占用高 |

Tauri 的优势不是某个固定数字，而是架构上不把 Chromium 打进应用本体；Electron 官方定位就是把 Chromium + Node.js 嵌入二进制，因此天然更重。对一个象棋小工具，优先控制壳体体积是合理的，Tauri 更符合目标。

### 3.2 为什么推荐 Tauri 2

1. **包体更容易控制**：你的前端是 Vite 产物，Tauri 直接复用；总体积主要由 Python sidecar、模型文件和 WebView2 分发策略决定。
2. **跨平台**：Win/macOS/Linux 一套代码，三端打包。
3. **sidecar 模式契合本地后端**：Tauri 2 支持嵌入外部二进制并通过 shell plugin 启动 sidecar。需要在 capabilities 中明确授权 `execute/spawn` 权限，生命周期管理、健康检查、崩溃重启由应用层实现。
4. **对你的改造量小**：前端几乎不动，新增一个「上传截图→调本地接口→拿 FEN→填入残局编辑器」的功能模块即可。

### 3.3 Tauri 的代价（需知晓）

- 需要装 Rust 工具链来构建（仅开发/打包阶段，最终用户无感）。
- 各平台 WebView 行为可能有细微差异，需三端各测一遍。
- Windows 依赖 Microsoft Edge WebView2。Windows 11 通常预装；旧系统可由安装器处理。如果选择离线内置 WebView2，会显著增加安装包体积。
- Windows 分发如果不做代码签名，会遇到 SmartScreen 信任提示；macOS 对外分发需要签名和公证。这些不是技术阻断，但要计入发布计划。
- Rust 侧主要写「拉起 sidecar、端口协商、健康检查、退出清理」这类胶水代码，不需要深入 Rust 业务逻辑。

> 如果你完全不想碰 Rust、且不在意体积，Electron 是更省心的兜底；但综合体积、跨平台、与本地后端的契合度，**Tauri 2 是更优解**。

---

## 4. 推荐总体架构

```
┌─────────────────────────────────────────────┐
│            Tauri 2 桌面应用 (Win/macOS/Linux)  │
│                                               │
│   ┌─────────────────────────────────────┐    │
│   │  WebView：现有 Vue3 前端              │    │
│   │  - 棋盘渲染 (Konva)                   │    │
│   │  - fairy-stockfish-nnue.wasm 引擎     │    │
│   │  - 【新增】截图识别页：上传图→显示结果 │    │
│   └───────────────┬─────────────────────┘    │
│                   │ localhost HTTP            │
│   ┌───────────────▼─────────────────────┐    │
│   │  Python sidecar (FastAPI, PyInstaller)│    │
│   │  ① 棋盘定位 (OpenCV)                  │    │
│   │  ② 切 90 格                          │    │
│   │  ③ 分类：CNN-ONNX                   │    │
│   │  ④ 输出 FEN                          │    │
│   └─────────────────────────────────────┘    │
│         Rust 主进程：启动 sidecar / 分配端口 / 健康检查 / 退出清理 │
└─────────────────────────────────────────────┘
```

预估安装包体积：**壳体 + Python 后端 + ONNX 模型文件**。在不带 PaddleOCR、不离线内置 WebView2 的前提下，整体大概率能控制在几十 MB 到百 MB 内；实际大小必须以 PyInstaller/Tauri 原型包为准。

> 当前实施已决定删除模板匹配路线，因此推理端保留 ONNX Runtime；后续省体积重点放在模型量化、OpenCV/onnxruntime 打包裁剪和是否内置 WebView2。

---

## 5. 分阶段落地建议

1. **阶段一｜截图识别闭环（不打包）**：先在现有 Web 项目里加一个本地 Python 服务（FastAPI），训练并加载 **小型 CNN/ONNX**，跑通「《燕云十六声》截图→FEN→自动布局」。目标是验证棋盘定位、90 格切分、FEN 对接和编辑器回填。
2. **阶段二｜翻拍增强**：如果手机翻拍是高优先级，再做透视校正、反光/摩尔纹/白平衡增强，并用合成数据 + 少量真实翻拍样本增强同一套 CNN。
3. **阶段三｜桌面打包**：PyInstaller 打包后端为 sidecar，接入 Tauri 2；先出 Windows 包并压测，再补 macOS 包。
4. **阶段四｜分发完善**：处理 Windows 签名/SmartScreen、macOS 签名与公证、自动更新、错误日志收集、模型版本管理。
5. **阶段五｜可选扩展**：如果未来要识别其他象棋 App、印刷棋谱或真实棋盘，再考虑 PaddleOCR 或更通用的检测识别模型。

> 强烈建议：无论识别多准，残局编辑器都要保留「**识别后可手动拖动纠正**」的交互——这是体验与可靠性的安全网。

---

## 6. 已确认的范围边界

- **识别来源**：仅《燕云十六声》游戏内象棋——游戏截图 + 手机翻拍游戏画面（单一皮肤）。
- **后端**：Python（FastAPI + OpenCV + ONNX），PyInstaller 打包为 Tauri sidecar。
- **平台**：Windows（主）+ macOS。Windows 优先做、优先测。
- **不需要**：PaddleOCR、对其他象棋 App/印刷棋谱的泛化、手机实拍真实木棋盘。

- ~~视角是否翻转~~：已确认不翻转，红方恒在下。
- ~~残局编辑器是否支持 FEN~~：已确认支持。当前项目已有 `parseFen/toFen`，编辑器提交时会调用 `game.applyCustomPosition(fen)`，因此 OCR 输出 FEN 可直接进入现有流程。
- 仍需确认：手机翻拍是否为高优先级，还是「截图为主、翻拍为辅」？这决定第一版是否就要做透视校正 + CNN，还是先只做截图路。

---

### 参考来源

- [Tauri 官方：What is Tauri](https://v2.tauri.app/start/)
- [Tauri 官方：Embedding External Binaries / Sidecar](https://v2.tauri.app/develop/sidecar/)
- [Tauri 官方：Shell Plugin 权限与 sidecar API](https://v2.tauri.app/plugin/shell/)
- [Tauri 官方：Windows WebView2 说明](https://v2.tauri.app/reference/webview-versions/)
- [Tauri 官方：Windows Installer / WebView2 分发模式](https://v2.tauri.app/distribute/windows-installer/)
- [Tauri 官方：Windows Code Signing](https://v2.tauri.app/distribute/sign/windows/)
- [Tauri 官方：macOS Code Signing / Notarization](https://v2.tauri.app/distribute/sign/macos/)
- [Electron 官方：Introduction](https://electronjs.org/docs/latest/)
- [Electron 官方首页：Chromium + Node.js](https://electronjs.org/)
- [PaddleOCR 官方：PP-OCRv5](https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html)
- [PaddleOCR 官方：PP-OCRv5 多语言识别](https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html)
