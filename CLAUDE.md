# 项目记忆 / Project Memory — xiangqi-endgame

> 本文件只保留长期基线、当前状态和下一步。详细开发/发布说明见 `README.md`、`docs/development.md`、`docs/release.md`、`backend/README.md`。
> 最后更新：2026-06-17

## 项目概述

《燕云十六声》象棋残局工具：玩家可自定义残局、截图识别棋盘布局，并与 AI 对弈。

技术栈：

- 前端：Vue 3 + Vite + TypeScript + Pinia + naive-ui + Konva
- AI：fairy-stockfish-nnue.wasm
- 识别后端：Python + FastAPI + OpenCV + ONNX Runtime
- 桌面端：Tauri 2 + PyInstaller sidecar
- 发布：GitHub Actions + GitHub Releases

## 范围边界

- 识别目标仅限《燕云十六声》游戏内象棋：PC/手机原生截图、手机翻拍屏幕。
- 单一棋盘皮肤；红方恒在下，暂不做朝向归一化。
- 不做通用 OCR、不支持其他象棋 App/印刷棋谱/真实木棋盘。
- Windows 优先，同时支持 macOS；后端允许使用 Python。
- 残局编辑器必须保留“识别后手动纠正”安全网。

## 核心方案

- 识别流水线：棋盘四角定位 → 透视校正 → 切 90 个交叉点 → 判空/判色/ONNX 分类 → 输出 FEN。
- 运行时只走 ONNX 模型，不维护模板匹配回退；无模型时明确报未就绪。
- 定位优先使用学习式关键点 CNN，失败时回退经典 CV，再失败由前端手动框选四角。
- 截图和翻拍共用同一定位/分类骨架，靠数据增强覆盖透视、反光、摩尔纹等差异。

## 当前实现状态

- 前端残局编辑、AI 对弈、截图识别入口、手动框选四角、识别后手动纠正已实现。
- 后端 FastAPI sidecar 已实现 `/health`、`/recognize`、`/training/*`、`/model/*`。
- 棋子分类模型：`piece_classifier.onnx` 已纳入 `backend/models`。
- 棋盘定位模型：`board_locator.onnx` 已纳入 `backend/models`，后续仍需用真实 `screenshot_1..4` 验证精度。
- 训练入口仅开发/显式开启时可见；分发构建默认推理-only，不包含 torch。
- 模型更新已实现：GitHub Release manifest → 下载双 ONNX → sha256 + ONNX shape 校验 → 版本目录落盘 → 热重载。
- Tauri 2 基础壳已落，Rust 启动时尝试拉起 PyInstaller sidecar。
- GitHub Actions 已有 `ci`、`release-models`、`release-app`。

## 版本与发布约定

- App 版本单一来源：根目录 `VERSION`，SemVer；用 `pnpm version:sync -- --version=x.y.z` 同步到前端/Tauri/Cargo。
- 模型版本独立：`backend/models/version.json`，整数版本；App 版本和模型版本不要混用。
- 代码变更走 Tauri updater 整包更新；模型变好走 App 内 GitHub Releases 模型更新。
- 固定 Release tag：App updater 读 `app-latest/latest.json`；模型更新读 `models-latest/models.json`。
- 模型 Release 是完整双 ONNX 包；不支持只发单个模型，避免半包/兼容性复杂化。
- 用户模型仅在版本高于内置且文件完整时覆盖内置；失败保留旧模型/内置模型。
- 发布操作、GitHub secrets、Tauri updater keys 统一维护在 `docs/release.md`。

## 仓库文档分工

- `README.md`：项目入口、功能、开发和测试最短路径。
- `docs/development.md`：模型文件入 Git 规则、版本同步约定。
- `docs/release.md`：GitHub Actions 发布、Tauri updater keys、secrets/vars。
- `backend/README.md`：识别后端、训练工具、后端 API。
- `docs/OCR与桌面端技术选型分析.md`：技术选型背景。

## 重要目录

- `src/components/editor/`：残局编辑器、截图识别 UI。
- `src/components/training/`：开发期模型训练 UI。
- `backend/recognizer/`：识别流水线和模型更新逻辑。
- `backend/tools/`：训练、导出、检查模型工具。
- `backend/models/`：发布基线 ONNX、labels、模型版本。
- `src-tauri/`：Tauri 桌面壳和 sidecar 配置。
- `.github/workflows/`：CI、模型发布、App 发布。

## 下一步

- 用真实 `docs/samples/screenshot_1..4` 验证 `board_locator.onnx` 四角定位精度。
- 完成首次发布前，按 `docs/release.md` 配置 GitHub repo variable/secrets。
- 跑首次发布：`release-models` → `release-app`。
- 可选桌面打磨：sidecar 冷启动状态、窗口尺寸记忆、日志入口。

## 协作约定

- 默认中文回复，简洁直接。
- 涉及边界或长期约定的变更，确认后更新本文件或对应 docs。
