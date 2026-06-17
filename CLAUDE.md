# 项目记忆 / Project Memory — xiangqi-endgame

> 本文件为长期项目基线，供后续会话快速对齐。最后更新：2026-06-16

## 项目概述

中国象棋残局应用。玩家自定义残局并与 AI 对弈。当前为纯前端 Web 应用。

**现有技术栈**：Vue 3 + Vite + TypeScript + Konva（棋盘渲染）+ naive-ui + Pinia + fairy-stockfish-nnue.wasm（引擎）。包管理用 pnpm。

## 当前规划（进行中）

为「自定义残局」新增**截图识别自动布局**功能，并引入本地后端、打包为桌面 App。

### 已确认的范围边界

- **识别来源**：仅《燕云十六声》游戏内象棋——①游戏截图（PC/手机原生截图）②手机翻拍游戏画面/屏幕。**单一棋盘皮肤**。
- **视角不翻转**：红方恒在下，游戏内几乎不出现黑方在下 → 无需朝向归一化。
- **透出背景较暗且一致**：棋盘是半透明叠层，但各残局间透出底色基本一致、偏暗，多底色干扰小。
- **平台**：Windows（主）+ macOS。Windows 优先。
- **后端**：可用 Python。
- **不需要**：PaddleOCR、对其他象棋 App/印刷棋谱的泛化、实拍真实木棋盘。

### 选定技术方案（详见 docs/OCR与桌面端技术选型分析.md）

- **桌面框架**：Tauri 2（复用现有 Vue 前端，包体小，跨平台）。
- **后端形态**：本地 sidecar 进程，Python + FastAPI，PyInstaller 打包，随 App 分发、离线可用。前后端走 localhost HTTP。
- **识别核心**：不是通用 OCR，而是「棋盘定位 → 切 90 个交叉点 → 每格分类 → 输出 FEN」。FEN 可无缝对接 fairy-stockfish。
- **分类**：运行时只走小型 CNN/ONNX 模型；无模型时明确提示未就绪，不再维护模板匹配回退。
- **预估包体**：前端壳 ~5MB + Python 后端（OpenCV+ONNX，无 Paddle）~40–60MB ≈ 50–70MB。

### 识别难度分两路（共用同一骨架）

| 输入 | 难度 | 要点 |
|---|---|---|
| 游戏截图 | 低 | 检测外框→切格→CNN 分类，识别后保留人工纠正 |
| 手机翻拍屏幕 | 高（透视/反光/摩尔纹/偏灰/可能手指遮挡）| 四角透视校正 + CNN 增强训练；遮挡格人工补 |

### 关键设计约束

- 残局编辑器须保留「识别后可手动拖动纠正」交互，作为任何识别方案的安全网。
- 定位禁止写死像素坐标（分辨率/缩放会变），靠检测棋盘外框 + 网格线 + 九宫斜线。

## 实现进度

### 阶段一（截图路）— 已搭好骨架，待真实截图调参
- `backend/`：Python + FastAPI 识别服务（`/health`、`/recognize`），离线运行。
  - 流水线：定位四角 → 透视校正 → 切 90 格 → 判空/判色/CNN 判类型 → FEN。
  - `recognizer/{locate,slice,classify,model_io,fen,pipeline}.py`，`app.py`，`tools/{extract_crops,gen_training_data,train_classifier}.py`。
  - 测试：`tests/test_fen.py`、`tests/test_pipeline.py`（合成棋盘端到端，已全过）。
  - FEN 输出严格对齐前端 `src/engine/fen.ts`（rank0=黑底线，WXF 风格 KAEHRCP）。
- 前端：`src/utils/recognize-api.ts` + 编辑器「截图识别（实验）」卡片，识别结果经
  `editor.loadFen()` 填入；保留手动拖动纠正。typecheck 通过。
