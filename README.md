# 燕云象棋残局

一个《燕云十六声》象棋残局工具：前端用 Vue/Naive UI/Konva，识别后端用 Python FastAPI + OpenCV + ONNX Runtime，桌面端用 Tauri 2 打包并通过 GitHub Releases 更新。

## 功能

- 自定义象棋残局、校验局面、对战 AI
- 截图识别棋盘，支持自动定位和手动框选四角
- 识别模型内置在桌面包中，也可通过 App 内模型更新单独升级
- 桌面整包更新走 Tauri updater + GitHub Releases

## 技术栈

- Frontend: Vue 3, Vite, TypeScript, Pinia, Naive UI, Konva
- Backend sidecar: Python, FastAPI, OpenCV, ONNX Runtime
- Desktop: Tauri 2, PyInstaller sidecar
- Release: GitHub Actions + GitHub Releases

## 本地开发

安装前端依赖：

```bash
pnpm install
```

启动前端：

```bash
pnpm dev
```

启动识别后端：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

前端默认访问 `http://127.0.0.1:8765`，可用 `VITE_RECOGNIZE_API` 覆盖。

## 模型文件

发布基线模型会进入 Git：

- `backend/models/piece_classifier.onnx`
- `backend/models/board_locator.onnx`
- `backend/models/labels.txt`
- `backend/models/version.json`

不要提交训练 checkpoint、dataset、crops 或发布时生成的 `models.json`。

模型版本是整数，记录在 `backend/models/version.json`。App 版本和模型版本是两条线：App 代码更新走整包；模型变好走模型 Release。

## 版本控制

App 版本的单一来源是根目录 `VERSION`，必须是 SemVer，例如 `0.2.0`。

同步版本到 `package.json`、`src-tauri/tauri.conf.json` 和 `src-tauri/Cargo.toml`：

```bash
pnpm version:sync -- --version=0.2.0
```

检查版本是否一致：

```bash
pnpm version:check
```

## 测试

```bash
pnpm typecheck
pnpm test:run
backend/.venv/bin/python backend/tests/test_fen.py
backend/.venv/bin/python backend/tests/test_pipeline.py
```

## 桌面打包与发布

GitHub Actions 已配置三条工作流：

- `ci`: 常规检查
- `release-models`: 发布模型包到 `models-latest`
- `release-app`: 发布桌面包到 `app-latest`

首次发布建议顺序：

1. 确认 `backend/models/*.onnx` 和 `backend/models/version.json` 已更新。
2. 运行 `release-models`，生成并上传 `models.json`。
3. 运行 `release-app`，构建 Tauri 桌面包。

`release-app` 会优先从 `models-latest` 下载模型；如果该 Release 还不存在，则使用 Git 中的 `backend/models`。

## Tauri Updater Keys

Tauri updater 需要一对更新签名密钥。它们只用于验证更新包是不是可信来源，不等同于 macOS/Windows 代码签名证书。

生成密钥：

```bash
pnpm tauri signer generate -- -w ~/.tauri/xiangqi-endgame.key
```

需要配置到 GitHub：

- Repository variable `TAURI_UPDATER_PUBKEY`: 生成时输出的 public key 内容。它会写进 Tauri 配置，可以公开。
- Repository secret `TAURI_PRIVATE_KEY`: 私钥文件内容，或私钥文件路径对应的内容。必须保密，丢失后无法继续给已安装用户发布可验证更新。
- Repository secret `TAURI_KEY_PASSWORD`: 生成私钥时设置的密码。若生成时没设密码，可留空或设为空字符串。

官方要求：构建更新包时私钥必须通过环境变量 `TAURI_SIGNING_PRIVATE_KEY` 提供，密码通过 `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` 提供；`.env` 文件不会被 Tauri updater 签名流程读取。

后续若要消除系统安全提示，还需要另外接入 macOS Developer ID 签名/公证和 Windows 代码签名。
