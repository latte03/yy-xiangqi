# 燕云象棋残局

一个《燕云十六声》象棋残局工具：自定义残局、截图识别棋盘，并与 AI 对弈。

## 功能

- 自定义象棋残局、校验局面、对战 AI
- 截图识别棋盘，支持自动定位和手动框选四角
- 识别模型内置在桌面包中，也可通过 App 内模型更新单独升级

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

## 测试

```bash
pnpm typecheck
pnpm test:run
backend/.venv/bin/python backend/tests/test_fen.py
backend/.venv/bin/python backend/tests/test_pipeline.py
```

## 文档

- 开发约定、模型文件、版本控制见 [docs/development.md](docs/development.md)。
- 发布密钥、Tauri updater、GitHub secrets 详见 [docs/release.md](docs/release.md)。