- 前端「手动框选四角」已实现：`src/components/editor/RecognizeCorners.vue`（上传图后
  弹窗，4 个可拖角点，换算回原图像素传 `corners` 给后端；含「自动定位识别」按钮）。
  作为自动定位失败的兜底。typecheck 通过。
  （注：沙箱内 `vite build` 因 rolldown 原生绑定缺失而失败，属环境问题；本机正常。）

### 模板方案（已废弃）
- 用户已拍板：直接删掉模板匹配路线，运行时只用 ONNX 模型。
- `backend/templates/` 与 `tools/gen_synthetic_templates.py` 已删除。
- 原 `extract_templates.py` 改为 `extract_crops.py`，只负责收集训练裁剪到 `backend/crops/`，不参与运行时识别。

### 真实截图验证（历史里程碑 2026-06-16）
- `docs/samples/full.png`（王大演开局，含全 14 类）曾用于验证旧模板方案：
  - 网格四角（HoughCircles 取四角棋子圆心）：`179.5,126.5;845.5,126.5;843.5,805.5;180.5,805.5`
  - 对应 FEN = 标准初始局面 `rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR`
  - 旧模板验证曾证明几何/切格/判空/判色/FEN 骨架可行，但模板路线已不再作为运行时方案。
  - **整盘 32 子识别完全正确（MATCH）**。
- 历史调参要点：
  - 判空 `bright_ratio > 0.13`（真子≥0.16，空格≤0.05，纹理假阳性~0.10）。
  - 旧模板匹配参数已删除；后续分类泛化靠 CNN。
- 注意：`auto_detect_corners` 对真实图仍只能框到「面板外框」而非落子网格，
  当前主用前端「手动框选四角」兜底（已验证此路径 MATCH）。自动定位待更多样本调参。

### ⚠️ full.png 是 AI 生成的假图（用户告知，已弃用）
- `docs/samples/full.png` 非真实游戏截图，从它提取的旧模板对真实游戏不准，已弃用并删除
  （`templates_fake_full/`）。真实素材为 `screenshot_1..4`（1/2/3 同为 1440×648）。

### 已转向小型 CNN 分类（2026-06-16）
- 经验证纯模板匹配跨图泛化弱 → 按选型计划转 CNN（用户拍板）。
- 新增（沙箱无 torch，训练在本机）：
  - `recognizer/model_io.py`：类别(7)/输入(64灰度)/preprocess 共享定义。
  - `tools/gen_training_data.py`：渲染真实字形+强增强生成数据集（已测，样本质量好）。
  - `tools/train_classifier.py`：小型 CNN(约3卷积)→ 导出 `models/piece_classifier.onnx`。
  - `recognizer/classify.py`：只保留 `OnnxClassifier`(onnxruntime)，无模型不回退，`/health` 返回 `model_ready: false`。
  - 后端新增 `/training/*` API：提取 crops、生成 dataset、训练/导出模型、检查模型，长任务后台执行并轮询日志。
  - 前端新增「模型训练」入口：`src/components/training/Training.vue` + `src/utils/training-api.ts`，可在 Web 页面完成真实截图→crops→dataset→ONNX→检查模型流程。
  - ONNX 工具链增强：`gen_training_data.py` 支持 `--clean`、自定义字体、manifest、真实裁剪增强次数；
    `train_classifier.py` 支持随机种子、checkpoint、`--export-only`、opset 17 legacy ONNX 导出、混淆矩阵、PyTorch/ONNX 输出一致性校验；
    `tools/check_model.py` 可独立检查模型加载、单图预测、数据集准确率和推理耗时。
- 待用户本机：`pip install -r requirements-train.txt` → `extract_crops.py`(可选) → `gen_training_data.py` → `train_classifier.py`，
  生成 `models/piece_classifier.onnx` 后识别自动走 CNN。

### 多张真实截图验证（2026-06-16，关键结论）
- 已有样本：`docs/samples/` 下 full.png + screenshot_1..4（5 张，含开局与残局、jpg/png、不同分辨率）。
- **识别核心已充分验证**：full.png（开局 32 子）MATCH；screenshot_4（王大演残局，
  用旧同图模板）MATCH，反证几何/切格/判空/判色/FEN 全部正确，残局稀疏局面也准。
  - screenshot_4 网格四角（圆心间距拟合）：`152,78;760,78;760,780;152,780`，
    FEN=`9/4a4/4ka3/9/4P1b2/9/9/9/9/3K1AB2`。
- **两个硬结论（经典 CV 的天花板，均指向小型 CNN）**：
  1. **自动定位不可靠**：半透明棋盘对比度低，5 张里仅 ~1 张能用轮廓找到面板，
     且只到「面板外框」非落子网格；竖线太淡 Hough 抓不全。→ 当前必须靠前端手动框选四角
     （已验证此路 MATCH）。鲁棒自动定位需学习式（关键点/分割 CNN）。
  2. **模板跨图迁移差**：A 图模板识别 B 图明显掉准（尺度/光照/渲染差异）；
     且把多图模板混池取最高分会「跨类干扰」反而更糟（加入 s4 模板后 full.png 由
     MATCH 退化）。→ 纯模板匹配只在「同图/同尺度」可靠，泛化必须靠 CNN。
- 工具修复：`extract_crops.py` 的 idx 按已有文件续编（多图累加而非覆盖），用于训练真实裁剪。
- 环境备查：沙箱有 `onnxruntime`(1.23) 可做推理，但无 torch/tf/sklearn 且无外网，
  CNN 训练需在本机进行（脚本可由我生成）。

### 学习式定位 CNN（2026-06-17，截图+翻拍统一，已搭好待训练）
- 经典 CV 自动定位已确认无法一步到位（半透明/线淡/面板倾斜/背景干扰），
  用户拍板：上关键点 CNN，且与翻拍路合并（同一模型靠数据增强覆盖两 régime）。
- 新增（沙箱无 torch，训练在本机）：
  - `recognizer/locate_model.py`：LOC_INPUT=256、letterbox 预处理、四角归一化编解码（往返误差 0px）。
  - `tools/gen_locate_data.py`：全场景合成（半透明面板+网格+九宫+河界+棋子）→ 随机背景+单应，
    screenshot régime（弱透视/清晰）与 photo régime（强透视/反光/摩尔纹/模糊/偏色）混合，
    标注四角；可 `--real-labels` 混入真实标注。已验证生成图+标注精确（截图/翻拍两类目视 OK）。
  - `tools/train_locator.py`：小 CNN 回归 8 坐标(sigmoid)→ 导出 `models/board_locator.onnx`，
    checkpoint+ONNX 校验+opset17，验证报四角平均像素误差(@256)。
  - `recognizer/locate.py`：`CnnLocator`(onnxruntime) + `locate_corners()`（CNN 优先→经典回退→手动兜底）；
    `pipeline.recognize` 已改用 `locate_corners`。桩 session 验证解码接线正确、在界内。
  - 后端：`/health` 加 `locator_ready`；新增 `/training/gen-locate-data`、`/training/train-locator`；
    `extract-crops` 带 corners 时自动把「图+四角」存进 `locate_labels/` 作定位真实标注（一举两得）。
  - 前端：`training-api.ts` 加 `generateLocateData`/`trainLocator`；
    `Training.vue` 新增「4. 棋盘定位模型」卡片（生成定位数据 + 训练定位模型，
    含「混入真实标注」开关）；第 1 步框选四角时提示「图+四角」已同时存为定位标注。typecheck 通过。
- 数据闭环：棋子训练第 1 步手动框四角 → extract-crops 带 corners → 后端存 `locate_labels/` →
  生成定位数据勾「混入真实标注」即自动用上。手动框选越多，定位越准。
- 待用户本机：`gen_locate_data.py` → `train_locator.py` 产出 `board_locator.onnx`，
  就绪后自动定位走 CNN（截图+翻拍）。

### 打包前置（2026-06-17）
- 训练入口按构建开关 gate：`App.vue` 用 `import.meta.env.DEV || VITE_ENABLE_TRAINING==='true'`
  控制；分发构建（生产、未设标志）**不含**「模型训练」入口，Training 组件用
  `defineAsyncComponent` 按需加载、被拆为不加载的独立 chunk。首页入口网格改 auto-fit 适应 2/3 张卡。
  `.env.example` 记录 `VITE_RECOGNIZE_API` 与 `VITE_ENABLE_TRAINING`。
  - 约定：训练是维护者离线活；分发包是推理-only（onnxruntime），不含 torch，
    内置预训练 onnx 作只读资产；终端用户只识别+手动纠正，无法/无需重训。
- 截图导入增强（Editor）：除「点击上传」外，新增**拖拽图片到识别区** + **剪贴板粘贴 Ctrl/Cmd+V**
  （桌面端最自然），统一走 `startRecognizeFlow`。typecheck 通过。

### 更新策略（2026-06-17，打包前已敲定）
- **版本控制（2026-06-17）**：
  - App 版本单一来源是根目录 `VERSION`，SemVer 格式；`pnpm version:sync -- --version=x.y.z`
    同步到 `package.json`、`src-tauri/tauri.conf.json`、`src-tauri/Cargo.toml`。
  - CI 跑 `pnpm version:check`，防止多处版本号漂移。
  - 模型版本独立，用 `backend/models/version.json` 的整数版本；App 整包版本和模型包版本不要混用。
- **整包更新**：Tauri 2 updater 插件 + GitHub Releases（前后端代码变动走这条）。需更新签名密钥，macOS 另需代码签名/公证。Tauri 接入阶段配。
- **仅模型更新（in-app，走 GitHub Releases）**：模型当数据资产发布，App 内下载，不发整包。
  - 发布侧：建模型 Release（如 tag `models-vN`），**每个 Release 固定完整包含两个 ONNX**：
    `piece_classifier.onnx`、`board_locator.onnx`、`models.json`(版本号+各文件 url+sha256)。
    暂不支持只发单个模型，避免局部版本/半包状态复杂化。
  - 加载策略：用户数据目录和内置目录都用 `version.json {"version": N}` 记录整包模型版本；
    **只有用户目录版本高于内置版本且两个 ONNX 都齐全时，才优先用户模型**，否则回退打包内置。
    整包升级带来的新内置模型不会被旧下载模型遮住。
    下载模型按 `appData/models/packages/<version>/` 存完整版本目录，`version.json` 指向当前版本目录，
    避免更新中断时出现半替换/混合模型包。
  - 更新流程：拉 manifest → 比当前 active 版本 → 下载两个 onnx → **校验 sha256 + onnxruntime 试加载 + 输入/输出 shape 契约校验**
    通过才替换 + 热重载；任一步失败保留旧模型，不会变砖。
  - 写入位置用平台标准用户数据目录（可被 env `XIANGQI_MODEL_DIR` 覆盖）；
    manifest 地址通过打包时注入 `XIANGQI_MODELS_MANIFEST`，不在源码里写死真实 Release 地址。
  - 实现：`recognizer/model_store.py`（路径解析/版本）；`/model/status`、`/model/check-update`、
    `/model/apply-update`、`/model/update-status`；前端「检查模型更新」入口（对所有用户开放，属推理侧），
    下载/校验/应用过程显示真实进度条。
- **Tauri 接入（2026-06-17 已落基础壳）**：
  - `src-tauri/` 使用 Tauri 2；Rust 启动时尝试拉起 PyInstaller sidecar `binaries/recognizer`。
  - 普通 `pnpm tauri:build` 不强制 sidecar；正式整包更新构建走
    `pnpm tauri:build:release` + `src-tauri/tauri.release.conf.json`，该 overlay 开启 updater artifacts、
    配置 updater endpoint/pubkey，并强制带入 `externalBin`。
  - updater Release 用 Tauri `latest.json` + 签名产物；真实 `pubkey` 和 GitHub Release endpoint 发布前替换。
- **GitHub Actions 发布（2026-06-17 已落工作流）**：
  - 固定 tag 策略，避免 App Release 和 Model Release 抢 GitHub `/releases/latest`：
    App updater 固定读 `app-latest/latest.json`；模型更新固定读 `models-latest/models.json`。
  - `.github/workflows/ci.yml`：PR/push 跑前端 typecheck + Vitest、后端 Python 测试、Tauri cargo check。
  - `.github/workflows/release-models.yml`：手动输入 `version`、两个 ONNX 下载 URL，生成 `models.json`/`version.json`，
    并上传到 `models-latest` Release。ONNX 已允许进 Git，因此下载 URL 可留空，默认使用仓库里的 `backend/models/*.onnx`。
  - `.github/workflows/release-app.yml`：手动输入 App 版本，从 `models-latest` 下载两个 ONNX 内置进 PyInstaller sidecar，
    再用 `tauri-apps/tauri-action` 构建 macOS arm64、macOS x64、Windows x64、Linux x64 并上传到 `app-latest`。
    若 `models-latest` 尚不存在，则直接使用 Git 中的 `backend/models` 作为内置模型。
  - GitHub 需配置：repo variable `TAURI_UPDATER_PUBKEY`；repo secrets `TAURI_PRIVATE_KEY`、`TAURI_KEY_PASSWORD`。
    生成命令：`pnpm tauri signer generate --write-keys ~/.tauri/xiangqi-endgame.key`。
    `TAURI_UPDATER_PUBKEY` 是可公开 public key 内容；`TAURI_PRIVATE_KEY` 是私钥内容，必须长期保存且保密；
    `TAURI_KEY_PASSWORD` 是生成私钥时设置的密码（无密码可空）。私钥丢失后，已安装用户无法继续接收同一更新信任链下的新版本。
    macOS Developer ID 签名/公证、Windows 代码签名还未接入，后续拿到证书后再补。
- **模型入 Git 约定（2026-06-17）**：
  - 允许追踪发布基线：`backend/models/*.onnx`、`labels.txt`、`version.json`、`README.md`。
  - 继续忽略训练 checkpoint / 临时发布产物：`*.pt`、`models.json`、dataset、crops、locate_dataset 等。
  - `version.json` 是内置模型包版本；当内置版本高于用户下载版本时，整包内置模型优先生效。

### 下一步
- [ ] 本机训练定位 CNN，产出 `models/board_locator.onnx` 并在真实 screenshot_1..4 上验证四角精度。
- [ ] 桌面打包：PyInstaller 打后端为 sidecar（含 models/ 两个 onnx + `version.json`），接入 Tauri 2；
      打包构建保持 `VITE_ENABLE_TRAINING` 未设（训练入口不进分发包）。
- [ ] Tauri updater（整包）填真实 pubkey/endpoint；模型 Release 的 `models.json` 由发布流程生成，
      `XIANGQI_MODELS_MANIFEST` 通过打包环境注入。
- [ ] 配置 GitHub Actions secrets/vars；首次发布顺序：先 `release-models` 上传 `models-latest`，
      再 `release-app` 构建 `app-latest`。
- [ ] （可选）sidecar 冷启动过渡态、窗口最小尺寸/记忆等桌面化打磨。

## 待办 / 待确认

- [x] 截图为主、翻拍后续
- [x] 支持 FEN。
- [ ] 用户补充：把 3 张样例截图放入 `docs/samples/`（王大演的棋局截图、王十三的棋局翻拍照、王大演干净截图）。

## 样例素材

`docs/samples/`（待用户补充）：含游戏截图与手机翻拍两类，是定位与合成训练的参考基线。

## 协作约定（用户偏好）

- 用中文回复，简洁直接。
- 任务/项目第一次对话先问清边界再动手。
- 资料经用户确认后存入项目记忆（本文件）。
